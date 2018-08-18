Free OPC UA Modeler
===================


[![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/FreeOpcUa/opcua-modeler/badges/quality-score.png?b=master)](https://scrutinizer-ci.com/g/FreeOpcUa/opcua-modeler/?branch=master)
[![Build Status](https://travis-ci.org/FreeOpcUa/opcua-modeler.svg?branch=master)](https://travis-ci.org/FreeOpcUa/opcua-modeler)
[![Build Status](https://travis-ci.org/FreeOpcUa/opcua-widgets.svg?branch=master)](https://travis-ci.org/FreeOpcUa/opcua-widgets)


Free OPC UA Modeler is a tool for designing OPC UA address spaces. It uses OPC UA specified XML format which allows the produced XML to be imported into any OPC UA SDK.

Basic features of the modeler work, but this is a work in progress.   
Bug reports and feature requests are welcome.

Ïn the background the modeler uses an OPC UA server which can be connected to. The server is either a python-opcua server (default) or the C based open65421 server. To use the open62541 backend, open65241.so must be available as well as the its python wrapper.

Current state and plans can be found here: https://github.com/FreeOpcUa/opcua-modeler/issues/3

![Screenshot](/screenshot.png?raw=true "Screenshot")

# Creating custom structures

The process of creatig custom structures is a bit different than in order modelers. Ideas and code to improve process is welcome

1. Create a new namespace (Only ONE namespace is required, namespace one will be used) 
2. create a new data type under DataType /  Structure
3. populate data type with new variables using correct data type
4. save

The new nodes under your custom Structure will not be saved in model but a new node called TypeDictionnay will be created and its value describe the custom nodes (As specified in UA specification). When reopening your model, the design nodes will be recreated on the fly and you can add/modify your custom structure

# How to Install  

*Note: PyQT 5 is required.*

### Linux:

1. Make sure python and python-pip is installed  
2. `pip3 install opcua-modeler`  
4. Run with: `opcua-modeler`  
  
### Windows:  

1. Install winpython https://winpython.github.io/  
2. Use pip to install opcua-modeler: `pip install opcua-modeler`  
3. Run via the script pip created: `YOUR_INSTALL_PATH\Python\Python35Python\Python35-32\Scripts\opcua-modeler.exe`  

To update to the latest release run: `pip install opcua-modeler --upgrade`

### Development version
1. git clone https://github.com/FreeOpcUa/python-opcua.git 
2. git clone https://github.com/FreeOpcUa/opcua-widgets.git
3. export PYTHONPATH=$PWD/python-opcua;$PWD/opcua-widgets  # let Python find the repositories
or set PYTHONPATH=%PYTHONPATH%;%cd%\python-opcua;%cd%\opcua-widgets on Windows
4. git clone https://github.com/FreeOpcUa/opcua-modeler.git 
5. cd opcua-modeler;
6. 'python3 app.py' # or 'make run'

