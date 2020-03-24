#! /usr/bin/env python3

import sys
import os
import logging

from PyQt5.QtCore import QTimer, QSettings, QModelIndex, Qt, QCoreApplication, QObject, pyqtSignal
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox, QStyledItemDelegate, QMenu, QAction


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


class ActionsManager:
    """
    Manage actions of Modeler
    """

    def __init__(self, window, ui, model_mgr):
        self.window = window
        self.ui = ui
        self.model_mgr = model_mgr

        self._fix_icons()
        # actions
        self.ui.actionNew.triggered.connect(self.model_mgr.new)
        self.ui.actionOpen.triggered.connect(self.model_mgr.open)
        self.ui.actionCopy.triggered.connect(self.model_mgr.copy)
        self.ui.actionQuit.triggered.connect(self.window.close)
        self.ui.actionPaste.triggered.connect(self.model_mgr.paste)
        self.ui.actionDelete.triggered.connect(self.model_mgr.delete)
        self.ui.actionImport.triggered.connect(self.model_mgr.import_xml)
        self.ui.actionSave.triggered.connect(self.model_mgr.save)
        self.ui.actionSaveAs.triggered.connect(self.model_mgr.save_as)
        self.ui.actionCloseModel.triggered.connect(self.model_mgr.close_model)
        self.ui.actionAddObjectType.triggered.connect(self.model_mgr.add_object_type)
        self.ui.actionAddObject.triggered.connect(self.model_mgr.add_object)
        self.ui.actionAddFolder.triggered.connect(self.model_mgr.add_folder)
        self.ui.actionAddMethod.triggered.connect(self.model_mgr.add_method)
        self.ui.actionAddDataType.triggered.connect(self.model_mgr.add_data_type)
        self.ui.actionAddVariable.triggered.connect(self.model_mgr.add_variable)
        self.ui.actionAddVariableType.triggered.connect(self.model_mgr.add_variable_type)
        self.ui.actionAddProperty.triggered.connect(self.model_mgr.add_property)

        self.disable_all_actions()

    def _fix_icons(self):
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

    def update_actions_states(self, node):
        self.disable_add_actions()
        if not node or node in (self.model_mgr.get_current_server().nodes.root,
                                self.model_mgr.get_current_server().nodes.types,
                                self.model_mgr.get_current_server().nodes.event_types,
                                self.model_mgr.get_current_server().nodes.object_types,
                                self.model_mgr.get_current_server().nodes.reference_types,
                                self.model_mgr.get_current_server().nodes.variable_types,
                                self.model_mgr.get_current_server().nodes.data_types):
            return
        path = node.get_path()
        nodeclass = node.get_node_class()
        typedefinition = node.get_type_definition()

        self.ui.actionCopy.setEnabled(True)
        self.ui.actionDelete.setEnabled(True)

        if typedefinition == ua.NodeId(ua.ObjectIds.PropertyType):
            return

        if nodeclass == ua.NodeClass.Variable:
            self.ui.actionAddVariable.setEnabled(True)
            self.ui.actionAddProperty.setEnabled(True)
            return

        self.ui.actionPaste.setEnabled(True)

        if self.model_mgr.get_current_server().nodes.base_object_type in path:
            self.ui.actionAddObjectType.setEnabled(True)

        if self.model_mgr.get_current_server().nodes.base_variable_type in path:
            self.ui.actionAddVariableType.setEnabled(True)

        if self.model_mgr.get_current_server().nodes.base_data_type in path:
            self.ui.actionAddDataType.setEnabled(True)
            if self.model_mgr.get_current_server().nodes.enum_data_type in path:
                self.ui.actionAddProperty.setEnabled(True)
            elif self.model_mgr.get_current_server().nodes.base_structure_type in path:
                self.ui.actionAddVariable.setEnabled(True)
            return  # not other nodes should be added here

        self.ui.actionAddFolder.setEnabled(True)
        self.ui.actionAddObject.setEnabled(True)
        self.ui.actionAddVariable.setEnabled(True)
        self.ui.actionAddProperty.setEnabled(True)
        self.ui.actionAddMethod.setEnabled(True)

    def disable_model_actions(self):
        self.ui.actionImport.setEnabled(False)
        self.ui.actionSave.setEnabled(False)
        self.ui.actionSaveAs.setEnabled(False)

    def disable_all_actions(self):
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


