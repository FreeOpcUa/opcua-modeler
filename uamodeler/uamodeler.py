#! /usr/bin/env python3

import sys
import os
import logging

from PyQt5.QtCore import QTimer, QSettings, QModelIndex, Qt, QCoreApplication
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox, QStyledItemDelegate, QMenu

from opcua import ua
from opcua import copy_node
from opcua.common.ua_utils import get_node_children
from opcua.common.instantiate import instantiate

from uawidgets import resources
from uawidgets.attrs_widget import AttrsWidget
from uawidgets.tree_widget import TreeWidget
from uawidgets.refs_widget import RefsWidget
from uawidgets.new_node_dialogs import NewNodeBaseDialog, NewUaObjectDialog, NewUaVariableDialog, NewUaMethodDialog
from uawidgets.utils import trycatchslot
from uawidgets.logger import QtHandler

from uamodeler.server_manager import ServerManager
from uamodeler.uamodeler_ui import Ui_UaModeler
from uamodeler.namespace_widget import NamespaceWidget
from uamodeler.refnodesets_widget import RefNodeSetsWidget


logger = logging.getLogger(__name__)


class BoldDelegate(QStyledItemDelegate):

    def __init__(self, parent, model, added_node_list):
        QStyledItemDelegate.__init__(self, parent)
        self.added_node_list = added_node_list
        self.model = model

    def paint(self, painter, option, idx):
        new_idx = idx.sibling(idx.row(), 0)
        item = self.model.itemFromIndex(new_idx)
        if item and item.data(Qt.UserRole) in self.added_node_list:
            option.font.setWeight(QFont.Bold)
        QStyledItemDelegate.paint(self, painter, option, idx)


