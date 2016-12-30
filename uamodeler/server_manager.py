import time
import logging
from threading import Thread

from PyQt5.QtCore import QSettings

from opcua import ua
from opcua import Server
from opcua import Client
from opcua.common.xmlexporter import XmlExporter

logger = logging.getLogger(__name__)

OPENUA = True
try:
    import openua
except ImportError as ex:
    logger.info("Could not import open62541 python wrapper: %s ", ex)
    OPENUA = False


class ServerManager(object):
    def __init__(self, action):
        self._backend = ServerPython()
        self._action = action
        self._settings = QSettings()

        if OPENUA:
            use_openua = int(self._settings.value("use_openua_server", 0))
            logger.info("Using open62541: %s", openua)
            self._action.setChecked(use_openua)
            self._action.toggled.connect(self._toggle_use_openua)
            self._toggle_use_openua(use_openua)  # init state
        else:
            logger.info("Open62541 python wrappers not available, disabling action")
            self._action.setChecked(False)
            self._action.setEnabled(False)


    def close(self):
        if OPENUA:
            self._settings.setValue("use_openua_server", int(self._action.isChecked()))
        self.stop_server()

    def _toggle_use_openua(self, val):
        print("SET SERVER", val)
        if val:
            print("use C")
            self._backend = ServerC()
        else:
            self._backend = ServerPython()

    @property
    def nodes(self):
        return self._backend.nodes

    def get_node(self, node):
        return self._backend.get_node(node)

    def get_namespace_array(self):
        return self._backend.get_namespace_array()

    def start_server(self, endpoint):
        self._action.setEnabled(False)
        self._backend.start_server(endpoint)

    def stop_server(self):
        self._backend.stop_server()
        self._action.setEnabled(True)

    def import_xml(self, path):
        return self._backend.import_xml(path)

    def export_xml(self, nodes, uris, path):
        return self._backend.export_xml(nodes, uris, path)


class ServerPython(object):
    def __init__(self):
        self._server = None
        self.nodes = None
        self.get_node = None
        self.get_namespace_array = None

    def start_server(self, endpoint):
        self._server = Server()
        self._server.set_endpoint(endpoint)
        self._server.set_server_name("OpcUa Modeler Server")
        self.nodes = self._server.nodes
        self.get_node = self._server.get_node
        self.get_namespace_array = self._server.get_namespace_array
        # now remove freeopcua namespace, not necessary when modeling and
        # ensures correct idx for exported nodesets
        ns_node = self._server.get_node(ua.NodeId(ua.ObjectIds.Server_NamespaceArray))
        nss = ns_node.get_value()
        ns_node.set_value(nss[1:])
        self._server.start()

    def stop_server(self):
        if self._server is not None:
            self._server.stop()
            self._server = None

    def import_xml(self, path):
        return self._server.import_xml(path)

    def export_xml(self, nodes, uris, path):
        exp = XmlExporter(self._server)
        exp.build_etree(nodes, uris=uris)
        exp.write_xml(path)


class UAServer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.server = openua.Server()
        self.status = None
        self.endpoint = None

    def run(self):
        print("start server")
        self.status = self.server.run(self.endpoint)
        print("server stopped")

    def stop(self):
        print("trying to stop server")
        self.server.stop()


class ServerC(object):
    def __init__(self):
        self._server = None
        self._client = None
        self.nodes = None
        self.get_node = None
        self.get_namespace_array = None

    def start_server(self, endpoint):
        self._server = UAServer()
        self._server.endpoint = 48400  # enpoint not supported yet
        #self._server.endpoint = endpoint
        self._server.start()
        #self._server.set_server_name("OpcUa Modeler Server")
        time.sleep(0.2)
        self._client = Client(endpoint)
        self._client.connect()

        self.nodes = self._client.nodes
        self.get_node = self._client.get_node
        self.get_namespace_array = self._client.get_namespace_array
        # now remove freeopcua namespace, not necessary when modeling and
        # ensures correct idx for exported nodesets
        ns_node = self._client.get_node(ua.NodeId(ua.ObjectIds.Server_NamespaceArray))
        nss = ns_node.get_value()
        #ns_node.set_value(nss[1:])

    def stop_server(self):
        if self._server is not None:
            self._client.disconnect()
            self._client = None
            self._server.stop()
            time.sleep(0.2)
            self._server = None

    def import_xml(self, path):
        return self._client.import_xml(path)

    def export_xml(self, nodes, uris, path):
        exp = XmlExporter(self._client)
        exp.build_etree(nodes, uris=uris)
        exp.write_xml(path)

