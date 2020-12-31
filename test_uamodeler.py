
import sys
import pytest

from asyncua import ua

from PyQt5.QtCore import QTimer, QSettings, QModelIndex, Qt, QCoreApplication

from uamodeler.uamodeler import UaModeler
from uawidgets.new_node_dialogs import NewNodeBaseDialog, NewUaObjectDialog, NewUaVariableDialog, NewUaMethodDialog



@pytest.fixture(scope="function")
def modeler():
    app = QApplication(sys.argv)
    modeler = UaModeler()
    yield modeler
    #sys.exit(0)


@pytest.fixture
def mgr(modeler):
    mgr = modeler.model_mgr._model_mgr
    mgr.close_model(force=True)  # make sure we close model
    yield mgr
    mgr.close_model(force=True)  # make sure we close model


@pytest.fixture
def model(mgr):
    mgr.new_model()
    yield model
    mgr.close_model(True)


def test_new_close(modeler, mgr):
    mgr.new_model()
    assert not mgr.modified
    modeler.tree_ui.expand_to_node("Objects")
    mgr.add_folder(1, "myfolder")
    assert mgr.modified
    with pytest.raises(RuntimeError):
        mgr.close_model()
    mgr.close_model(True)


def test_save_open_xml(modeler, mgr):
    path = "test_save_open.xml"
    val = 0.99
    mgr.new_model()
    modeler.tree_ui.expand_to_node("Objects")
    node = mgr.add_variable(1, "myvar", val)
    mgr.save_xml(path)
    mgr.close_model()
    with pytest.raises(Exception):
        node = mgr.server_mgr.get_node(node.nodeid)
        node.read_value()
    mgr.open(path)
    node = mgr.server_mgr.get_node(node.nodeid)
    assert node.read_value() == val
    mgr.close_model(True)


def test_save_open_ua_model(modeler, mgr):
    path = "test_save_open.uamodel"
    val = 0.99
    mgr.new_model()
    modeler.tree_ui.expand_to_node("Objects")
    node = mgr.add_variable(1, "myvar", val)
    mgr.save_ua_model(path)
    mgr.save_xml(path)
    mgr.close_model()
    with pytest.raises(Exception):
        node = mgr.server_mgr.get_node(node.nodeid)
        node.read_value()
    mgr.open(path)
    node = mgr.server_mgr.get_node(node.nodeid)
    node.read_value() == val
    mgr.close_model()


#@pytest.mark.skip("Something wrong with expand_to_node")
def test_delete_save(modeler, mgr, model):
    path = "test_delete_save.uamodel"
    val = 0.99
    modeler.tree_ui.expand_to_node("Objects")
    obj_node = mgr.add_folder(1, "myobj")
    obj2_node = mgr.add_folder(1, "myobj2")
    QApplication.processEvents()
    modeler.tree_ui.expand_to_node("myobj2")
    var_node = mgr.add_variable(1, "myvar", val)
    mgr.save_ua_model(path)
    mgr.save_xml(path)

    QApplication.processEvents()
    modeler.tree_ui.expand_to_node(obj2_node)
    mgr.delete_node(obj2_node)
    mgr.save_ua_model(path)
    mgr.save_xml(path)
    assert obj2_node not in mgr.new_nodes
    assert var_node not in mgr.new_nodes


def test_structs(modeler, mgr):
    mgr.new_model()

    urns = modeler.get_current_server().get_namespace_array()
    ns_node = mgr.server_mgr.get_node(ua.ObjectIds.Server_NamespaceArray)
    urns = ns_node.read_value()
    urns.append("urn://modeller/testing")
    ns_node.write_value(urns)

    path = "test_save_structs.xml"

    struct_node = mgr.server_mgr.get_node(ua.ObjectIds.Structure)
    modeler.tree_ui.expand_to_node(struct_node)
    mystruct = mgr.add_data_type(1, "MyStruct")
    var1 = mystruct.add_variable(1, "MyFloat", 0.1, varianttype=ua.VariantType.Float)
    var2 = mystruct.add_variable(1, "MyBytes", b'lkjlk', varianttype=ua.VariantType.ByteString)
    mgr.save_xml(path)
    assert len(mgr.new_nodes) == 4  # one struct + TypeDictionary node + namespace and struct node under typedict

    # FIXME: test for presence of nodes under typedict for every new struct
    opc_binary = mgr.server_mgr.get_node(ua.ObjectIds.OPCBinarySchema_TypeSystem)
    typedict = opc_binary.get_child("1:TypeDictionary")
    xml = typedict.read_value()
    assert b"MyFloat" in xml
    assert b"MyStruct" in xml

    mgr.save_xml(path)
    mgr.close_model()
    mgr.open_xml(path)

    opc_binary = mgr.server_mgr.get_node(ua.ObjectIds.OPCBinarySchema_TypeSystem)
    typedict = opc_binary.get_child("1:TypeDictionary")
    xml = typedict.read_value()

    assert b"MyFloat" in xml
    assert b"MyStruct" in xml

    struct_node = mgr.server_mgr.get_node(ua.ObjectIds.Structure)
    struct_node.get_child("1:MyStruct")

    mgr.server_mgr.load_type_definitions()

    st = ua.MyStruct()
    assert hasattr(st, "MyFloat")
    st.MyBytes = b"klk"