class ModelManagerUI(QObject):
    """
    Interface to ModelMgr that displays dialogs to interact with users.
    Logic is inside ModelManager, this class only handle the UI and dialogs
    """

    error = pyqtSignal(Exception)
    titleChanged = pyqtSignal(str)

    def __init__(self, modeler):
        QObject.__init__(self)
        self.modeler = modeler
        self._model_mgr = ModelManager(modeler)
        self._model_mgr.error.connect(self.error)
        self._model_mgr.titleChanged.connect(self.titleChanged)
        self.settings = QSettings()
        self._last_model_dir = self.settings.value("last_model_dir", ".")
        self._copy_clipboard = None

    def get_current_server(self):
        return self._model_mgr.server_mgr

    def get_new_nodes(self):
        return self._model_mgr.new_nodes

    def setModified(self, val=True):
        self._model_mgr.modified = val

    @trycatchslot
    def new(self):
        if not self.try_close_model():
            return
        self._model_mgr.new_model()

    @trycatchslot
    def delete(self):
        node = self.modeler.get_current_node()
        self._model_mgr.delete_node(node)

    @trycatchslot
    def copy(self):
        node = self.modeler.get_current_node()
        if node:
            self._copy_clipboard = node

    @trycatchslot
    def paste(self):
        if self._copy_clipboard:
            self._model_mgr.paste_node(self._copy_clipboard)

    @trycatchslot
    def close_model(self):
        self.try_close_model()

    def try_close_model(self):
        if self._model_mgr.modified:
            reply = QMessageBox.question(
                self.modeler,
                "OPC UA Modeler",
                "Model is modified, do you really want to close model?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply != QMessageBox.Yes:
                return False
        self._model_mgr.close_model(force=True)
        return True

    @trycatchslot
    def open(self):
        if not self.try_close_model():
            return
        path, ok = QFileDialog.getOpenFileName(self.modeler, caption="Open OPC UA XML", filter="XML Files (*.xml *.XML *.uamodel)", directory=self._last_model_dir)
        if not ok:
            return
        if self._last_model_dir != os.path.dirname(path):
            self._last_model_dir = os.path.dirname(path)
            self.settings.setValue("last_model_dir", self._last_model_dir)
        self._model_mgr.open(path)
        self.modeler.update_recent_files(path)

    def open_file(self, path):
        self._model_mgr.open(path)

    @trycatchslot
    def import_xml(self):
        last_import_dir = self.settings.value("last_import_dir", ".")
        path, ok = QFileDialog.getOpenFileName(self.modeler, caption="Import reference OPC UA XML", filter="XML Files (*.xml *.XML)", directory=last_import_dir)
        if not ok:
            return
        self.settings.setValue("last_import_dir", last_import_dir)
        self._model_mgr.import_xml(path)

    @trycatchslot
    def save_as(self):
        self._save_as()

    def _save_as(self):
        path, ok = QFileDialog.getSaveFileName(self.modeler, caption="Save OPC UA XML", filter="XML Files (*.xml *.XML)")
        if ok:
            print("PATH", path)
            if self._last_model_dir != os.path.dirname(path):
                self._last_model_dir = os.path.dirname(path)
                self.settings.setValue("last_model_dir", self._last_model_dir)
            self._model_mgr.save_xml(path)
            path = self._model_mgr.save_ua_model(path)
            self.modeler.update_recent_files(path)

    @trycatchslot
    def save(self):
        if not self._model_mgr.current_path:
            self.save_as()
        else:
            self._model_mgr.save_xml()
            self._model_mgr.save_ua_model()

    @trycatchslot
    def add_method(self):
        args, ok = NewUaMethodDialog.getArgs(self.modeler, "Add Method", self._model_mgr.server_mgr)
        if ok:
            nodes = self._model_mgr.add_method(*args)
            print("ADDED", [c.get_browse_name() for c in nodes])
            self._add_modelling_rule(nodes)

    @trycatchslot
    def add_object_type(self):
        args, ok = NewNodeBaseDialog.getArgs(self.modeler, "Add Object Type", self._model_mgr.server_mgr)
        if ok:
            self._model_mgr.add_object_type(*args)

    @trycatchslot
    def add_folder(self):
        args, ok = NewNodeBaseDialog.getArgs(self.modeler, "Add Folder", self._model_mgr.server_mgr)
        if ok:
            node = self._model_mgr.add_folder(*args)
            self._add_modelling_rule(node)

    @trycatchslot
    def add_object(self):
        args, ok = NewUaObjectDialog.getArgs(self.modeler, "Add Object", self._model_mgr.server_mgr, base_node_type=self._model_mgr.server_mgr.nodes.base_object_type)
        if ok:
            nodes = self._model_mgr.add_object(*args)
            # FIXME: in this particular case we may want to navigate recursively to add ref
            self._add_modelling_rule(nodes)

    def _add_modelling_rule(self, nodes):
        if not isinstance(nodes, (list, tuple)):
            nodes = [nodes]
        for node in nodes:
            path = node.get_path()
            if self._model_mgr.server_mgr.nodes.base_object_type in path:
                # we are creating a new type, add modeling rule
                node.set_modelling_rule(True)

    @trycatchslot
    def add_data_type(self):
        args, ok = NewNodeBaseDialog.getArgs(self.modeler, "Add Data Type", self._model_mgr.server_mgr)
        if ok:
            self._model_mgr.add_data_type(*args)

    @trycatchslot
    def add_variable(self):
        args, ok = NewUaVariableDialog.getArgs(self.modeler, "Add Variable", self._model_mgr.server_mgr)
        if ok:
            node = self._model_mgr.add_variable(*args)
            self._add_modelling_rule(node)

    @trycatchslot
    def add_property(self):
        args, ok = NewUaVariableDialog.getArgs(self.modeler, "Add Property", self._model_mgr.server_mgr)
        if ok:
            node = self._model_mgr.add_property(*args)
            self._add_modelling_rule(node)

    @trycatchslot
    def add_variable_type(self):
        args, ok = NewUaObjectDialog.getArgs(self.modeler, "Add Variable Type", self._model_mgr.server_mgr, base_node_type=self._model_mgr.server_mgr.get_node(ua.ObjectIds.BaseVariableType))
        if ok:
            self._model_mgr.add_variable_type(*args)


class UaModeler(QMainWindow):
    """
    Main class of modeler. Should be as simple as possible, try to push things to other classes
    or even better python-opcua
    """

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

        self._restore_ui_geometri()

        self.tree_ui = TreeWidget(self.ui.treeView)
        self.tree_ui.error.connect(self.show_error)

        self.refs_ui = RefsWidget(self.ui.refView)
        self.refs_ui.error.connect(self.show_error)
        self.refs_ui.reference_changed.connect(self.tree_ui.reload_current)  # FIXME: shoudl reload a specific node
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

        self.model_mgr = ModelManagerUI(self)
        self.model_mgr.error.connect(self.show_error)
        self.model_mgr.titleChanged.connect(self.update_title)
        self.actions = ActionsManager(self, self.ui, self.model_mgr)

        self.setup_context_menu_tree()

        delegate = BoldDelegate(self, self.tree_ui.model, self.model_mgr.get_new_nodes())
        self.ui.treeView.setItemDelegate(delegate)
        self.ui.treeView.selectionModel().currentChanged.connect(self._update_actions_state)

        self._recent_files = self.settings.value("recent_files", [])
        self._recent_files_max_count = int(self.settings.value("recent_files_max_count", 10))
        self._recent_files_acts = [QAction(self, visible=False, triggered=self.open_recent_files) for _ in range(self._recent_files_max_count)]
        for act in self._recent_files_acts:
            self.ui.menuRecentFiles.addAction(act)
        self._update_recent_files_ui()

    def open_recent_files(self):
        if not self.model_mgr.try_close_model():
            return
        action = self.sender()
        if action:
            path = action.data()
            self.model_mgr.open_file(path)
            self.update_recent_files(path)

    def update_recent_files(self, path):
        if self._recent_files and path == self._recent_files[0]:
            return
        if self._recent_files is not None:
            if path in self._recent_files:
                self._recent_files.remove(path)
            self._recent_files.insert(0, path)
            self._recent_files = self._recent_files[:self._recent_files_max_count]
            self._update_recent_files_ui()

    def _update_recent_files_ui(self):
        if self._recent_files is not None:
            for idx, path in enumerate(self._recent_files):
                self._recent_files_acts[idx].setText(path)
                self._recent_files_acts[idx].setData(path)
                self._recent_files_acts[idx].setVisible(True)

    def get_current_node(self, idx=None):
        return self.tree_ui.get_current_node(idx)

    def get_current_server(self):
        """
        Used by tests
        """
        return self.model_mgr.get_current_server()

    def clear_all_widgets(self):
        self.tree_ui.clear()
        self.refs_ui.clear()
        self.attrs_ui.clear()
        self.idx_ui.clear()
        self.nodesets_ui.clear()

    @trycatchslot
    def _update_actions_state(self, current, previous):
        node = self.get_current_node(current)
        self.actions.update_actions_states(node)

    def setup_context_menu_tree(self):
        self.ui.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeView.customContextMenuRequested.connect(self._show_context_menu_tree)
        self._contextMenu = QMenu()

        # tree view menu
        self._contextMenu.addAction(self.ui.actionCopy)
        self._contextMenu.addAction(self.ui.actionPaste)
        self._contextMenu.addAction(self.ui.actionDelete)
        self._contextMenu.addSeparator()
        self._contextMenu.addAction(self.tree_ui.actionReload)
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

    def _restore_ui_geometri(self):
        self.resize(int(self.settings.value("main_window_width", 800)),
                    int(self.settings.value("main_window_height", 600)))
        #self.restoreState(self.settings.value("main_window_state", b"", type="QByteArray"))
        self.restoreState(self.settings.value("main_window_state", bytearray()))
        self.ui.splitterLeft.restoreState(self.settings.value("splitter_left", bytearray()))
        self.ui.splitterRight.restoreState(self.settings.value("splitter_right", bytearray()))
        self.ui.splitterCenter.restoreState(self.settings.value("splitter_center", bytearray()))

    def update_title(self, path):
        self.setWindowTitle("FreeOpcUa Modeler " + str(path))

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

    @trycatchslot
    def show_refs(self, idx=None):
        node = self.get_current_node(idx)
        if node:
            self.refs_ui.show_refs(node)

    @trycatchslot
    def show_attrs(self, idx=None):
        if not isinstance(idx, QModelIndex):
            idx = None
        node = self.get_current_node(idx)
        if node:
            self.attrs_ui.show_attrs(node)

    def nodesets_change(self, data):
        self.idx_ui.reload()
        self.tree_ui.reload()
        self.refs_ui.clear()
        self.attrs_ui.clear()
        self.model_mgr.setModified(True)

    def closeEvent(self, event):
        if not self.model_mgr.try_close_model():
            event.ignore()
            return
        self.attrs_ui.save_state()
        self.refs_ui.save_state()
        self.tree_ui.save_state()
        self.settings.setValue("main_window_width", self.size().width())
        self.settings.setValue("main_window_height", self.size().height())
        self.settings.setValue("main_window_state", self.saveState())
        self.settings.setValue("splitter_left", self.ui.splitterLeft.saveState())
        self.settings.setValue("splitter_right", self.ui.splitterRight.saveState())
        self.settings.setValue("splitter_center", self.ui.splitterCenter.saveState())
        self.settings.setValue("recent_files", self._recent_files)
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
