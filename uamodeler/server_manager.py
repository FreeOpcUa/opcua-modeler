import time
from threading import Thread

from opcua import ua
from opcua import Server
from opcua import Client

OPENUA = True
try:
    import openua
except ImportError:
    OPENUA = False


class ServerManagerPython(object):
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

    def stop_server(self):
        if self._server is not None:
            self._server.stop()
            self._server = None

    def import_xml(self, path):
        return self._server.import_xml(path)


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


class ServerManagerC(object):
    def __init__(self):
        self._server = None
        self._client = None
        self.nodes = None
        self.get_node = None
        self.get_namespace_array = None

    def start_server(self, endpoint):
        self._server = UAServer()
        self._server.run(endpoint)
        #self._server.set_server_name("OpcUa Modeler Server")
        self._client = Client(endpoint)

        self.nodes = self._client.nodes
        self.get_node = self._client.get_node
        self.get_namespace_array = self._client.get_namespace_array
        # now remove freeopcua namespace, not necessary when modeling and
        # ensures correct idx for exported nodesets
        ns_node = self._client.get_node(ua.NodeId(ua.ObjectIds.Server_NamespaceArray))
        nss = ns_node.get_value()
        ns_node.set_value(nss[1:])

    def stop_server(self):
        if self._server is not None:
            self._client.disconnect()
            self._client = None
            self._server.stop()
            time.sleep(0.2)
            self._server = None

    def import_xml(self, path):
        return self._client.import_xml(path)