def test_structs_2(modeler, mgr):
    mgr.new_model()

    urns = modeler.get_current_server().get_namespace_array()
    ns_node = mgr.server_mgr.get_node(ua.ObjectIds.Server_NamespaceArray)
    urns = ns_node.read_value()
    urns.append("urn://modeller/testing")
    ns_node.write_value(urns)

    path = "test_save_structs_2.xml"

    struct_node = mgr.server_mgr.get_node(ua.ObjectIds.Structure)
    modeler.tree_ui.expand_to_node(struct_node)
    mystruct = mgr.add_data_type(1, "MyStruct")
    QApplication.processEvents()
    modeler.tree_ui.expand_to_node("MyStruct")
    var_node = mgr.add_variable(1, "myvar", 0.1)

    mgr.save_xml(path)
    mgr.close_model()
    mgr.open_xml(path)

    struct_node = mgr.server_mgr.get_node(ua.ObjectIds.Structure)
    mystruct_node = struct_node.get_child("1:MyStruct")
    var2_node = mystruct_node.add_variable(1, "myvar2", 0.2)
    # following code break...why??!?!??!
    #QApplication.processEvents()
    #modeler.tree_ui.expand_to_node("MyStruct")
    #var2_node = mgr.add_variable(1, "myvar2", 0.2)

    mgr.save_xml(path)
    mgr.close_model()
    mgr.open_xml(path)

    struct_node = mgr.server_mgr.get_node(ua.ObjectIds.Structure)
    mystruct = struct_node.get_child("1:MyStruct")
    assert len(mystruct.get_children()) == 2

    mgr.server_mgr.load_type_definitions()

    st = ua.MyStruct()
    assert hasattr(st, "myvar")
    assert hasattr(st, "myvar2")
    mgr.close_model()


def test_set_current_node(modeler, mgr, model):
    objects = modeler.get_current_server().nodes.objects
    modeler.tree_ui.expand_to_node("Objects")
    assert objects == modeler.tree_ui.get_current_node()


def test_set_current_node_nodeid(modeler, mgr, model):
    struct_node = mgr.server_mgr.get_node(ua.ObjectIds.Structure)
    modeler.tree_ui.expand_to_node(struct_node)
    assert struct_node == modeler.tree_ui.get_current_node()


def test_add_folder(modeler, mgr, model):
    modeler.tree_ui.expand_to_node("Objects")
    dia = NewNodeBaseDialog(modeler, "Add Folder", modeler.get_current_server())
    args = dia.get_args()
    new_node = mgr.add_folder(*args)
    assert new_node in modeler.get_current_server().nodes.objects.get_children()


def test_add_variable_double(modeler, mgr, model):
    modeler.tree_ui.expand_to_node("Objects")
    dia = NewUaVariableDialog(modeler, "Add Variable", modeler.get_current_server(), dtype=ua.ObjectIds.Double)
    args = dia.get_args()
    new_node = mgr.add_variable(*args)
    assert new_node in modeler.get_current_server().nodes.objects.get_children()


def test_add_variable_double_list(modeler, mgr, model):
    modeler.tree_ui.expand_to_node("Objects")
    dia = NewUaVariableDialog(modeler, "Add Variable", modeler.get_current_server(), dtype=ua.ObjectIds.Double)
    args = dia.get_args()
    new_node = mgr.add_variable(*args)
    assert new_node in modeler.get_current_server().nodes.objects.get_children()
    assert isinstance(new_node.read_value(), float)


def test_add_variable_string(modeler, mgr, model):
    modeler.tree_ui.expand_to_node("Objects")
    dia = NewUaVariableDialog(modeler, "Add Variable", modeler.get_current_server(), dtype=ua.ObjectIds.String)
    args = dia.get_args()
    new_node = mgr.add_variable(*args)
    assert new_node in modeler.get_current_server().nodes.objects.get_children()


def test_add_variable_extobj(modeler, mgr, model):
    modeler.tree_ui.expand_to_node("Objects")
    dia = NewUaVariableDialog(modeler, "Add Variable", modeler.get_current_server(), dtype=ua.ObjectIds.Structure)
    args = dia.get_args()
    new_node = mgr.add_variable(*args)
    assert new_node in modeler.get_current_server().nodes.objects.get_children()


def test_add_variable_bytes(modeler, mgr, model):
    modeler.tree_ui.expand_to_node("Objects")
    dia = NewUaVariableDialog(modeler, "Add Variable", modeler.get_current_server(), dtype=ua.ObjectIds.ByteString)
    val = b"lkjkjl"
    dia.valLineEdit.setText(val.decode())
    args = dia.get_args()
    new_node = mgr.add_variable(*args)
    assert new_node in modeler.get_current_server().nodes.objects.get_children()
    assert val == new_node.read_value()


def test_add_variable_float_fail(modeler, mgr, model):
    modeler.tree_ui.expand_to_node("Objects")
    dia = NewUaVariableDialog(modeler, "Add Variable", modeler.get_current_server(), dtype=ua.ObjectIds.Float)
    dia.valLineEdit.setText("oiuiu")
    with pytest.raises(ValueError):
        args = dia.get_args()
        new_node = mgr.add_variable(*args)


def test_add_namespace(modeler, mgr, model):
    view = modeler.idx_ui.view
    modeler.idx_ui.addNamespaceAction.activate(0)
    editor = view.focusWidget()
    urn = "urn:new_namespace"
    editor.setText(urn)
    view.commitData(editor)
    view.closeEditor(editor, QAbstractItemDelegate.NoHint)
    urns = modeler.get_current_server().get_namespace_array()
    assert urn in urns

    root = view.model().index(0, 0)
    idx = root.child(len(urns)-1, 0)
    view.setCurrentIndex(idx)
    modeler.idx_ui.removeNamespaceAction.activate(0)
    urns = modeler.get_current_server().get_namespace_array()
    assert urn not in urns


