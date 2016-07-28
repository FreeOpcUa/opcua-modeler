CSV to XML

Python OPC UA address space builder which converts a basic configuration in CSV format to an OPC UA XML. The programming design was intended to model the XML schema.

See the example CSV for configuration.

What works:
*Creating Objects Types, Objects, and Variables
*Basic address space modelling with structure created by defining the parent
*Automatic Node Id creation (only integer ids)
*Custom Object types and creating instances of the object type (variables of an instance can get new values via 'child values' column)

Not supported:
*Folder objects
*Property objects
*Method objects
*String node ids  
*Custom namespaces

Notes:
*Code needs to be cleaned up; lots of code duplication that should be reduced by adding methods
*Defining node ids in csv isn't tested
