from csvtoxml.ua.object_ids import ObjectIds
import copy
import xml.etree.ElementTree as ET

UA_ROOT = {'Root': 'i=85'}

ua_types = {'Server': 'i=85',
            'Folder': 'i=61',
            'Object': 'i=58',
            'Variable': 'i=69',
            }

# starting values for UA Node Id addresses
object_type_ns_index = 1000
child_type_ns_index = 2000
object_ns_index = 5000
variable_ns_index = 6000


def index_manager(mode):
    """
    Integer UA Node Id address generator
    :param mode:
    :return:
    """
    global object_type_ns_index
    global child_type_ns_index
    global object_ns_index
    global variable_ns_index

    if mode == 1:
        object_type_ns_index += 1
        return str(object_type_ns_index)
    if mode == 2:
        child_type_ns_index += 1
        return str(child_type_ns_index)
    if mode == 3:
        object_ns_index += 1
        return str(object_ns_index)
    if mode == 4:
        variable_ns_index += 1
        return str(variable_ns_index)
    else:
        return None


class UANodeSet(object):
    """
    Python class representing the UA Node Set XML element
    """
    def __init__(self, attributes):
        self.object_types = []
        self.objects = []
        self.variables = []
        self.root_attributes = attributes
        self.etree = ET.ElementTree(ET.Element(self.__class__.__name__, self.root_attributes))

        self._get_aliases(self.etree.getroot())

    def add_object(self, ua_object):
        ua_object.add_to_etree(self.etree.getroot())
        if isinstance(ua_object, UAObjectType):
            self.object_types.append(ua_object)
        elif isinstance(ua_object, UAObject):
            self.objects.append(ua_object)
        elif isinstance(ua_object, UAVariable):
            self.variables.append(ua_object)
        else:
            print("error adding object")

    def dump_etree(self):
        ET.dump(self.etree)

    def write(self, file_name):

        try:
            self.etree.write(file_name, short_empty_elements=False)
        except TypeError as e:
            print("error writing XML to file: ", e)

    # TODO this hack just makes a bunch of aliases, it should make aliases only for used object ids
    def _get_aliases(self, parent_el):
        alias_el = ET.SubElement(parent_el, 'Aliases')

        for name in [name for name in dir(ObjectIds) if not name.startswith('__')]:
            val = getattr(ObjectIds, name)
            tagx = ET.SubElement(alias_el, 'Alias', Alias=name)
            tagx.text = 'i=' + str(val)


class UAObjectType(object):
    """
    Python class representing the UA Object Type XML element
    """

    def __init__(self, name, node_id=None, namespace='1', children=None):
        self.object_type_name = self.__class__.__name__

        self.namespace = namespace
        if self.namespace is None:
            self.namespace = '1'

        self.node_id = node_id
        if self.node_id is None:
            self.node_id = index_manager(1)

        self.full_node_id = 'ns=' + self.namespace + ';i=' + self.node_id

        self.name = name
        self.browse_name = self.namespace + ':' + self.name

        # TODO should get ref type automatically
        self.ref_type_has_subtype = "i=58"  # opc ua object id for base object type

        self.children = children
        if self.children is not None:
            child_vars = [UAVariable(self.full_node_id, child['name'], child['data type'], child['node id'], value=child['value']) for k, child in children.items()]
            self.children = child_vars

    def add_to_etree(self, parent_el):
        # ET.Comment('**** Object Type - ' + self.name + ' ****')

        root_el = ET.SubElement(parent_el, self.object_type_name, NodeId=self.full_node_id, BrowseName=self.browse_name)
        disp_el = ET.SubElement(root_el, 'DisplayName')
        disp_el.text = self.name

        ref_el = ET.SubElement(root_el, 'References')

        tagx = ET.SubElement(ref_el, 'Reference', ReferenceType='HasSubtype', IsForward='false')
        tagx.text = self.ref_type_has_subtype

        for child in self.children:
            tagx = ET.SubElement(ref_el, 'Reference', ReferenceType='HasComponent')
            tagx.text = child.full_node_id

            child.add_to_etree(parent_el, True)


