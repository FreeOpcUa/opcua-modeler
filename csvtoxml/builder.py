from csvtoxml.xmlmodeler import UANodeSet, UAObjectType, UAObject, UAVariable
import csv
from collections import OrderedDict

node_set_attributes = OrderedDict()
node_set_attributes['xmlns:xsi'] = '"http://www.w3.org/2001/XMLSchema-instance"'
node_set_attributes['xmlns:uax'] = 'http://opcfoundation.org/UA/2008/02/Types.xsd'
node_set_attributes['xmlns:s1'] = 'http://yourorganisation.org/dataobject/Types.xsd'
node_set_attributes['xmlns:xsd'] = 'http://www.w3.org/2001/XMLSchema'
node_set_attributes['xmlns'] = 'http://opcfoundation.org/UA/2011/03/UANodeSet.xsd'


def csv_to_xml(file, xml_filename):
    """
    Take formatted csv file and convert it to an OPC UA XML

    :param file:
    :param xml_filename:
    :return:
    """
    my_types = OrderedDict()
    my_types_children = OrderedDict()
    my_objects = OrderedDict()
    my_variables = OrderedDict()

    # get base objects
    print('Importing objects from csv')
    with open(file) as csv_file:
        reader = csv.DictReader(csv_file, dialect='excel')
        for row in reader:
            if row['base type'] == 'ObjectType':
                my_types[(row['name'])] = row
            elif row['base type'] == 'Object':
                if row['child values'] == '':
                    row['child values'] = None
                my_objects[(row['name'])] = row
            elif row['base type'] == 'Variable':
                my_variables[(row['name'])] = row

    # get objects which belong to a custom type
    print('Importing objects that belong to a custom type from csv')
    with open(file) as csv_file:
        reader = csv.DictReader(csv_file, dialect='excel')
        for ua_type in my_types.keys():
            type_children = OrderedDict()
            for row in reader:
                if row['parent'] == ua_type:
                    if row['node id'] == '':
                        row['node id'] = None
                    # type_children.append([row['name'], row['object type'], row['node id']])
                    type_children[row['name']] = row
            my_types_children[ua_type] = type_children

    # remove objects/variables that belong to a custom UA type
    print('Removing duplicate entries due to custom object types')
    for k, v in my_types_children.items():
        for key in v.keys():
            if key in my_variables.keys():
                del my_variables[key]

    for k, v in my_types_children.items():
        for key in v.keys():
            if key in my_objects.keys():
                del my_objects[key]

    print('Creating a new UA Node Set')
    myNodeSet = UANodeSet(node_set_attributes)

    # build base types
    print('Building custom UA types')
    my_ua_types = OrderedDict()
    for k, v in my_types.items():
        my_ua_types[k] = UAObjectType(k, children=my_types_children[v['name']])

    # add types to node set
    print('Adding the custom types to the node set')
    for k, ua_type in my_ua_types.items():
        myNodeSet.add_object(ua_type)

    # build objects
    print('Building remaining objects')
    my_ua_objects = OrderedDict()
    for k, o in my_objects.items():
        if o['instance type'] in my_types.keys():
            if o['parent'] in my_ua_objects.keys():
                my_ua_objects[o['name']] = UAObject(my_ua_objects[o['parent']].full_node_id, o['name'], object_type=my_ua_types[o['instance type']], child_values=o['child values'])
            else:
                my_ua_objects[o['name']] = UAObject(o['parent'], o['name'], object_type=my_ua_types[o['instance type']], child_values=o['child values'])
        else:
            if o['parent'] in my_ua_objects.keys():
                my_ua_objects[o['name']] = UAObject(my_ua_objects[o['parent']].full_node_id, o['name'])
            else:
                my_ua_objects[o['name']] = UAObject(o['parent'], o['name'])

    # build variables
    for k, v in my_variables.items():
        if v['parent'] in my_ua_objects.keys():
            my_ua_objects[v['name']] = UAVariable(my_ua_objects[v['parent']].full_node_id, v['name'], v['data type'], value=v['value'])
        else:
            my_ua_objects[v['name']] = UAVariable(v['parent'], v['name'], v['data type'], value=v['value'])

    # add objects to node set
    print('Adding remaining objects to the node set')
    for k, o in my_ua_objects.items():
        myNodeSet.add_object(o)

    # myNodeSet.dump_etree()
    print('Exporting the node set to XML')
    myNodeSet.write(xml_filename)
