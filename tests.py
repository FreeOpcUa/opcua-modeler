
import unittest
import sys
sys.path.insert(0, "python-opcua")
sys.path.insert(0, "opcua-widgets")
import os

from opcua import ua

from PyQt5.QtCore import QTimer, QSettings, QModelIndex, Qt, QCoreApplication
from PyQt5.QtWidgets import QApplication, QAbstractItemDelegate
from PyQt5.QtTest import QTest

from uamodeler.uamodeler import UaModeler
from uawidgets.new_node_dialogs import NewNodeBaseDialog, NewUaObjectDialog, NewUaVariableDialog, NewUaMethodDialog


class TestModeler(unittest.TestCase):
    def setUp(self):
        self.modeler = UaModeler()
        self.modeler.ui.actionNew.activate(0)
        #modeler.show()
        #sys.exit(app.exec_())

    def tearDown(self):
        self.modeler.server.stop()

    def test_add_folder(self):
        objects = self.modeler.server.nodes.objects
        self.modeler.tree_ui.set_current_node("Objects")
        self.assertEqual(objects, self.modeler.tree_ui.get_current_node())
        #self.modeler.ui.actionAddFolder.activate(0)  # we cannot call this, we need a link to dialog
        dia = NewNodeBaseDialog(self.modeler, "Add Folder", self.modeler.server)
        args = dia.get_args()
        new_node = objects.add_folder(*args)
        self.assertIn(new_node, objects.get_children())

    def test_add_variable_double(self):
        objects = self.modeler.server.nodes.objects
        self.modeler.tree_ui.set_current_node("Objects")
        self.assertEqual(objects, self.modeler.tree_ui.get_current_node())
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.server, default_value=9.99, dtype=ua.ObjectIds.Double)
        args = dia.get_args()
        new_node = objects.add_variable(*args)
        self.assertIn(new_node, objects.get_children())

    def test_add_variable_double_list(self):
        objects = self.modeler.server.nodes.objects
        self.modeler.tree_ui.set_current_node("Objects")
        self.assertEqual(objects, self.modeler.tree_ui.get_current_node())
        val = [9.9, 5.5, 1.2]
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.server, default_value=val, dtype=ua.ObjectIds.Double)
        args = dia.get_args()
        new_node = objects.add_variable(*args)
        self.assertIn(new_node, objects.get_children())
        self.assertEqual(val, new_node.get_value())

    def test_add_variable_string(self):
        objects = self.modeler.server.nodes.objects
        self.modeler.tree_ui.set_current_node("Objects")
        self.assertEqual(objects, self.modeler.tree_ui.get_current_node())
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.server, default_value="lkjkl", dtype=ua.ObjectIds.String)
        args = dia.get_args()
        new_node = objects.add_variable(*args)
        self.assertIn(new_node, objects.get_children())

    def test_add_variable_extobj(self):
        objects = self.modeler.server.nodes.objects
        self.modeler.tree_ui.set_current_node("Objects")
        self.assertEqual(objects, self.modeler.tree_ui.get_current_node())
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.server, default_value="lkjkl", dtype=ua.ObjectIds.Structure)
        args = dia.get_args()
        new_node = objects.add_variable(*args)
        self.assertIn(new_node, objects.get_children())

    def test_add_variable_bytes(self):
        objects = self.modeler.server.nodes.objects
        self.modeler.tree_ui.set_current_node("Objects")
        self.assertEqual(objects, self.modeler.tree_ui.get_current_node())
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.server, default_value=b"lkjkl", dtype=ua.ObjectIds.ByteString)
        args = dia.get_args()
        new_node = objects.add_variable(*args)
        self.assertIn(new_node, objects.get_children())

    def test_add_variable_float_fail(self):
        objects = self.modeler.server.nodes.objects
        self.modeler.tree_ui.set_current_node("Objects")
        self.assertEqual(objects, self.modeler.tree_ui.get_current_node())
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.server, default_value=b"lkjkl", dtype=ua.ObjectIds.Float)
        with self.assertRaises(ValueError):
            args = dia.get_args()
            new_node = objects.add_variable(*args)
    
    def test_add_namespace(self):
        view = self.modeler.idx_ui.view
        self.modeler.idx_ui.addNamespaceAction.activate(0)
        editor = view.focusWidget()
        urn = "urn:new_namespace"
        editor.setText(urn)
        view.commitData(editor)
        view.closeEditor(editor, QAbstractItemDelegate.NoHint)
        urns = self.modeler.server.get_namespace_array()
        self.assertIn(urn, urns)

        root = view.model().index(0, 0)
        idx = root.child(len(urns)-1, 0)
        view.setCurrentIndex(idx)
        self.modeler.idx_ui.removeNamespaceAction.activate(0)
        urns = self.modeler.server.get_namespace_array()
        self.assertNotIn(urn, urns)







if __name__ == "__main__":
    app = QApplication(sys.argv)
    unittest.main()


