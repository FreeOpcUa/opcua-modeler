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

    def delete_node(self, node):
        if node:
            deleted_nodes = node.delete(delete_references=True, recursive=True)
            for dn in deleted_nodes:
                if dn in self.new_nodes:
                    self.new_nodes.remove(dn)
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
            struct_node.add_variable(idx, field.name, field.value, varianttype=vtype, datatype=dtype.nodeid)

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

    def _save_structs(self):
        """
        Save struct and delete our design nodes. They will need to be recreated
        """
        struct_node = self.server_mgr.get_node(ua.ObjectIds.Structure)
        structs = []
        to_delete = []
        for node in self.new_nodes:
            # FIXME: we do not support inheritance
            parent = node.get_parent()
            if parent == struct_node:
                bname = node.get_browse_name()
                st = _Struct(bname.Name, "ExtensionObject")
                childs = node.get_children()
                for child in childs:
                    bname = child.get_browse_name()
                    try:
                        dtype = child.get_data_type()
                    except ua.UaError:
                        logger.warning("could not get data type for node %s, %s, skipping", child, child.get_browse_name())
                        continue
                    dtype_name = Node(node.server, dtype).get_browse_name()
                    st.fields.append([bname.Name, dtype_name.Name])
                    to_delete.append(child)
                structs.append(st)

        if structs:
            self._save_bsd(structs)

        for node in to_delete:
            node.delete()
            if node in self.new_nodes:
                self.new_nodes.remove(node)

    def _save_bsd(self, structs):
        logger.warning("Structs %s", structs)
        idx = 1 
        urn = self.server_mgr.get_namespace_array()[1]
        dict_name = "TypeDictionary"

        node_set_attributes = OrderedDict()
        node_set_attributes['xmlns:opc'] = "http://opcfoundation.org/BinarySchema/"
        node_set_attributes['xmlns:xsi'] = 'http://www.w3.org/2001/XMLSchema-instance'
        node_set_attributes['xmlns:ua'] = "http://opcfoundation.org/UA/"
        node_set_attributes['xmlns:tns'] = urn
        node_set_attributes['DefaultByteOrder'] = 'LittleIndian'
        node_set_attributes['TargetNamespace'] = urn

        etree = Et.ElementTree(Et.Element('opc:TypeDictionnary', node_set_attributes))
        root_el = etree.getroot()

        Et.SubElement(root_el, 'opc:Import', {'Namespace': "http://opcfoundation.org/UA/", 'Location': 'Opc.Ua.BinarySchema.bsd'})
        for struct in structs:
            struct_el = Et.SubElement(root_el, 'opc:StructuredType', {'Name': struct.name, 'BaseType': 'ua' + struct.typename})
            for name, typename in struct.fields:
                if hasattr(ua.ObjectIds, typename):
                    prefix = "opc"
                else:
                    prefix = "tns"
                Et.SubElement(struct_el, 'opc:Field', {'Name': name, 'TypeName': prefix + ":" + typename})

        val = Et.tostring(root_el, encoding='utf-8')
        opc_binary = self.server_mgr.get_node(ua.ObjectIds.OPCBinarySchema_TypeSystem)
        dict_node = self._set_or_add_variable(opc_binary, idx, dict_name, val, ua.VariantType.ByteString)

        # add struct and namespace nodes under dict_node
        self._create_typedictonary_children(dict_node, idx, urn, [struct.name for struct in structs])

    def _create_typedictonary_children(self, typenode, idx, urn, structs):
        self._set_or_add_variable(typenode, idx, "NamespaceUri", urn, varianttype=ua.VariantType.String, isproperty=True)
        for name in structs:
            node = self._set_or_add_variable(typenode, idx, name, name, varianttype=ua.VariantType.String, isproperty=True)
            ref_desc_list = node.get_references(refs=ua.ObjectIds.HasDescription, direction=ua.BrowseDirection.Inverse)
            if not ref_desc_list:
                # we need to add description
                node.add_reference(ua.ObjectIds.DataTypeEncodingType, ua.ObjectIds.HasDescription, forward=False, bidirectional=True)
                #FIXME: link is bidirectional... this is not going to be saved or??

    def _set_or_add_variable(self, parent, idx, name, val, varianttype, isproperty=False, save=True):
        try:
            node = parent.get_child(f'{idx}:{name}')
            node.set_value(val, varianttype=varianttype)
        except ua.UaError:
            if isproperty:
                node = parent.add_property(idx, name, val, varianttype=varianttype)
            else:
                node = parent.add_variable(idx, name, val, varianttype=varianttype)
        if save:
            self._after_add(node)
        return node

