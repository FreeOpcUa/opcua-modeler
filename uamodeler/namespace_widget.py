from PyQt5.QtCore import pyqtSignal, Qt, QObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QApplication, QMenu, QAction

from opcua import ua


class NamespaceWidget(QObject):

    error = pyqtSignal(str)

    def __init__(self, view):
        QObject.__init__(self, view)
        self.view = view
        self.model = QStandardItemModel()
        self.view.setModel(self.model)
        self.node = None
        self.view.header().setSectionResizeMode(1)
        
        addNamespaceAction = QAction("Add Namespace", self.model)
        removeNamespaceAction = QAction("Remove Namespace", self.model)

        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.showContextMenu)
        self._contextMenu = QMenu()
        self._contextMenu.addAction(addNamespaceAction)
        self._contextMenu.addAction(removeNamespaceAction)

    def set_node(self, node):
        self.node = node
        self.show_array()

    def show_array(self):
        self.model.setHorizontalHeaderLabels(['Browse Name', 'Index', 'Value'])

        name_item = QStandardItem(self.node.get_browse_name().Name)
        self.model.appendRow([name_item, QStandardItem(""), QStandardItem()])
        it = self.model.item(0, 0)
        val = self.node.get_value()
        for idx, url in enumerate(val):
            it.appendRow([QStandardItem(), QStandardItem(url), QStandardItem(str(idx))])

    def clear(self):
        self.model.clear()

    def showContextMenu(self, position):
        item = self.get_current_item()
        if item:
            self._contextMenu.exec_(self.view.mapToGlobal(position))

    def get_current_item(self, col_idx=0):
        idx = self.view.currentIndex()
        return self.model.item(idx.row(), col_idx)



