import logging
import os
import xml.etree.ElementTree as Et
from collections import OrderedDict


from PyQt5.QtCore import pyqtSignal, QObject, QSettings

from opcua import ua
from opcua import copy_node
from opcua import Node
from opcua.common.instantiate import instantiate
from opcua.common.ua_utils import data_type_to_variant_type
from opcua.common.structures import Struct, StructGenerator
from opcua.common.type_dictionary_buider import DataTypeDictionaryBuilder, get_ua_class

from uawidgets.utils import trycatchslot

from uamodeler.server_manager import ServerManager

logger = logging.getLogger(__name__)


class _Struct:
    def __init__(self, name, typename):
        self.name = name
        self.typename = typename
        self.fields = []


class ModelManager(QObject):
    """
    Manage our model. loads xml, start and close, add nodes
    No dialogs at that level, only api
    """

    error = pyqtSignal(Exception)
    titleChanged = pyqtSignal(str)
    modelChanged = pyqtSignal()

    def __init__(self, modeler):
        QObject.__init__(self, modeler)
        self.modeler = modeler
        self.server_mgr = ServerManager(self.modeler.ui.actionUseOpenUa)
        self.new_nodes = []  # the added nodes we will save
        self.current_path = None
        self.settings = QSettings()
        self.modified = False
        self.modeler.attrs_ui.attr_written.connect(self._attr_written)

    def delete_node(self, node, interactive=True):
        logger.warning("Deleting: %s", node)
        if node:
            deleted_nodes = node.delete(delete_references=True, recursive=True)
            for dn in deleted_nodes:
                # make sure we remove ALL instances of node
                self.new_nodes[:] = (node for node in self.new_nodes if node != dn)
            if interactive:
                self.modeler.tree_ui.remove_current_item()

    def paste_node(self, node):
        parent = self.modeler.get_current_node()
        try:
            added_nodes = copy_node(parent, node)
        except Exception as ex:
            self.show_error(ex)
            raise
        self.new_nodes.extend(added_nodes)
        self.modeler.tree_ui.reload_current()
        self.modeler.show_refs()
        self.modified = True

    def close_model(self, force=False):
        if not force and self.modified:
            raise RuntimeError("Model is modified, use force to close it")
        self.modeler.actions.disable_all_actions()
        self.server_mgr.stop_server()
        self.current_path = None
        self.modified = False
        self.titleChanged.emit("")
        self.modeler.clear_all_widgets()

    def new_model(self):
        if self.modified:
            raise RuntimeError("Model is modified, cannot create new model")
        del (self.new_nodes[:])  # empty list while keeping reference

        endpoint = "opc.tcp://0.0.0.0:48400/freeopcua/uamodeler/"
        logger.info("Starting server on %s", endpoint)
        self.server_mgr.start_server(endpoint)

        self.modeler.tree_ui.set_root_node(self.server_mgr.nodes.root)
        self.modeler.idx_ui.set_node(self.server_mgr.get_node(ua.ObjectIds.Server_NamespaceArray))
        self.modeler.nodesets_ui.set_server_mgr(self.server_mgr)
        self.modified = False
        self.modeler.actions.enable_model_actions()
        self.current_path = None
        self.titleChanged.emit("No Name")
        return True

    def import_xml(self, path):
        new_nodes = self.server_mgr.import_xml(path)
        self.new_nodes.extend([self.server_mgr.get_node(node) for node in new_nodes])
        self.modified = True
        # we maybe should only reload the imported nodes
        self.modeler.tree_ui.reload()
        self.modeler.idx_ui.reload()
        return path

    def open_xml(self, path):
        self.new_model()
        try:
            self._open_xml(path)
        except:
            self.close_model(force=True)
            raise

    def _open_xml(self, path):
        path = self.import_xml(path)
        self.server_mgr.load_enums()
        self.server_mgr.load_type_definitions()
        self._show_structs()
        self.modified = False
        self.current_path = path
        self.titleChanged.emit(self.current_path)

    def _show_structs(self):
        base_struct = self.server_mgr.get_node(ua.ObjectIds.Structure)
        opc_binary = self.server_mgr.get_node(ua.ObjectIds.OPCBinarySchema_TypeSystem)
        opc_schema = self.server_mgr.get_node(ua.ObjectIds.OpcUa_BinarySchema)
        for node in opc_binary.get_children():
            if node == opc_schema:
                continue  # This is standard namespace structures
            try:
                ns = node.get_child("0:NamespaceUri").get_value()
                ar = self.server_mgr.get_namespace_array()
                idx = ar.index(ns)
            except ua.UaError:
                idx = 1
            xml = node.get_value()
            if not xml:
                return

            xml = xml.decode("utf-8")
            generator = StructGenerator()
            generator.make_model_from_string(xml)
            for el in generator.model:
                # we only care about structs, ignoring enums
                if isinstance(el, Struct):
                    self._add_design_node(base_struct, idx, el)

    def _add_design_node(self, base_struct, idx, el):
        try:
            struct_node = base_struct.get_child(f"{idx}:{el.name}")
        except ua.UaError:
            logger.warning("Could not find struct %s under %s", el.name, base_struct)
            return
        for field in el.fields:
            if hasattr(ua.ObjectIds, field.uatype):
                dtype = self.server_mgr.get_node(getattr(ua.ObjectIds, field.uatype))
            else:
                dtype = self._get_datatype_from_string(idx, field.uatype)
                if not dtype:
                    logger.warning("Could not find datatype of name %s %s", field.uatype, type(field.uatype))
                    return
            vtype = data_type_to_variant_type(dtype)
            val = ua.get_default_value(vtype)
            node = struct_node.add_variable(idx, field.name, val, varianttype=vtype, datatype=dtype.nodeid)
            if field.array:
                node.set_value_rank(ua.ValueRank.OneDimension)
                node.set_array_dimensions([1])


    def _get_datatype_from_string(self, idx, name):
        #FIXME: this is very heavy and missing recusion, what is the correct way to do that?
        for node in self.server_mgr.get_node(ua.ObjectIds.BaseDataType).get_children():
            try:
                dtype = node.get_child(f'{idx}:{name}')
            except ua.UaError:
                continue
            return dtype
        return None

    def open(self, path):
        if path.endswith(".xml"):
            self.open_xml(path)
        else:
            self.open_ua_model(path)

    def open_ua_model(self, path):
        self.new_model()
        try:
            self._open_ua_model(path)
        except:
            self.close_model(force=True)
            raise

    def _open_ua_model(self, path):
        tree = Et.parse(path)
        root = tree.getroot()
        for ref_el in root.findall("Reference"):
            refpath = ref_el.attrib['path']
            self.modeler.nodesets_ui.import_nodeset(refpath)
        mod_el = root.find("Model")
        dirname = os.path.dirname(path)
        xmlpath = os.path.join(dirname, mod_el.attrib['path'])
        self._open_xml(xmlpath)
        if "current_node" in mod_el.attrib:
            current_node_str = mod_el.attrib['current_node']
            nodeid = ua.NodeId.from_string(current_node_str)
            current_node = self.server_mgr.get_node(nodeid)
            self.modeler.tree_ui.expand_to_node(current_node)

    def _get_path(self, path):
        if path is None:
            path = self.current_path
        if path is None:
            raise ValueError("No path is defined")
        self.current_path = os.path.splitext(path)[0]
        self.titleChanged.emit(self.current_path)
        return self.current_path

    def save_xml(self, path=None):
        self._save_structs()
        path = self._get_path(path)
        path += ".xml"
        logger.info("Saving nodes to %s", path)
        logger.info("Exporting  %s nodes: %s", len(self.new_nodes), self.new_nodes)
        logger.info("and namespaces: %s ", self.server_mgr.get_namespace_array()[1:])
        uris = self.server_mgr.get_namespace_array()[1:]
        self.new_nodes = list(OrderedDict.fromkeys(self.new_nodes))  # remove any potential duplicate
        self.server_mgr.export_xml(self.new_nodes, uris, path)
        self.modified = False
        logger.info("%s saved", path)
        self._show_structs()  #_save_structs has delete our design nodes for structure, we need to recreate them

    def save_ua_model(self, path=None):
        path = self._get_path(path)
        model_path = path + ".uamodel"
        logger.info("Saving model to %s", model_path)
        etree = Et.ElementTree(Et.Element('UAModel'))
        node_el = Et.SubElement(etree.getroot(), "Model")
        node_el.attrib["path"] = os.path.basename(path) + ".xml"
        c_node = self.modeler.tree_ui.get_current_node()
        if c_node:
            node_el.attrib["current_node"] = c_node.nodeid.to_string()
        for refpath in self.modeler.nodesets_ui.nodesets:
            node_el = Et.SubElement(etree.getroot(), "Reference")
            node_el.attrib["path"] = refpath
        etree.write(model_path, encoding='utf-8', xml_declaration=True)
        return model_path

    def _after_add(self, new_nodes):
        if isinstance(new_nodes, (list, tuple)):
            for node in new_nodes:
                if node not in self.new_nodes:
                    self.new_nodes.append(node)
        else:
            if new_nodes not in self.new_nodes:
                self.new_nodes.append(new_nodes)
        self.modeler.tree_ui.reload_current()
        self.modeler.show_refs()
        self.modified = True

    def add_method(self, *args):
        logger.info("Creating method type with args: %s", args)
        parent = self.modeler.tree_ui.get_current_node()
        new_nodes = []
        new_node = parent.add_method(*args)
        new_nodes.append(new_node)
        new_nodes.extend(new_node.get_children())
        self._after_add(new_nodes)
        return new_nodes

    def add_object_type(self, *args):
        logger.info("Creating object type with args: %s", args)
        parent = self.modeler.tree_ui.get_current_node()
        new_node = parent.add_object_type(*args)
        self._after_add(new_node)
        return new_node

    def add_folder(self, *args):
        parent = self.modeler.tree_ui.get_current_node()
        logger.info("Creating folder with args: %s", args)
        new_node = parent.add_folder(*args)
        self._after_add(new_node)
        return new_node

    def add_object(self, *args):
        parent = self.modeler.tree_ui.get_current_node()
        logger.info("Creating object with args: %s", args)
        nodeid, bname, otype = args
        new_nodes = instantiate(parent, otype, bname=bname, nodeid=nodeid, dname=ua.LocalizedText(bname.Name))
        self._after_add(new_nodes)
        return new_nodes

    def add_data_type(self, *args):
        parent = self.modeler.tree_ui.get_current_node()
        logger.info("Creating data type with args: %s", args)
        new_node = parent.add_data_type(*args)
        self._after_add(new_node)
        return new_node

    def add_variable(self, *args):
        parent = self.modeler.tree_ui.get_current_node()
        logger.info("Creating variable with args: %s", args)
        new_node = parent.add_variable(*args)
        self._after_add(new_node)
        return new_node

    def add_property(self, *args):
        parent = self.modeler.tree_ui.get_current_node()
        logger.info("Creating property with args: %s", args)
        new_node = parent.add_property(*args)
        self._after_add(new_node)
        return new_node

    def add_variable_type(self, *args):
        parent = self.modeler.tree_ui.get_current_node()
        logger.info("Creating variable type with args: %s", args)
        nodeid, bname, datatype = args
        new_node = parent.add_variable_type(nodeid, bname, datatype.nodeid)
        self._after_add(new_node)
        return new_node

    @trycatchslot
    def _attr_written(self, attr, dv):
        self.modified = True
        if attr == ua.AttributeIds.BrowseName:
            self.modeler.tree_ui.update_browse_name_current_item(dv.Value.Value)
        elif attr == ua.AttributeIds.DisplayName:
            self.modeler.tree_ui.update_display_name_current_item(dv.Value.Value)

    def _create_type_dict_node(self, idx, urn, name):
        node_id = None
        # first delete current dict node and its children
        try:
            opc_binary = self.server_mgr.get_node(ua.ObjectIds.OPCBinarySchema_TypeSystem)
            dnode = opc_binary.get_child(f"{idx}:{name}")
            node_id = dnode.nodeid
        except ua.UaError:
            logger.warning("Dictionary node does not exist, creating it: %s", name)
        builder = DataTypeDictionaryBuilder(self.server_mgr, idx, urn, name, dict_node_id=node_id)
        if builder.dict_id not in self.new_nodes:
            self.new_nodes.append(self.server_mgr.get_node(builder.dict_id))
        return builder

    def _save_structs(self):
        """
        Save struct and delete our design nodes. They will need to be recreated
        """
        struct_node = self.server_mgr.get_node(ua.ObjectIds.Structure)
        dict_name = "TypeDictionary"
        idx = 1
        urn = self.server_mgr.get_namespace_array()[1]
        to_delete = []
        have_structs = False
        to_add = []
        for node in self.new_nodes:
            # FIXME: we do not support inheritance
            parent = node.get_parent()
            if parent == struct_node:
                if not have_structs:
                    dict_builder = self._create_type_dict_node(idx, urn, dict_name)
                    dict_node = self.server_mgr.get_node(dict_builder.dict_id)
                have_structs = True
                bname = node.get_browse_name()
                try:
                    dict_node.get_child(f"{idx}:{bname.Name}")
                    struct = dict_builder.create_data_type(bname.Name, node.nodeid, init=False)
                except ua.UaError:
                    logger.warning("DataType %s has not been initialized, doing it", bname)
                    struct = dict_builder.create_data_type(bname.Name, node.nodeid, init=True)

                childs = node.get_children()
                for child in childs:
                    bname = child.get_browse_name()
                    try:
                        dtype = child.get_data_type()
                    except ua.UaError:
                        logger.warning("could not get data type for node %s, %s, skipping", child, child.get_browse_name())
                        continue
                    array = False
                    if isinstance(child.get_value(), list) or child.get_array_dimensions() or child.get_value_rank() != ua.ValueRank.Scalar:
                        array = True

                    dtype_name = Node(node.server, dtype).get_browse_name()
                    struct.add_field(bname.Name, dtype_name.Name, is_array=array)
                    to_delete.append(child)

                to_add.extend([self.server_mgr.get_node(nodeid) for nodeid in struct.node_ids])

        if have_structs:
            dict_builder.set_dict_byte_string()
            self.new_nodes.extend(to_add)

        for node in to_delete:
            self.delete_node(node, False)

