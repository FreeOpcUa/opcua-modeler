
import unittest
import sys
print("SYS:PATH", sys.path)
sys.path.insert(0, "python-opcua")
sys.path.insert(0, "opcua-widgets")
import os
print("PWD", os.getcwd())

from opcua import ua

from PyQt5.QtCore import QTimer, QSettings, QModelIndex, Qt, QCoreApplication
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest

from uamodeler.uamodeler import UaModeler
from uawidgets.new_node_dialogs import NewNodeBaseDialog, NewUaObjectDialog, NewUaVariableDialog, NewUaMethodDialog


class Tester(unittest.TestCase):
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

    def test_add_variable_string(self):
        objects = self.modeler.server.nodes.objects
        self.modeler.tree_ui.set_current_node("Objects")
        self.assertEqual(objects, self.modeler.tree_ui.get_current_node())
        dia = NewUaVariableDialog(self.modeler, "Add Variable", self.modeler.server, default_value="lkjkl", dtype=ua.ObjectIds.String)
        args = dia.get_args()
        new_node = objects.add_variable(*args)
        self.assertIn(new_node, objects.get_children())



if __name__ == "__main__":
    app = QApplication(sys.argv)
    unittest.main()


