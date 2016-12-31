#! /usr/bin/env python3

import sys
import os
import logging

from PyQt5.QtCore import QTimer, QSettings, QModelIndex, Qt, QCoreApplication
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox, QStyledItemDelegate, QMenu

from opcua import ua

from uawidgets import resources
from uawidgets.attrs_widget import AttrsWidget
from uawidgets.tree_widget import TreeWidget
from uawidgets.refs_widget import RefsWidget
from uawidgets.new_node_dialogs import NewNodeBaseDialog, NewUaObjectDialog, NewUaVariableDialog, NewUaMethodDialog
from uawidgets.utils import trycatchslot
from uawidgets.logger import QtHandler

from uamodeler.uamodeler_ui import Ui_UaModeler
from uamodeler.namespace_widget import NamespaceWidget
from uamodeler.refnodesets_widget import RefNodeSetsWidget
from uamodeler.model_manager import ModelManager


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
        self._copy_clipboard = None

        self.tree_ui = TreeWidget(self.ui.treeView)
        self.tree_ui.error.connect(self.show_error)

        self.refs_ui = RefsWidget(self.ui.refView)
        self.refs_ui.error.connect(self.show_error)
        self.attrs_ui = AttrsWidget(self.ui.attrView, show_timestamps=False)
        self.attrs_ui.error.connect(self.show_error)
        self.idx_ui = NamespaceWidget(self.ui.namespaceView)
        self.nodesets_ui = RefNodeSetsWidget(self.ui.refNodeSetsView)
        self.nodesets_ui.error.connect(self.show_error)
        self.nodesets_ui.nodeset_added.connect(self.nodesets_change)
        self.nodesets_ui.nodeset_removed.connect(self.nodesets_change)

        self.ui.treeView.activated.connect(self.show_refs)
        self.ui.treeView.clicked.connect(self.show_refs)
        self.ui.treeView.activated.connect(self.show_attrs)
        self.ui.treeView.clicked.connect(self.show_attrs)

        self.model_mgr = ModelManager(self)
        delegate = BoldDelegate(self, self.tree_ui.model, self.model_mgr.new_nodes)
        self.ui.treeView.setItemDelegate(delegate)
        self.ui.treeView.selectionModel().currentChanged.connect(self._update_actions_state)

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

        self.disable_actions()

    def get_current_server(self):
        return self.model_mgr.server_mgr

    def _update_actions_state(self, current, previous):
        self.disable_add_actions()
        node = self.tree_ui.get_current_node(current)
        if not node or node in (self.model_mgr.server_mgr.nodes.root, 
                                self.model_mgr.server_mgr.nodes.types, 
                                self.model_mgr.server_mgr.nodes.event_types, 
                                self.model_mgr.server_mgr.nodes.object_types, 
                                self.model_mgr.server_mgr.nodes.reference_types, 
                                self.model_mgr.server_mgr.nodes.variable_types, 
                                self.model_mgr.server_mgr.nodes.data_types):
            return
        path = node.get_path()
        nodeclass = node.get_node_class()

        self.ui.actionAddFolder.setEnabled(True)
        self.ui.actionCopy.setEnabled(True)
        self.ui.actionPaste.setEnabled(True)
        self.ui.actionDelete.setEnabled(True)

        if self.model_mgr.server_mgr.nodes.base_object_type in path:
            self.ui.actionAddObjectType.setEnabled(True)

        if self.model_mgr.server_mgr.nodes.base_variable_type in path:
            self.ui.actionAddVariableType.setEnabled(True)

        if self.model_mgr.server_mgr.nodes.base_data_type in path:
            self.ui.actionAddDataType.setEnabled(True)
            if self.model_mgr.server_mgr.nodes.enum_data_type in path:
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
    def _new(self):
        if not self._close_model():
            return
        self.model_mgr.new_model()

    @trycatchslot
    def _delete(self):
        node = self.tree_ui.get_current_node()
        self.model_mgr.delete_node(node)

    @trycatchslot
    def _copy(self):
        node = self.tree_ui.get_current_node()
        if node:
            self._copy_clipboard = node

    @trycatchslot
    def _paste(self):
        if self._copy_clipboard:
            self.model_mgr.paste_node(self._copy_clipboard)

    @trycatchslot
    def _close_model_slot(self):
        self._close_model()

    def _close_model(self):
        if not self.really_exit():
            return False
        self.model_mgr.close_model()
        return True

    def _get_xml(self):
        path, ok = QFileDialog.getOpenFileName(self, caption="Open OPC UA XML", filter="XML Files (*.xml *.XML)", directory=self._last_dir)
        if ok:
            self._last_dir = os.path.dirname(path)
        return path, ok

    @trycatchslot
    def _open(self):
        if not self._close_model():
            return
        path, ok = self._get_xml()
        if not ok:
            return
        self.modee_mgr.open_model(path)

    @trycatchslot
    def _import_slot(self):
        path, ok = self._get_xml()
        if not ok:
            return None
        self.model_mgr.import_xml(path)

    @trycatchslot
    def _save_as_slot(self):
        self._save_as()

    def _save_as(self):
        path, ok = QFileDialog.getSaveFileName(self, caption="Save OPC UA XML", filter="XML Files (*.xml *.XML)")
        if ok:
            if os.path.isfile(path):
                reply = QMessageBox.question(
                    self,
                    "OPC UA Modeler",
                    "File already exit, do you really want to save to this file?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                if reply != QMessageBox.Yes:
                    return
            self.model_mgr.save_model(path)

    @trycatchslot
    def _save_slot(self):
        if not self.model_mgr.current_path:
            self.save_as(self)
        else:
            self.model_mgr.save_model()

    def _restore_state(self):
        self.resize(int(self.settings.value("main_window_width", 800)),
                    int(self.settings.value("main_window_height", 600)))
        #self.restoreState(self.settings.value("main_window_state", b"", type="QByteArray"))
        self.restoreState(self.settings.value("main_window_state", bytearray()))
        self.ui.splitterLeft.restoreState(self.settings.value("splitter_left", bytearray()))
        self.ui.splitterRight.restoreState(self.settings.value("splitter_right", bytearray()))
        self.ui.splitterCenter.restoreState(self.settings.value("splitter_center", bytearray()))

    def disable_model_actions(self):
        self.ui.actionImport.setEnabled(False)
        self.ui.actionSave.setEnabled(False)
        self.ui.actionSaveAs.setEnabled(False)

    def disable_actions(self):
        self.disable_add_actions()
        self.disable_model_actions()

    def disable_add_actions(self):
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

    def enable_model_actions(self):
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

    def update_title(self, path):
        self.setWindowTitle("FreeOpcUa Modeler " + str(path))

    def really_exit(self):
        if self.model_mgr.modified:
            reply = QMessageBox.question(
                self,
                "OPC UA Modeler",
                "Model is modified, do you really want to close model?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply != QMessageBox.Yes:
                return False

        return True

    @trycatchslot
    def _add_method(self):
        args, ok = NewUaMethodDialog.getArgs(self, "Add Method", self.model_mgr.server_mgr)
        if ok:
            self.model_mgr.add_method(args)

    @trycatchslot
    def _add_object_type(self):
        args, ok = NewNodeBaseDialog.getArgs(self, "Add Object Type", self.model_mgr.server_mgr)
        if ok:
            self.model_mgr.add_object_type(args)

    @trycatchslot
    def _add_folder(self):
        args, ok = NewNodeBaseDialog.getArgs(self, "Add Folder", self.model_mgr.server_mgr)
        if ok:
            self.model_mgr.add_folder(args)

    @trycatchslot
    def _add_object(self):
        args, ok = NewUaObjectDialog.getArgs(self, "Add Object", self.model_mgr.server_mgr, base_node_type=self.model_mgr.server_mgr.nodes.base_object_type)
        if ok:
            self.model_mgr.add_object(args)

    @trycatchslot
    def _add_data_type(self):
        args, ok = NewNodeBaseDialog.getArgs(self, "Add Data Type", self.model_mgr.server_mgr)
        if ok:
            self.model_mgr.add_data_type(args)
    
    @trycatchslot
    def _add_variable(self):
        dtype = self.settings.value("last_datatype", None)
        args, ok = NewUaVariableDialog.getArgs(self, "Add Variable", self.model_mgr.server_mgr, default_value=9.99, dtype=dtype)
        if ok:
            self.model_mgr.add_variable(args)
            self.settings.setValue("last_datatype", args[4])

    @trycatchslot
    def _add_property(self):
        dtype = self.settings.value("last_datatype", None)
        args, ok = NewUaVariableDialog.getArgs(self, "Add Property", self.model_mgr.server_mgr, default_value=9.99, dtype=dtype)
        if ok:
            self.model_mgr.add_property(args)

    @trycatchslot
    def _add_variable_type(self):
        args, ok = NewUaObjectDialog.getArgs(self, "Add Variable Type", self.model_mgr.server_mgr, base_node_type=self.model_mgr.server_mgr.get_node(ua.ObjectIds.BaseVariableType))
        if ok:
            self.model_mgr.add_variable_type(args)

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
        if not self.model_mgr.close_model():
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
        self.model_mgr.server_mgr.close()
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
