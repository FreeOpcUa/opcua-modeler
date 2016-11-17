Free OPC UA Modeler
===================

Free OPC UA Modeler is a tool for designing OPC UA address spaces. It uses OPC UA specified XML format which allows the produced XML to be imported into any OPC UA SDK.

Basic features of the modeler work, but this is a work in progress.   
Bug reports and feature requests are welcome.

Current state and plans can be found here: https://github.com/FreeOpcUa/opcua-modeler/issues/3

![Screenshot](/screenshot.png?raw=true "Screenshot")

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
1. Clone python-opcua and set python to include the opcua directory. for ex: export PYTHONPATH=~/python-opcua/
2. Clone opcua-modeler
3. Cone opcua-widgets as uawidgets in opcua-modeler directory
4. type 'python3 app.pyæ or 'make run'

