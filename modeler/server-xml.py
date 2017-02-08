import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
sys.path.insert(0, "..")
import time

from opcua import ua, Server
from opcua.ua import object_ids as o_ids


def node_to_xml(etree, node):
    if node.get_node_class() is ua.NodeClass.Variable:
        var_el = ET.SubElement(etree.getroot(),
                                'UAVariable',
                                BrowseName=make_xml_browsename(node),
                                DataType=o_ids.ObjectIdNames[node.get_data_type().Identifier],
                                NodeId=make_xml_nodeid(node),
                                ParentNodeId=get_parent(node),
                                AccessLevel='3',  # TODO How to get this attribute as a number and not as AccessLevel.X enum
                                UserAccessLevel='3')  # TODO How to get this attribute as a number and not as AccessLevel.X enum

        disp_el = ET.SubElement(var_el, 'DisplayName',)
        disp_el.text = node.get_display_name().Text.decode(encoding='UTF8')

        refs_el = ET.SubElement(var_el, 'References')

        refx_el = ET.SubElement(refs_el, 'Reference', ReferenceType='x')  # TODO find reusable way to get all refs

        val_el = ET.SubElement(var_el, 'Value')

        valx_el = ET.SubElement(val_el, 'uax:' + o_ids.ObjectIdNames[node.get_data_type().Identifier])
        valx_el.text = str(node.get_value())

    elif node.get_node_class() is ua.NodeClass.Object:
        #  make a different element
        pass


def make_xml_nodeid(node):
    """
    Convert a UA NodeId object to a formatted string for XML
    :param node:
    :return:
    """
    return 'ns=' + str(node.nodeid.NamespaceIndex) + ';' + str(node.nodeid.Identifier)


def make_xml_browsename(node):
    bn = node.get_browse_name()
    return str(bn.NamespaceIndex) + ':' + bn.Name


def get_parent(node):
    return make_xml_nodeid(node.get_parent())


# noinspection PyPackageRequirements
if __name__ == "__main__":
    node_set_attributes = OrderedDict()
    node_set_attributes['xmlns:xsi'] = '"http://www.w3.org/2001/XMLSchema-instance"'
    node_set_attributes['xmlns:uax'] = 'http://opcfoundation.org/UA/2008/02/Types.xsd'
    node_set_attributes['xmlns:s1'] = 'http://yourorganisation.org/dataobject/Types.xsd'
    node_set_attributes['xmlns:xsd'] = 'http://www.w3.org/2001/XMLSchema'
    node_set_attributes['xmlns'] = 'http://opcfoundation.org/UA/2011/03/UANodeSet.xsd'

    # create an XML element tree
    etree = ET.ElementTree(ET.Element('UANodeSet', node_set_attributes))

    # setup our server
    server = Server()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")

    # setup our own namespace, not really necessary but should as spec
    uri = "http://examples.freeopcua.github.io"
    idx = server.register_namespace(uri)

    # get Objects node, this is where we should put our nodes
    objects = server.get_objects_node()

    # populating our address space
    myobj = objects.add_object(idx, "MyObject")
    myvar = myobj.add_variable(idx, "MyVariable", 6.7)
    myvar.set_writable()    # Set MyVariable to be writable by clients

    # starting!
    server.start()

    # test converting a node in the server address space to XML
    node_to_xml(etree, myvar)

    # output the XML for testing
    ET.dump(etree)

    server.stop()
