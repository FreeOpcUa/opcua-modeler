#! /usr/bin/env python3

import sys

from PyQt5.QtCore import QTimer, QSettings, QModelIndex, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QPushButton, QComboBox, QLabel, QLineEdit, QHBoxLayout, QDialog, QDialogButtonBox

from opcua import ua
from opcua import Server

from uawidgets import resources
from uawidgets.attrs_widget import AttrsWidget
from uawidgets.tree_widget import TreeWidget
from uawidgets.refs_widget import RefsWidget
from uawidgets.get_node_dialog import GetNodeDialog
from uamodeler.uamodeler_ui import Ui_UaModeler
from uamodeler.namespace_widget import NamespaceWidget


class NewNodeDialog(QDialog):
    def __init__(self, parent, title, server, node_type=None, default_value=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(title)

        layout = QHBoxLayout(self)
        
        self.nsComboBox = QComboBox(self)
        uries = server.get_namespace_array()
        for uri in uries:
            self.nsComboBox.addItem(uri)
        layout.addWidget(self.nsComboBox)

        self.nameLabel = QLineEdit(self)
        self.nameLabel.setText("NoName")
        layout.addWidget(self.nameLabel)

        self.start_node_type = node_type
        self.node_type = node_type
        self._is_variable = False

        if self.node_type is not None:
            name = self.node_type.get_browse_name().to_string()
            self.objectTypeButton = QPushButton(name, self)
            self.objectTypeButton.clicked.connect(self._get_node_type)
            layout.addWidget(self.objectTypeButton)
        
        if default_value is not None:
            self._is_variable = True
            self.valLineEdit = QLineEdit(self)
            self.valLineEdit.setText(str(default_value))
            layout.addWidget(self.valLineEdit)

            self.vtypeComboBox = QComboBox(self)
            vtypes = [vt.name for vt in ua.VariantType]
            for vtype in vtypes:
                self.vtypeComboBox.addItem(vtype)
            layout.addWidget(self.vtypeComboBox)

            self.original_data_type = server.get_node(ua.ObjectIds.BaseDataType)
            self.data_type = self.original_data_type 
            name = self.data_type.get_browse_name().to_string()
            self.dataTypeButton = QPushButton(name, self)
            self.dataTypeButton.clicked.connect(self._get_data_type)
            layout.addWidget(self.dataTypeButton)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def _get_data_type(self):
        node, ok = GetNodeDialog.getNode(self, self.original_data_type)
        if ok:
            self.node_type = node
            self.objectTypeButton.setText(node.get_browse_name().to_string())


    def _get_node_type(self):
        node, ok = GetNodeDialog.getNode(self, self.start_node_type)
        if ok:
            self.node_type = node
            self.objectTypeButton.setText(node.get_browse_name().to_string())

    def get_args(self):
        args = []
        ns = self.nsComboBox.currentIndex()
        args.append(ns)
        name = self.nameLabel.text()
        args.append(name)
        if self.node_type is not None:
            args.append(self.node_type)
        if self._is_variable is not None:
            args.append(self.valLineEdit.text())
            args.append(getattr(ua.VariantType, self.vtypeComboBox.currentText()))
            args.append(self.data_type.nodeid)
        return args

    @staticmethod
    def getArgs(parent, title, server, node_type=None, default_value=None):
        dialog = NewNodeDialog(parent, title, server, node_type=node_type, default_value=default_value)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            return dialog.get_args(), True
        else:
            return [], False


class UaModeler(QMainWindow):

    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_UaModeler()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon(":/network.svg"))

        # we only show statusbar in case of errors
        self.ui.statusBar.hide()

        # load settings, seconds arg is default
        self.settings = QSettings("FreeOpcUa", "OpcUaModeler")

        self.server = Server()
        self.server.set_endpoint("opc.tcp://0.0.0.0:48400/freeopcua/uamodeler/")
        self.server.set_server_name("OpcUa Modeler Server")

        self._new_nodes = []  # the added nodes we will save


        self.tree_ui = TreeWidget(self.ui.treeView)
        self.tree_ui.error.connect(self.show_error)
        self.refs_ui = RefsWidget(self.ui.refView)
        self.refs_ui.error.connect(self.show_error)
        self.attrs_ui = AttrsWidget(self.ui.attrView)
        self.attrs_ui.error.connect(self.show_error)
        self.idx_ui = NamespaceWidget(self.ui.namespaceView)

        self.ui.treeView.activated.connect(self.show_refs)
        self.ui.treeView.clicked.connect(self.show_refs)
        self.ui.treeView.activated.connect(self.show_attrs)
        self.ui.treeView.clicked.connect(self.show_attrs)


        self.resize(int(self.settings.value("main_window_width", 800)), int(self.settings.value("main_window_height", 600)))
        #self.restoreState(self.settings.value("main_window_state", b"", type="QByteArray"))
        self.restoreState(self.settings.value("main_window_state", b""))
       
        self.ui.splitterLeft.restoreState(self.settings.value("splitter_left", b""))
        self.ui.splitterRight.restoreState(self.settings.value("splitter_right", b""))
        self.ui.splitterCenter.restoreState(self.settings.value("splitter_center", b""))

        self.server.start()
        self.tree_ui.set_root_node(self.server.get_root_node())
        self.idx_ui.set_node(self.server.get_node(ua.ObjectIds.Server_NamespaceArray))

        # fix icon stuff
        self.ui.actionAddFolder.setIcon(QIcon(":/folder.svg"))
        self.ui.actionAddObject.setIcon(QIcon(":/object.svg"))
        self.ui.actionAddObjectType.setIcon(QIcon(":/object_type.svg"))
        self.ui.actionAddProperty.setIcon(QIcon(":/property.svg"))
        self.ui.actionAddVariable.setIcon(QIcon(":/variable.svg"))
        self.ui.actionAddVariableType.setIcon(QIcon(":/variable_type.svg"))

        # menu
        self.ui.treeView.addAction(self.ui.actionAddFolder)
        self.ui.treeView.addAction(self.ui.actionAddObject)
        self.ui.treeView.addAction(self.ui.actionAddVariable)
        self.ui.treeView.addAction(self.ui.actionAddProperty)
        self.ui.treeView.addAction(self.ui.actionAddObjectType)
        self.ui.treeView.addAction(self.ui.actionAddVariableType)
        self.ui.treeView.addAction(self.ui.actionAddDataType)

        # actions
        self.ui.actionOpen.triggered.connect(self._open)
        self.ui.actionSave.triggered.connect(self._save)
        self.ui.actionAddObjectType.triggered.connect(self._add_object_type)
        self.ui.actionAddObject.triggered.connect(self._add_object)
        self.ui.actionAddDataType.triggered.connect(self._add_data_type)
        self.ui.actionAddVariable.triggered.connect(self._add_variable)
        self.ui.actionAddProperty.triggered.connect(self._add_property)

    def _open(self):
        path = QFileDialog.getOpenFileName(self)
        f = open(path[0], 'r')
        xml = f.read()
        print("should read", xml)

    def _save(self):
        raise NotImplementedError

    def _add_node(self, func_name, node_type=None, default_value=None):
        node = self.tree_ui.get_current_node()
        if not node:
            self.show_error("No node selected")
            raise RuntimeError("No node selected")
        args, ok = NewNodeDialog.getArgs(self, func_name, self.server, node_type=node_type, default_value=default_value)
        print("ARGS are", args)
        if ok:
            new_node = getattr(node, func_name)(*args)
            self._new_nodes.append(new_node)
            self.tree_ui.reload_current()
            self.show_refs()

    def _add_object_type(self):
        return self._add_node("add_object_type")

    def _add_object(self):
        return self._add_node("add_object", node_type=self.server.get_node(ua.ObjectIds.BaseObjectType))

    def _add_data_type(self):
        return self._add_node("add_data_type")

    def _add_variable(self):
        return self._add_node("add_variable", default_value=9.99)

    def _add_property(self):
        return self._add_node("add_property", default_value=1.11)

    def show_refs(self, idx=None):
        node = self.get_current_node(idx)
        if node:
            self.refs_ui.show_refs(node)

    def show_attrs(self, idx=None):
        if not isinstance(idx, QModelIndex):
            idx = None
        node = self.get_current_node(idx)
        if node:
            self.attrs_ui.show_attrs(node)

    def show_error(self, msg, level=1):
        print("showing error: ", msg, level)
        self.ui.statusBar.show()
        self.ui.statusBar.setStyleSheet("QStatusBar { background-color : red; color : black; }")
        self.ui.statusBar.showMessage(str(msg))
        QTimer.singleShot(1500, self.ui.statusBar.hide)

    def get_current_node(self, idx=None):
        return self.tree_ui.get_current_node(idx)

    def closeEvent(self, event):
        self.settings.setValue("main_window_width", self.size().width())
        self.settings.setValue("main_window_height", self.size().height())
        self.settings.setValue("main_window_state", self.saveState())
        self.settings.setValue("splitter_left", self.ui.splitterLeft.saveState())
        self.settings.setValue("splitter_right", self.ui.splitterRight.saveState())
        self.settings.setValue("splitter_center", self.ui.splitterCenter.saveState())
        self.server.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    modeler = UaModeler()
    modeler.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
