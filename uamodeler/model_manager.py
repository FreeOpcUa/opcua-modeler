import logging
import os
import xml.etree.ElementTree as Et


from PyQt5.QtCore import pyqtSignal, QObject, QSettings

from opcua import ua
from opcua import copy_node
from opcua.common.instantiate import instantiate
from opcua.common.ua_utils import get_node_children

from uawidgets.utils import trycatchslot

from uamodeler.server_manager import ServerManager

logger = logging.getLogger(__name__)


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
            nodes = get_node_children(node)
            for n in nodes:
                n.delete()
                if n in self.new_nodes:
                    self.new_nodes.remove(n)
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
        self.modified = False
        self.current_path = path
        self.titleChanged.emit(self.current_path)

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
        xmlpath = mod_el.attrib['path']
        self._open_xml(xmlpath)

    def _get_path(self, path):
        if path is None:
            path = self.current_path
        if path is None:
            raise ValueError("No path is defined")
        self.current_path = os.path.splitext(path)[0] 
        self.titleChanged.emit(self.current_path)
        return self.current_path

    def save_xml(self, path=None):
        path = self._get_path(path)
        path += ".xml"
        logger.info("Saving nodes to %s", path)
        logger.info("Exporting  %s nodes: %s", len(self.new_nodes), self.new_nodes)
        logger.info("and namespaces: %s ", self.server_mgr.get_namespace_array()[1:])
        uris = self.server_mgr.get_namespace_array()[1:]
        self.server_mgr.export_xml(self.new_nodes, uris, path)
        self.modified = False
        logger.info("%s saved", path)

    def save_ua_model(self, path=None):
        path = self._get_path(path)
        model_path = path + ".uamodel"
        logger.info("Saving model to %s", model_path)
        etree = Et.ElementTree(Et.Element('UAModel'))
        node_el = Et.SubElement(etree.getroot(), "Model")
        node_el.attrib["path"] = path + ".xml"
        for refpath in self.modeler.nodesets_ui.nodesets:
            node_el = Et.SubElement(etree.getroot(), "Reference")
            node_el.attrib["path"] = refpath 
        etree.write(model_path, encoding='utf-8', xml_declaration=True)

    def _after_add(self, new_nodes):
        if isinstance(new_nodes, (list, tuple)):
            self.new_nodes.extend(new_nodes)
        else:
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

    def add_object_type(self, *args):
        logger.info("Creating object type with args: %s", args)
        parent = self.modeler.tree_ui.get_current_node()
        new_node = parent.add_object_type(*args)
        self._after_add(new_node)

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
        self.settings.setValue("last_datatype", args[4])
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