class UaModeler(QMainWindow):

    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_UaModeler()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon(":/network.svg"))

        # we only show statusbar in case of errors
        self.ui.statusBar.hide()

        # setup QSettings for application and get a settings object
        QCoreApplication.setOrganizationName("FreeOpcUa")
        QCoreApplication.setApplicationName("OpcUaModeler")
        self.settings = QSettings()
        self._last_dir = self.settings.value("last_dir", ".")

        self._restore_state()

        self.server_mgr = ServerManager(self.ui.actionUseOpenUa)
        self._new_nodes = []  # the added nodes we will save
        self._current_path = None
        self._modified = False
        self._copy_clipboard = None

        self.tree_ui = TreeWidget(self.ui.treeView)
        self.tree_ui.error.connect(self.show_error)
        delegate = BoldDelegate(self, self.tree_ui.model, self._new_nodes)
        self.ui.treeView.setItemDelegate(delegate)
        self.ui.treeView.selectionModel().currentChanged.connect(self._update_actions_state)

        self.refs_ui = RefsWidget(self.ui.refView)
        self.refs_ui.error.connect(self.show_error)
        self.attrs_ui = AttrsWidget(self.ui.attrView, show_timestamps=False)
        self.attrs_ui.error.connect(self.show_error)
        self.attrs_ui.attr_written.connect(self._attr_written)
        self.idx_ui = NamespaceWidget(self.ui.namespaceView)
        self.nodesets_ui = RefNodeSetsWidget(self.ui.refNodeSetsView)
        self.nodesets_ui.error.connect(self.show_error)
        self.nodesets_ui.nodeset_added.connect(self.nodesets_change)
        self.nodesets_ui.nodeset_removed.connect(self.nodesets_change)

        self.ui.treeView.activated.connect(self.show_refs)
        self.ui.treeView.clicked.connect(self.show_refs)
        self.ui.treeView.activated.connect(self.show_attrs)
        self.ui.treeView.clicked.connect(self.show_attrs)

        # fix icon stuff
        self.ui.actionNew.setIcon(QIcon(":/new.svg"))
        self.ui.actionOpen.setIcon(QIcon(":/open.svg"))
        self.ui.actionCopy.setIcon(QIcon(":/copy.svg"))
        self.ui.actionPaste.setIcon(QIcon(":/paste.svg"))
        self.ui.actionDelete.setIcon(QIcon(":/delete.svg"))
        self.ui.actionSave.setIcon(QIcon(":/save.svg"))
        self.ui.actionAddFolder.setIcon(QIcon(":/folder.svg"))
        self.ui.actionAddObject.setIcon(QIcon(":/object.svg"))
        self.ui.actionAddMethod.setIcon(QIcon(":/method.svg"))
        self.ui.actionAddObjectType.setIcon(QIcon(":/object_type.svg"))
        self.ui.actionAddProperty.setIcon(QIcon(":/property.svg"))
        self.ui.actionAddVariable.setIcon(QIcon(":/variable.svg"))
        self.ui.actionAddVariableType.setIcon(QIcon(":/variable_type.svg"))
        self.ui.actionAddDataType.setIcon(QIcon(":/data_type.svg"))
        self.ui.actionAddReferenceType.setIcon(QIcon(":/reference_type.svg"))

        self.setup_context_menu_tree()

        # actions
        self.ui.actionNew.triggered.connect(self._new)
        self.ui.actionOpen.triggered.connect(self._open)
        self.ui.actionCopy.triggered.connect(self._copy)
        self.ui.actionPaste.triggered.connect(self._paste)
        self.ui.actionDelete.triggered.connect(self._delete)
        self.ui.actionImport.triggered.connect(self._import_slot)
        self.ui.actionSave.triggered.connect(self._save_slot)
        self.ui.actionSaveAs.triggered.connect(self._save_as)
        self.ui.actionCloseModel.triggered.connect(self._close_model_slot)
        self.ui.actionAddObjectType.triggered.connect(self._add_object_type)
        self.ui.actionAddObject.triggered.connect(self._add_object)
        self.ui.actionAddFolder.triggered.connect(self._add_folder)
        self.ui.actionAddMethod.triggered.connect(self._add_method)
        self.ui.actionAddDataType.triggered.connect(self._add_data_type)
        self.ui.actionAddVariable.triggered.connect(self._add_variable)
        self.ui.actionAddVariableType.triggered.connect(self._add_variable_type)
        self.ui.actionAddProperty.triggered.connect(self._add_property)

        self._disable_actions()

    def _update_actions_state(self, current, previous):
        self._disable_add_actions()
        node = self.tree_ui.get_current_node(current)
        if not node or node in (self.server_mgr.nodes.root, 
                                self.server_mgr.nodes.types, 
                                self.server_mgr.nodes.event_types, 
                                self.server_mgr.nodes.object_types, 
                                self.server_mgr.nodes.reference_types, 
                                self.server_mgr.nodes.variable_types, 
                                self.server_mgr.nodes.data_types):
            return
        path = node.get_path()
        nodeclass = node.get_node_class()

        self.ui.actionAddFolder.setEnabled(True)
        self.ui.actionCopy.setEnabled(True)
        self.ui.actionPaste.setEnabled(True)
        self.ui.actionDelete.setEnabled(True)

        if self.server_mgr.nodes.base_object_type in path:
            self.ui.actionAddObjectType.setEnabled(True)

        if self.server_mgr.nodes.base_variable_type in path:
            self.ui.actionAddVariableType.setEnabled(True)

        if self.server_mgr.nodes.base_data_type in path:
            self.ui.actionAddDataType.setEnabled(True)
            if self.server_mgr.nodes.enum_data_type in path:
                self.ui.actionAddProperty.setEnabled(True)
            return  # not other nodes should be added here

        if nodeclass != ua.NodeClass.Variable:
            self.ui.actionAddFolder.setEnabled(True)
            self.ui.actionAddObject.setEnabled(True)
            self.ui.actionAddVariable.setEnabled(True)
            self.ui.actionAddProperty.setEnabled(True)
            self.ui.actionAddMethod.setEnabled(True)

    def setup_context_menu_tree(self):
        self.ui.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeView.customContextMenuRequested.connect(self._show_context_menu_tree)
        self._contextMenu = QMenu()

        # tree view menu
        self._contextMenu.addAction(self.ui.actionCopy)
        self._contextMenu.addAction(self.ui.actionPaste)
        self._contextMenu.addAction(self.ui.actionDelete)
        self._contextMenu.addSeparator()
        self._contextMenu.addAction(self.ui.actionAddFolder)
        self._contextMenu.addAction(self.ui.actionAddObject)
        self._contextMenu.addAction(self.ui.actionAddVariable)
        self._contextMenu.addAction(self.ui.actionAddProperty)
        self._contextMenu.addAction(self.ui.actionAddMethod)
        self._contextMenu.addAction(self.ui.actionAddObjectType)
        self._contextMenu.addAction(self.ui.actionAddVariableType)
        self._contextMenu.addAction(self.ui.actionAddDataType)

    def _show_context_menu_tree(self, position):
        node = self.tree_ui.get_current_node()
        if node:
            self._contextMenu.exec_(self.ui.treeView.viewport().mapToGlobal(position))

    @trycatchslot
    def _delete(self):
        node = self.tree_ui.get_current_node()
        if node:
            nodes = get_node_children(node)
            for n in nodes:
                n.delete()
                if n in self._new_nodes:
                    self._new_nodes.remove(n)
            self.tree_ui.remove_current_item()

    @trycatchslot
    def _copy(self):
        node = self.tree_ui.get_current_node()
        if node:

            self._copy_clipboard = node

    @trycatchslot
    def _paste(self):
        if self._copy_clipboard:
            parent = self.tree_ui.get_current_node()
            try:
                added_nodes = copy_node(parent, self._copy_clipboard)
            except Exception as ex:
                self.show_error(ex)
                raise
            self._new_nodes.extend(added_nodes)
            self.tree_ui.reload_current()
            self.show_refs()
            self._modified = True

    def _attr_written(self, attr, dv):
        self._modified = True
        if attr == ua.AttributeIds.BrowseName:
            self.tree_ui.update_browse_name_current_item(dv.Value.Value)
        elif attr == ua.AttributeIds.DisplayName:
            self.tree_ui.update_display_name_current_item(dv.Value.Value)
      
    def _restore_state(self):
        self.resize(int(self.settings.value("main_window_width", 800)),
                    int(self.settings.value("main_window_height", 600)))
        #self.restoreState(self.settings.value("main_window_state", b"", type="QByteArray"))
        self.restoreState(self.settings.value("main_window_state", bytearray()))
        self.ui.splitterLeft.restoreState(self.settings.value("splitter_left", bytearray()))
        self.ui.splitterRight.restoreState(self.settings.value("splitter_right", bytearray()))
        self.ui.splitterCenter.restoreState(self.settings.value("splitter_center", bytearray()))

    def _disable_model_actions(self):
        self.ui.actionImport.setEnabled(False)
        self.ui.actionSave.setEnabled(False)
        self.ui.actionSaveAs.setEnabled(False)

    def _disable_actions(self):
        self._disable_add_actions()
        self._disable_model_actions()

    def _disable_add_actions(self):
        self.ui.actionPaste.setEnabled(False)
        self.ui.actionCopy.setEnabled(False)
        self.ui.actionDelete.setEnabled(False)
        self.ui.actionAddObject.setEnabled(False)
        self.ui.actionAddFolder.setEnabled(False)
        self.ui.actionAddVariable.setEnabled(False)
        self.ui.actionAddProperty.setEnabled(False)
        self.ui.actionAddDataType.setEnabled(False)
        self.ui.actionAddVariableType.setEnabled(False)
        self.ui.actionAddObjectType.setEnabled(False)
        self.ui.actionAddMethod.setEnabled(False)

    def _enable_model_actions(self):
        self.ui.actionImport.setEnabled(True)
        self.ui.actionSave.setEnabled(True)
        self.ui.actionSaveAs.setEnabled(True)
        #self.ui.actionAddObject.setEnabled(True)
        #self.ui.actionAddFolder.setEnabled(True)
        #self.ui.actionAddVariable.setEnabled(True)
        #self.ui.actionAddProperty.setEnabled(True)
        #self.ui.actionAddDataType.setEnabled(True)
        #self.ui.actionAddVariableType.setEnabled(True)
        #self.ui.actionAddObjectType.setEnabled(True)

    @trycatchslot
    def _close_model_slot(self):
        self._close_model()

    def _close_model(self):
        if not self.really_exit():
            return False
        self._disable_actions()
        self.tree_ui.clear()
        self.refs_ui.clear()
        self.attrs_ui.clear()
        self.idx_ui.clear()
        self.nodesets_ui.clear()
        self._current_path = None
        self._modified = False
        self._update_title()
        self.server_mgr.stop_server()
        return True

    def _update_title(self):
        self.setWindowTitle("FreeOpcUa Modeler " + str(self._current_path))

    @trycatchslot
    def _new(self):
        if not self._close_model():
            return
        self._create_new_model()

    def _create_new_model(self):
        del(self._new_nodes[:])  # empty list while keeping reference

        endpoint = "opc.tcp://0.0.0.0:48400/freeopcua/uamodeler/"
        logger.info("Starting server on %s", endpoint)
        self.server_mgr.start_server(endpoint)

        self.tree_ui.set_root_node(self.server_mgr.nodes.root)
        self.idx_ui.set_node(self.server_mgr.get_node(ua.ObjectIds.Server_NamespaceArray))
        self.nodesets_ui.set_server_mgr(self.server_mgr)
        self._modified = False
        self._enable_model_actions()
        self._current_path = "NoName"
        self._update_title()
        return True

    @trycatchslot
    def _import_slot(self):
        self._import()

    def _import(self, path=None):
        if not path:
            path, ok = self._get_xml()
            if not ok:
                return None
        self._last_dir = os.path.dirname(path)
        try:
            new_nodes = self.server_mgr.import_xml(path)
            self._new_nodes.extend([self.server_mgr.get_node(node) for node in new_nodes])
            self._modified = True
        except Exception as ex:
            self.show_error(ex)
            raise
        # we maybe should only reload the imported nodes
        self.tree_ui.reload()
        self.idx_ui.reload()
        return path

    def _get_xml(self):
        return QFileDialog.getOpenFileName(self, caption="Open OPC UA XML", filter="XML Files (*.xml *.XML)", directory=self._last_dir)

    @trycatchslot
    def _open(self):
        if not self._close_model():
            return
        path, ok = self._get_xml()
        if not ok:
            return
        self._create_new_model()
        try:
            path = self._import(path)
        except:
            self._close_model()
            raise
        self._modified = False
        self._current_path = path
        self._update_title()

    @trycatchslot
    def _save_as(self):
        path, ok = QFileDialog.getSaveFileName(self, caption="Save OPC UA XML", filter="XML Files (*.xml *.XML)")
        if ok:
            self._current_path = path
            self._update_title()
            self._save()

    @trycatchslot
    def _save_slot(self):
        self._save()

    def _save(self):
        if not self._current_path or self._current_path == "NoName":
            path, ok = QFileDialog.getSaveFileName(self, caption="Save OPC UA XML", filter="XML Files (*.xml *.XML)")
            self._current_path = path
            if not ok:
                return
        logger.info("Saving to %s", self._current_path)
        logger.info("Exporting  %s nodes: %s", len(self._new_nodes), self._new_nodes)
        logger.info("and namespaces: %s ", self.server_mgr.get_namespace_array()[1:])
        uris = self.server_mgr.get_namespace_array()[1:]
        try:
            self.server_mgr.export_xml(self._new_nodes, uris, self._current_path)
        except Exception as ex:
            self.show_error(ex)
            raise
        self._modified = False
        self._update_title()
        self.show_msg(self._current_path + " saved")

    def really_exit(self):
        if self._modified:
            reply = QMessageBox.question(
                self,
                "OPC UA Modeler",
                "Model is modified, do you really want to close model?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply != QMessageBox.Yes:
                return False

        return True

    def _after_add(self, new_nodes):
        if isinstance(new_nodes, (list, tuple)):
            self._new_nodes.extend(new_nodes)
        else:
            self._new_nodes.append(new_nodes)
        self.tree_ui.reload_current()
        self.show_refs()
        self._modified = True

    @trycatchslot
    def _add_method(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewUaMethodDialog.getArgs(self, "Add Method", self.server_mgr)
        if ok:
            logger.info("Creating method type with args: %s", args)
            new_nodes = []
            new_node = parent.add_method(*args)
            new_nodes.append(new_node)
            new_nodes.extend(new_node.get_children())
            self._after_add(new_nodes)

    @trycatchslot
    def _add_object_type(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewNodeBaseDialog.getArgs(self, "Add Object Type", self.server_mgr)
        if ok:
            logger.info("Creating object type with args: %s", args)
            new_node = parent.add_object_type(*args)
            self._after_add(new_node)

    @trycatchslot
    def _add_folder(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewNodeBaseDialog.getArgs(self, "Add Folder", self.server_mgr)
        if ok:
            logger.info("Creating folder with args: %s", args)
            new_node = parent.add_folder(*args)
            self._after_add(new_node)

    @trycatchslot
    def _add_object(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewUaObjectDialog.getArgs(self, "Add Object", self.server_mgr, base_node_type=self.server_mgr.nodes.base_object_type)
        if ok:
            logger.info("Creating object with args: %s", args)
            nodeid, bname, otype = args
            new_nodes = instantiate(parent, otype, bname=bname, nodeid=nodeid)
            self._after_add(new_nodes)

    @trycatchslot
    def _add_data_type(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewNodeBaseDialog.getArgs(self, "Add Data Type", self.server_mgr)
        if ok:
            logger.info("Creating data type with args: %s", args)
            new_node = parent.add_data_type(*args)
            self._after_add(new_node)
    
    @trycatchslot
    def _add_variable(self):
        parent = self.tree_ui.get_current_node()
        dtype = self.settings.value("last_datatype", None)
        args, ok = NewUaVariableDialog.getArgs(self, "Add Variable", self.server_mgr, default_value=9.99, dtype=dtype)
        if ok:
            logger.info("Creating variable with args: %s", args)
            self.settings.setValue("last_datatype", args[4])
            new_node = parent.add_variable(*args)
            self._after_add(new_node)

    @trycatchslot
    def _add_property(self):
        parent = self.tree_ui.get_current_node()
        dtype = self.settings.value("last_datatype", None)
        args, ok = NewUaVariableDialog.getArgs(self, "Add Property", self.server_mgr, default_value=9.99, dtype=dtype)
        if ok:
            logger.info("Creating property with args: %s", args)
            self.settings.setValue("last_datatype", args[4])
            new_node = parent.add_property(*args)
            self._after_add(new_node)

    @trycatchslot
    def _add_variable_type(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewUaObjectDialog.getArgs(self, "Add Variable Type", self.server_mgr, base_node_type=self.server_mgr.get_node(ua.ObjectIds.BaseVariableType))
        if ok:
            logger.info("Creating variable type with args: %s", args)
            nodeid, bname, datatype = args
            new_node = parent.add_variable_type(nodeid, bname, datatype.nodeid)
            self._after_add(new_node)

    @trycatchslot
    def show_refs(self, idx=None):
        node = self.get_current_node(idx)
        self.refs_ui.show_refs(node)

    @trycatchslot
    def show_attrs(self, idx=None):
        if not isinstance(idx, QModelIndex):
            idx = None
        node = self.get_current_node(idx)
        self.attrs_ui.show_attrs(node)

    def show_error(self, msg):
        self.ui.statusBar.show()
        self.ui.statusBar.setStyleSheet("QStatusBar { background-color : red; color : black; }")
        self.ui.statusBar.showMessage(str(msg))
        QTimer.singleShot(2500, self.ui.statusBar.hide)

    def show_msg(self, msg):
        self.ui.statusBar.show()
        self.ui.statusBar.setStyleSheet("QStatusBar { background-color : green; color : black; }")
        self.ui.statusBar.showMessage(str(msg))
        QTimer.singleShot(1500, self.ui.statusBar.hide)

    def get_current_node(self, idx=None):
        return self.tree_ui.get_current_node(idx)
    
    def nodesets_change(self, data):
        self.idx_ui.reload()
        self.tree_ui.reload()
        self.refs_ui.clear()
        self.attrs_ui.clear()

    def closeEvent(self, event):
        if not self._close_model():
            event.ignore()
            return
        self.attrs_ui.save_state()
        self.refs_ui.save_state()
        self.settings.setValue("last_dir", self._last_dir)
        self.settings.setValue("main_window_width", self.size().width())
        self.settings.setValue("main_window_height", self.size().height())
        self.settings.setValue("main_window_state", self.saveState())
        self.settings.setValue("splitter_left", self.ui.splitterLeft.saveState())
        self.settings.setValue("splitter_right", self.ui.splitterRight.saveState())
        self.settings.setValue("splitter_center", self.ui.splitterCenter.saveState())
        self.server_mgr.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    modeler = UaModeler()
    handler = QtHandler(modeler.ui.logTextEdit)
    logging.getLogger().addHandler(handler)
    logging.getLogger("uamodeler").setLevel(logging.INFO)
    logging.getLogger("uawidgets").setLevel(logging.INFO)
    #logging.getLogger("opcua").setLevel(logging.INFO)  # to enable logging of ua server
    modeler.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
