import logging

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

    def __init__(self, modeler):
        QObject.__init__(self, modeler)
        self.modeler = modeler
        self.server_mgr = ServerManager(self.modeler.ui.actionUseOpenUa)
        self.new_nodes = []  # the added nodes we will save
        self.current_path = None
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
        self.modeler.update_title("")
        self.modeler.clear_all_widgets()

    def new_model(self):
        if self.modified:
            raise RuntimeError("Model is modified, cannot create new model")
        del(self.new_nodes[:])  # empty list while keeping reference

        endpoint = "opc.tcp://0.0.0.0:48400/freeopcua/uamodeler/"
        logger.info("Starting server on %s", endpoint)
        self.server_mgr.start_server(endpoint)

        self.modeler.tree_ui.set_root_node(self.server_mgr.nodes.root)
        self.modeler.idx_ui.set_node(self.server_mgr.get_node(ua.ObjectIds.Server_NamespaceArray))
        self.modeler.nodesets_ui.set_server_mgr(self.server_mgr)
        self.modified = False
        self.modeler.actions.enable_model_actions()
        self.current_path = None
        self.modeler.update_title("No Name")
        return True

    def import_xml(self, path):
        try:
            new_nodes = self.server_mgr.import_xml(path)
            self.new_nodes.extend([self.server_mgr.get_node(node) for node in new_nodes])
            self.modified = True
        except Exception as ex:
            self.show_error(ex)
            raise
        # we maybe should only reload the imported nodes
        self.modeler.tree_ui.reload()
        self.modeler.idx_ui.reload()
        return path

    def open_model(self, path):
        self.new_model()
        try:
            path = self.import_xml(path)
        except:
            self.close_model()
            raise
        self.modified = False
        self.current_path = path
        self.modeler.update_title(self.current_path)

    def save_model(self, path=None):
        if path is not None:
            self.current_path = path
            self.modeler.update_title(self.current_path)
        logger.info("Saving to %s", self.current_path)
        logger.info("Exporting  %s nodes: %s", len(self.new_nodes), self.new_nodes)
        logger.info("and namespaces: %s ", self.server_mgr.get_namespace_array()[1:])
        uris = self.server_mgr.get_namespace_array()[1:]
        try:
            self.server_mgr.export_xml(self.new_nodes, uris, self.current_path)
        except Exception as ex:
            self.show_error(ex)
            raise
        self.modified = False
        logger.info("%s saved", self.current_path)

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
        new_nodes = instantiate(parent, otype, bname=bname, nodeid=nodeid)
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


