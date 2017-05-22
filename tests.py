
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


class TestModelMgr(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modeler = UaModeler()
        cls.mgr = cls.modeler.model_mgr._model_mgr

    @classmethod
    def tearDownClass(cls):
        cls.mgr.close_model(True)

    def test_new_close(self):
        self.mgr.new_model()
        self.assertFalse(self.mgr.modified)
        self.modeler.tree_ui.expand_to_node("Objects")
        self.mgr.add_folder(1, "myfolder")
        self.assertTrue(self.mgr.modified)
        with self.assertRaises(RuntimeError):
            self.mgr.close_model()
        self.mgr.close_model(force=True)

    def test_save_open(self):
        path = "test_save_open.xml"
        val = 0.99
        self.mgr.new_model()
        self.modeler.tree_ui.expand_to_node("Objects")
        node = self.mgr.add_variable(1, "myvar", val)
        self.mgr.save_model(path)
        self.mgr.close_model()
        with self.assertRaises(Exception):
            node = self.mgr.server_mgr.get_node(node.nodeid)
            node.get_value()
        self.mgr.open_model(path)
        node = self.mgr.server_mgr.get_node(node.nodeid)
        self.assertEqual(node.get_value(), val)
        self.mgr.close_model()


class TestModeler(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.modeler = UaModeler()
        cls.modeler.ui.actionNew.activate(0)
        cls.mgr = cls.modeler.model_mgr._model_mgr
        #modeler.show()
        #sys.exit(app.exec_())

    @classmethod
    def tearDownClass(cls):
        cls.modeler.get_current_server().stop_server()

    def test_set_current_node(self):
        objects = self.modeler.get_current_server().nodes.objects
        self.modeler.tree_ui.expand_to_node("Objects")
        self.assertEqual(objects, self.modeler.tree_ui.get_current_node())

    def test_add_folder(self):
        self.modeler.tree_ui.expand_to_node("Objects")
        dia = NewNodeBaseDialog(self.modeler, "Add Folder", self.modeler.get_current_server())
        args = dia.get_args()
        new_node = self.mgr.add_folder(*args)
        self.assertIn(new_node, self.modeler.get_current_server().nodes.objects.get_children())

    def test_add_variable_double(self):
        self.modeler.tree_ui.expand_to_node("Objects")
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.get_current_server(), default_value=9.99, dtype=ua.ObjectIds.Double)
        args = dia.get_args()
        new_node = self.mgr.add_variable(*args)
        self.assertIn(new_node, self.modeler.get_current_server().nodes.objects.get_children())

    def test_add_variable_double_list(self):
        self.modeler.tree_ui.expand_to_node("Objects")
        val = [9.9, 5.5, 1.2]
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.get_current_server(), default_value=val, dtype=ua.ObjectIds.Double)
        args = dia.get_args()
        new_node = self.mgr.add_variable(*args)
        self.assertIn(new_node, self.modeler.get_current_server().nodes.objects.get_children())
        self.assertEqual(val, new_node.get_value())

    def test_add_variable_string(self):
        self.modeler.tree_ui.expand_to_node("Objects")
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.get_current_server(), default_value="lkjkl", dtype=ua.ObjectIds.String)
        args = dia.get_args()
        new_node = self.mgr.add_variable(*args)
        self.assertIn(new_node, self.modeler.get_current_server().nodes.objects.get_children())

    def test_add_variable_extobj(self):
        self.modeler.tree_ui.expand_to_node("Objects")
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.get_current_server(), default_value="lkjkl", dtype=ua.ObjectIds.Structure)
        args = dia.get_args()
        new_node = self.mgr.add_variable(*args)
        self.assertIn(new_node, self.modeler.get_current_server().nodes.objects.get_children())

    def test_add_variable_bytes(self):
        self.modeler.tree_ui.expand_to_node("Objects")
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.get_current_server(), default_value=b"lkjkl", dtype=ua.ObjectIds.ByteString)
        args = dia.get_args()
        new_node = self.mgr.add_variable(*args)
        self.assertIn(new_node, self.modeler.get_current_server().nodes.objects.get_children())

    def test_add_variable_float_fail(self):
        self.modeler.tree_ui.expand_to_node("Objects")
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.get_current_server(), default_value=b"lkjkl", dtype=ua.ObjectIds.Float)
        with self.assertRaises(ValueError):
            args = dia.get_args()
            new_node = self.mgr.add_variable(*args)
    
    def test_add_namespace(self):
        view = self.modeler.idx_ui.view
        self.modeler.idx_ui.addNamespaceAction.activate(0)
        editor = view.focusWidget()
        urn = "urn:new_namespace"
        editor.setText(urn)
        view.commitData(editor)
        view.closeEditor(editor, QAbstractItemDelegate.NoHint)
        urns = self.modeler.get_current_server().get_namespace_array()
        self.assertIn(urn, urns)

        root = view.model().index(0, 0)
        idx = root.child(len(urns)-1, 0)
        view.setCurrentIndex(idx)
        self.modeler.idx_ui.removeNamespaceAction.activate(0)
        urns = self.modeler.get_current_server().get_namespace_array()
        self.assertNotIn(urn, urns)







if __name__ == "__main__":
    app = QApplication(sys.argv)
    unittest.main()


