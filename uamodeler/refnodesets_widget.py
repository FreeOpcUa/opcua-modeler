import os

from PyQt5.QtCore import pyqtSignal, Qt, QObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QMenu, QAction, QFileDialog


from uawidgets.utils import trycatchslot


class RefNodeSetsWidget(QObject):

    error = pyqtSignal(Exception)
    nodeset_added = pyqtSignal(str)
    nodeset_removed = pyqtSignal(str)

    def __init__(self, view):
        QObject.__init__(self, view)
        self.view = view
        self.model = QStandardItemModel()
        self.view.setModel(self.model)
        self.nodesets = []
        self.server_mgr = None
        self.view.header().setSectionResizeMode(1)

        addNodeSetAction = QAction("Add Reference Node Set", self.model)
        addNodeSetAction.triggered.connect(self.add_nodeset)
        self.removeNodeSetAction = QAction("Remove Reference Node Set", self.model)
        self.removeNodeSetAction.triggered.connect(self.remove_nodeset)

        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.showContextMenu)
        self._contextMenu = QMenu()
        self._contextMenu.addAction(addNodeSetAction)
        self._contextMenu.addAction(self.removeNodeSetAction)

    @trycatchslot
    def add_nodeset(self):
        path, ok = QFileDialog.getOpenFileName(self.view, caption="Import OPC UA XML Node Set", filter="XML Files (*.xml *.XML)", directory=".")
        if not ok:
            return None
        self.import_nodeset(path)

    def import_nodeset(self, path):
        print("IMPORT", path)
        name = os.path.basename(path)
        if name in self.nodesets:
            return
        try:
            self.server_mgr.import_xml(path)
        except Exception as ex:
            self.error.emit(ex)
            raise

        item = QStandardItem(name)
        self.model.appendRow([item])
        self.nodesets.append(name)
        self.view.expandAll()
        self.nodeset_added.emit(path)

    @trycatchslot
    def remove_nodeset(self):
        idx = self.view.currentIndex()
        if not idx.isValid() or idx.row() == 0:
            return

        item = self.model.itemFromIndex(idx)
        name = item.text()
        self.nodesets.remove(name)
        self.model.removeRow(idx.row())
        self.nodeset_removed.emit(name)

    def set_server_mgr(self, server_mgr):
        self.server_mgr = server_mgr
        self.nodesets = []
        self.model.clear()
        self.model.setHorizontalHeaderLabels(['Node Sets'])
        item = QStandardItem("Opc.Ua.NodeSet2.xml")
        item.setFlags(Qt.NoItemFlags)
        self.model.appendRow([item])
        self.view.expandAll()

    def clear(self):
        self.model.clear()

    @trycatchslot
    def showContextMenu(self, position):
        if not self.server_mgr:
            return
        idx = self.view.currentIndex()
        if not idx.isValid() or idx.row() == 0:
            self.removeNodeSetAction.setEnabled(False)
        else:
            self.removeNodeSetAction.setEnabled(True)
        self._contextMenu.exec_(self.view.viewport().mapToGlobal(position))