class UAVariable(object):
    """
    Python class representing the UA Variable XML element
    """
    def __init__(self, parent_full_node_id, name, data_type, node_id=None, namespace='1', value=None, user_access_level=3, access_level=3):
        self.parent_full_node_id = parent_full_node_id
        if self.parent_full_node_id in UA_ROOT:
            self.parent_full_node_id = UA_ROOT[parent_full_node_id]
        self.object_type_name = self.__class__.__name__
        self.data_type = data_type

        self.namespace = namespace
        if self.namespace is None:
            self.namespace = 1

        self.node_id = node_id
        if self.node_id is None:
            self.node_id = index_manager(2)

        self.full_node_id = 'ns=' + self.namespace + ';i=' + self.node_id

        self.name = name
        self.browse_name = self.namespace + ':' + self.name

        self.value = value

        self.user_access_level = str(user_access_level)
        self.access_level = str(access_level)

        # TODO should get ref type automatically
        self.ref_type_has_type_def = "i=63"  # opc ua object id for base data variable

    def update_for_instance(self, parent_full_node_id, value=None):
        # ONLY USE AFTER DEEP COPY
        # TODO better to override __deepcopy__?
        self.parent_full_node_id = parent_full_node_id
        self.node_id = index_manager(4)
        self.full_node_id = 'ns=' + self.namespace + ';i=' + self.node_id
        self.value = value

    def add_to_etree(self, parent_el, as_object_type=False):
        # ET.Comment('**** Object Type Child - ' + self.name + ' ****')

        root_el = ET.SubElement(parent_el, self.object_type_name, DataType=self.data_type, ParentNodeId=self.parent_full_node_id, NodeId=self.full_node_id, BrowseName=self.browse_name, UserAccessLevel=self.user_access_level, AccessLevel=self.access_level)
        disp_el = ET.SubElement(root_el, 'DisplayName')
        disp_el.text = self.name

        ref_el = ET.SubElement(root_el, 'References')

        tagx = ET.SubElement(ref_el, 'Reference', ReferenceType='HasTypeDefinition')
        tagx.text = self.ref_type_has_type_def

        if as_object_type is True:
            tagx = ET.SubElement(ref_el, 'Reference', ReferenceType='HasComponent', IsForward='false')
            tagx.text = self.parent_full_node_id

            tagx = ET.SubElement(ref_el, 'Reference', ReferenceType='HasModellingRule')
            tagx.text = 'i=78'  # opc ua object id for has modelling rule mandatory
        else:
            tagx = ET.SubElement(ref_el, 'Reference', ReferenceType='Organizes', IsForward='false')
            tagx.text = self.parent_full_node_id

        val_el = ET.SubElement(root_el, 'Value')

        tagx = ET.SubElement(val_el, 'uax:' + self.data_type)
        tagx.text = self.value
        if tagx.text is None:
            tagx.text = ''
        else:
            tagx.text = str(self.value)


class UAObject(object):
    """
    Python class representing the UA Object XML element
    """
    def __init__(self, parent_full_node_id, name, node_id=None, namespace='1', object_type=None, child_values=None):
        # self.parent = parent
        self.parent_full_node_id = parent_full_node_id
        if self.parent_full_node_id in UA_ROOT.keys():
            self.parent_full_node_id = UA_ROOT[parent_full_node_id]

        self.object_type_name = self.__class__.__name__

        self.namespace = namespace
        if self.namespace is None:
            self.namespace = '1'

        self.node_id = node_id
        if self.node_id is None:
            self.node_id = index_manager(3)

        self.full_node_id = 'ns=' + self.namespace + ';i=' + self.node_id

        self.name = name
        self.browse_name = self.namespace + ':' + self.name

        self.child_values = child_values
        if object_type is not None:
            self.child_values = child_values.split(';')

        # TODO should be improved
        self.object_type = object_type
        self.children = None
        if object_type is not None:
            self.ref_type_has_type_def = object_type.full_node_id
            self.children = copy.deepcopy(object_type.children)
            i = 0
            for child in self.children:
                if child_values is not None:
                    child.update_for_instance(self.full_node_id, self.child_values[i])
                else:
                    child.update_for_instance(self.full_node_id)
                i += 1

        else:
            self.ref_type_has_type_def = "i=58"  # opc ua object id for base object type

    def add_to_etree(self, parent_el):
        # ET.Comment('**** Object Type Instance - ' + self.name + ' ****')

        root_el = ET.SubElement(parent_el, self.object_type_name, NodeId=self.full_node_id, BrowseName=self.browse_name)
        disp_el = ET.SubElement(root_el, 'DisplayName')
        disp_el.text = self.name

        ref_el = ET.SubElement(root_el, 'References')

        tagx = ET.SubElement(ref_el, 'Reference', ReferenceType='Organizes', IsForward='false')
        tagx.text = self.parent_full_node_id

        tagx = ET.SubElement(ref_el, 'Reference', ReferenceType='HasTypeDefinition')
        tagx.text = self.ref_type_has_type_def

        if self.children is not None:
            for child in self.children:
                tagx = ET.SubElement(ref_el, 'Reference', ReferenceType='HasComponent')
                tagx.text = child.full_node_id

                child.add_to_etree(parent_el)
