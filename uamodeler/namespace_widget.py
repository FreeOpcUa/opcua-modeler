from PyQt5.QtCore import pyqtSignal, Qt, QObject, QModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QMenu, QAction, QInputDialog

from opcua import ua


class NamespaceWidget(QObject):

    error = pyqtSignal(str)

    def __init__(self, view):
        QObject.__init__(self, view)
        self.view = view
        self.model = QStandardItemModel()
        self.view.setModel(self.model)
        self.node = None
        self._namespace_to_delete = None
        self.view.header().setSectionResizeMode(1)
        
        addNamespaceAction = QAction("Add Namespace", self.model)
        addNamespaceAction.triggered.connect(self.add_namespace)
        self.removeNamespaceAction = QAction("Remove Namespace", self.model)
        self.removeNamespaceAction.triggered.connect(self.remove_namespace)

        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.showContextMenu)
        self._contextMenu = QMenu()
        self._contextMenu.addAction(addNamespaceAction)
        self._contextMenu.addAction(self.removeNamespaceAction)

    def add_namespace(self):
        uri, ok = QInputDialog.getText(self.view, "Enter new namespace URI", "URI:")
        uries = self.node.get_value()
        if uri in uries:
            return uries.index(uri)
        uries.append(uri)
        self.node.set_value(uries)
        self.reload()
        #it = self.model.item(0, 0)
        #it.appendRow([QStandardItem(), QStandardItem(str(len(uries)+1)), QStandardItem(uri)])

    def remove_namespace(self):
        uries = self.node.get_value()
        uries.remove(self._namespace_to_delete)
        self.node.set_value(uries)
        self.reload()

    def set_node(self, node):
        self.model.clear()
        self.node = node
        self.show_array()

    def reload(self):
        self.set_node(self.node)

    def show_array(self):
        self.model.setHorizontalHeaderLabels(['Browse Name', 'Index', 'Value'])

        name_item = QStandardItem(self.node.get_browse_name().Name)
        self.model.appendRow([name_item, QStandardItem(""), QStandardItem()])
        it = self.model.item(0, 0)
        val = self.node.get_value()
        for idx, url in enumerate(val):
            it.appendRow([QStandardItem(), QStandardItem(str(idx)), QStandardItem(url)])
        self.view.expandAll()

    def clear(self):
        self.model.clear()

    def showContextMenu(self, position):
        self.removeNamespaceAction.setEnabled(False)
        idx = self.view.currentIndex()
        if not idx.isValid():
            return
        if idx.parent().isValid() and idx.row() > 1:
            uri_it = self.model.itemFromIndex(idx.sibling(idx.row(), 2))
            self._namespace_to_delete = uri_it.text()
            self.removeNamespaceAction.setEnabled(True)
        self._contextMenu.exec_(self.view.mapToGlobal(position))
