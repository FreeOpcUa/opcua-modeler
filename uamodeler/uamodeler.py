#! /usr/bin/env python3

import sys
import os

from PyQt5.QtCore import QTimer, QSettings, QModelIndex, Qt, QCoreApplication
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox, QStyledItemDelegate, QMenu

from opcua import ua
from opcua import Server
from opcua import copy_node
from opcua import Node
from opcua.common.ua_utils import get_node_children
from opcua.common.xmlexporter import XmlExporter
from opcua.common.instantiate import instantiate

from uawidgets import resources
from uawidgets.attrs_widget import AttrsWidget
from uawidgets.tree_widget import TreeWidget
from uawidgets.refs_widget import RefsWidget
from uawidgets.new_node_dialogs import NewNodeBaseDialog, NewUaObjectDialog, NewUaVariableDialog, NewUaMethodDialog
from uamodeler.uamodeler_ui import Ui_UaModeler
from uamodeler.namespace_widget import NamespaceWidget
from uamodeler.refnodesets_widget import RefNodeSetsWidget


class BoldDelegate(QStyledItemDelegate):

    def __init__(self, parent, model, added_node_list):
        QStyledItemDelegate.__init__(self, parent)
        self.added_node_list = added_node_list
        self.model = model

    def paint(self, painter, option, idx):
        new_idx = idx.sibling(idx.row(), 0)
        item = self.model.itemFromIndex(new_idx)
        if item and item.data() in self.added_node_list:
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

        self.server = None
        self._new_nodes = []  # the added nodes we will save
        self._current_path = None
        self._modified = False
        self._copy_clipboard = None

        self.tree_ui = TreeWidget(self.ui.treeView)
        self.tree_ui.error.connect(self.show_error)
        delegate = BoldDelegate(self, self.tree_ui.model, self._new_nodes)
        self.ui.treeView.setItemDelegate(delegate)

        self.refs_ui = RefsWidget(self.ui.refView)
        self.refs_ui.error.connect(self.show_error)
        self.attrs_ui = AttrsWidget(self.ui.attrView, show_timestamps=False)
        self.attrs_ui.error.connect(self.show_error)
        self.attrs_ui.modified.connect(self.set_modified)
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
        self.ui.actionImport.triggered.connect(self._import)
        self.ui.actionSave.triggered.connect(self._save)
        self.ui.actionSaveAs.triggered.connect(self._save_as)
        self.ui.actionCloseModel.triggered.connect(self._close_model)
        self.ui.actionAddObjectType.triggered.connect(self._add_object_type)
        self.ui.actionAddObject.triggered.connect(self._add_object)
        self.ui.actionAddFolder.triggered.connect(self._add_folder)
        self.ui.actionAddMethod.triggered.connect(self._add_method)
        self.ui.actionAddDataType.triggered.connect(self._add_data_type)
        self.ui.actionAddVariable.triggered.connect(self._add_variable)
        self.ui.actionAddVariableType.triggered.connect(self._add_variable_type)
        self.ui.actionAddProperty.triggered.connect(self._add_property)

        self._disable_actions()

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
        idx = self.ui.treeView.currentIndex()
        if idx.isValid():
            self._contextMenu.exec_(self.ui.treeView.viewport().mapToGlobal(position))

    def _delete(self):
        node = self.tree_ui.get_current_node()
        if node:
            nodes = get_node_children(node)
            for n in nodes:
                n.delete()
                if n in self._new_nodes:
                    self._new_nodes.remove(n)
            self.tree_ui.remove_current_item()

    def _copy(self):
        node = self.tree_ui.get_current_node()
        if node:
            self._copy_clipboard = node

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

    def set_modified(self):
        self._modified = True

    def _restore_state(self):
        self.resize(int(self.settings.value("main_window_width", 800)),
                    int(self.settings.value("main_window_height", 600)))
        #self.restoreState(self.settings.value("main_window_state", b"", type="QByteArray"))
        self.restoreState(self.settings.value("main_window_state", bytearray()))
        self.ui.splitterLeft.restoreState(self.settings.value("splitter_left", bytearray()))
        self.ui.splitterRight.restoreState(self.settings.value("splitter_right", bytearray()))
        self.ui.splitterCenter.restoreState(self.settings.value("splitter_center", bytearray()))

    def _disable_actions(self):
        self.ui.actionImport.setEnabled(False)
        self.ui.actionSave.setEnabled(False)
        self.ui.actionSaveAs.setEnabled(False)
        self.ui.actionAddObject.setEnabled(False)
        self.ui.actionAddFolder.setEnabled(False)
        self.ui.actionAddVariable.setEnabled(False)
        self.ui.actionAddProperty.setEnabled(False)
        self.ui.actionAddDataType.setEnabled(False)
        self.ui.actionAddVariableType.setEnabled(False)
        self.ui.actionAddObjectType.setEnabled(False)

    def _enable_actions(self):
        self.ui.actionImport.setEnabled(True)
        self.ui.actionSave.setEnabled(True)
        self.ui.actionSaveAs.setEnabled(True)
        self.ui.actionAddObject.setEnabled(True)
        self.ui.actionAddFolder.setEnabled(True)
        self.ui.actionAddVariable.setEnabled(True)
        self.ui.actionAddProperty.setEnabled(True)
        self.ui.actionAddDataType.setEnabled(True)
        self.ui.actionAddVariableType.setEnabled(True)
        self.ui.actionAddObjectType.setEnabled(True)

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
        self._update_title()
        if self.server is not None:
            self.server.stop()
        self.server = None
        return True

    def _update_title(self):
        self.setWindowTitle("FreeOpcUa Modeler " + str(self._current_path))

    def _new(self):
        if not self._close_model():
            return
        self.server = Server()
        endpoint = "opc.tcp://0.0.0.0:48400/freeopcua/uamodeler/"
        print("Starting server on ", endpoint)
        self.server.set_endpoint(endpoint)
        self.server.set_server_name("OpcUa Modeler Server")
        # now remove freeopcua namespace, not necessary when modeling and
        # ensures correct idx for exported nodesets
        ns_node = self.server.get_node(ua.NodeId(ua.ObjectIds.Server_NamespaceArray))
        nss = ns_node.get_value()
        ns_node.set_value(nss[1:])

        del(self._new_nodes[:])  # empty list while keeping reference

        self.server.start()
        self.tree_ui.set_root_node(self.server.get_root_node())
        self.idx_ui.set_node(self.server.get_node(ua.ObjectIds.Server_NamespaceArray))
        self.nodesets_ui.set_server(self.server)
        self._modified = False
        self._enable_actions()
        self._current_path = "NoName"
        self._update_title()
        return True

    def _import(self):
        path, ok = QFileDialog.getOpenFileName(self, caption="Open OPC UA XML", filter="XML Files (*.xml *.XML)", directory=self._last_dir)
        if not ok:
            return None
        self._last_dir = os.path.dirname(path)
        try:
            new_nodes = self.server.import_xml(path)
            self._new_nodes.extend([self.server.get_node(node) for node in new_nodes])
            self._modified = True
        except Exception as ex:
            self.show_error(ex)
            raise
        # we maybe should only reload the imported nodes
        self.tree_ui.reload()
        self.idx_ui.reload()
        return path

    def _open(self):
        if self._new():
            path = self._import()
            if path:
                self._modified = False
                self._current_path = path
                self._update_title()
            else:
                self._close_model()

    def _save_as(self):
        path, ok = QFileDialog.getSaveFileName(self, caption="Save OPC UA XML", filter="XML Files (*.xml *.XML)")
        if ok:
            self._current_path = path
            self._update_title()
            self._save()

    def _save(self):
        if not self._current_path or self._current_path == "NoName":
            path, ok = QFileDialog.getSaveFileName(self, caption="Save OPC UA XML", filter="XML Files (*.xml *.XML)")
            self._current_path = path
            if not ok:
                return
        print("Saving to", self._current_path)
        print("Exporting  {} nodes: {}".format(len(self._new_nodes), self._new_nodes))
        print("and namespaces: ", self.server.get_namespace_array()[1:])
        exp = XmlExporter(self.server)
        uris = self.server.get_namespace_array()[1:]
        exp.build_etree(self._new_nodes, uris=uris)
        try:
            exp.write_xml(self._current_path)
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

    def _add_method(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewUaMethodDialog.getArgs(self, "Add Method", self.server)
        if ok:
            new_nodes = []
            new_node = parent.add_method(*args)
            new_nodes.append(new_node)
            new_nodes.extend(new_node.get_children())
            self._after_add(new_nodes)

    def _add_object_type(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewNodeBaseDialog.getArgs(self, "Add Object Type", self.server)
        if ok:
            new_node = parent.add_object_type(*args)
            self._after_add(new_node)

    def _add_folder(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewNodeBaseDialog.getArgs(self, "Add Folder", self.server)
        if ok:
            new_node = parent.add_folder(*args)
            self._after_add(new_node)

    def _add_object(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewUaObjectDialog.getArgs(self, "Add Object", self.server, base_node_type=self.server.get_node(ua.ObjectIds.BaseObjectType))
        if ok:
            nodeid, bname, otype = args
            new_nodes = instantiate(parent, otype, bname=bname, nodeid=nodeid)
            self._after_add(new_nodes)

    def _add_data_type(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewNodeBaseDialog.getArgs(self, "Add Data Type", self.server)
        if ok:
            new_node = parent.add_data_type(*args)
            self._after_add(new_node)

    def _add_variable(self):
        parent = self.tree_ui.get_current_node()
        try:
            args, ok = NewUaVariableDialog.getArgs(self, "Add Variable", self.server, default_value=9.99)
        except Exception as ex:
            self.show_error(ex)
            raise
        if ok:
            new_node = parent.add_variable(*args)
            self._after_add(new_node)

    def _add_property(self):
        parent = self.tree_ui.get_current_node()
        try:
            args, ok = NewUaVariableDialog.getArgs(self, "Add Property", self.server, default_value=9.99)
        except Exception as ex:
            self.show_error(ex)
            raise
        if ok:
            new_node = parent.add_property(*args)
            self._after_add(new_node)

    def _add_variable_type(self):
        parent = self.tree_ui.get_current_node()
        args, ok = NewUaObjectDialog.getArgs(self, "Add Variable Type", self.server, base_node_type=self.server.get_node(ua.ObjectIds.BaseVariableType))
        if ok:
            nodeid, bname, datatype = args
            new_node = parent.add_variable_type(nodeid, bname, datatype.nodeid)
            print("NEW TYPE", new_node)
            self._after_add(new_node)

    def show_refs(self, idx=None):
        node = self.get_current_node(idx)
        self.refs_ui.show_refs(node)

    def show_attrs(self, idx=None):
        if not isinstance(idx, QModelIndex):
            idx = None
        node = self.get_current_node(idx)
        self.attrs_ui.show_attrs(node)

    def show_error(self, msg, level=1):
        print("showing error: ", msg, level)
        self.ui.statusBar.show()
        self.ui.statusBar.setStyleSheet("QStatusBar { background-color : red; color : black; }")
        self.ui.statusBar.showMessage(str(msg))
        QTimer.singleShot(1500, self.ui.statusBar.hide)

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
        if self.server:
            self.server.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    modeler = UaModeler()
    modeler.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
