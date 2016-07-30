#! /usr/bin/env python3

import sys
from datetime import datetime
from enum import Enum

from PyQt5.QtCore import pyqtSignal, QTimer, Qt, QObject, QSettings, QModelIndex, QMimeData
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt5.QtWidgets import QMainWindow, QWidget, QApplication, QAbstractItemView, QMenu, QAction

from opcua import ua
from opcua import Server

from uamodeler.uamodeler_ui import Ui_UaModeler
from uawidgets import resources
from uawidgets.attrs_widget import AttrsWidget
from uawidgets.tree_widget import TreeWidget
from uawidgets.refs_widget import RefsWidget


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


        self.tree_ui = TreeWidget(self.ui.treeView)
        self.tree_ui.error.connect(self.show_error)
        self.refs_ui = RefsWidget(self.ui.refView)
        self.refs_ui.error.connect(self.show_error)
        self.attrs_ui = AttrsWidget(self.ui.attrView)
        self.attrs_ui.error.connect(self.show_error)

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
        self.tree_ui.start(self.server)


        # menu
        self.ui.treeView.addAction(self.ui.actionAddFolder)
        self.ui.treeView.addAction(self.ui.actionAddObject)
        self.ui.treeView.addAction(self.ui.actionAddVariable)
        self.ui.treeView.addAction(self.ui.actionAddProperty)
        self.ui.treeView.addAction(self.ui.actionAddObjectType)
        self.ui.treeView.addAction(self.ui.actionAddVariableType)
        self.ui.treeView.addAction(self.ui.actionAddDataType)

    def show_refs(self, idx):
        node = self.get_current_node(idx)
        if node:
            self.refs_ui.show_refs(node)

    def show_attrs(self, idx):
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
