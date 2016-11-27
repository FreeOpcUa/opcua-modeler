import logging

from PyQt5.QtCore import pyqtSignal, Qt, QObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QMenu, QAction, QStyledItemDelegate

from opcua import ua

from uawidgets.utils import trycatch


logger = logging.getLogger(__name__)


class NamespaceWidget(QObject):

    error = pyqtSignal(str)

    def __init__(self, view):
        QObject.__init__(self, view)
        self.view = view
        self.model = QStandardItemModel()
        self.view.setModel(self.model)
        delegate = MyDelegate(self.view, self)
        delegate.error.connect(self.error.emit)
        self.view.setItemDelegate(delegate)
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
        uries = self.node.get_value()
        newidx = len(uries)
        it = self.model.item(0, 0)
        uri_it = QStandardItem("")
        it.appendRow([QStandardItem(), QStandardItem(str(newidx)), uri_it])
        idx = self.model.indexFromItem(uri_it)
        self.view.edit(idx)

    def remove_namespace(self):
        uries = self.node.get_value()
        uries.remove(self._namespace_to_delete)
        self.logger.info("Writting namespace array: %s", uries)
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
        if idx.parent().isValid() and idx.row() >= 1:
            uri_it = self.model.itemFromIndex(idx.sibling(idx.row(), 2))
            self._namespace_to_delete = uri_it.text()
            self.removeNamespaceAction.setEnabled(True)
        self._contextMenu.exec_(self.view.viewport().mapToGlobal(position))


class MyDelegate(QStyledItemDelegate):

    error = pyqtSignal(Exception)
    attr_written = pyqtSignal(ua.AttributeIds, ua.DataValue)

    def __init__(self, parent, widget):
        QStyledItemDelegate.__init__(self, parent)
        self.widget = widget

    @trycatch
    def createEditor(self, parent, option, idx):
        """
        Called when editing starts, here can we override default editor,
        disable editing for some values, etc...
        """
        if idx.column() != 2 or idx.row() == 0:
            return None
        return QStyledItemDelegate.createEditor(self, parent, option, idx)

    @trycatch
    def setModelData(self, editor, model, idx):
        """
        Called when editor has finished editing data
        Here we call the default implementation and save our values
        """
        QStyledItemDelegate.setModelData(self, editor, model, idx)
        root = model.item(0, 0)
        uries = []
        count = 0
        while True:
            child = root.child(count, 2)
            count += 1
            if not child:
                break
            uries.append(child.text())
        self.logger.info("Writting namespace array: %s", uries)
        self.widget.node.set_value(uries)


