from setuptools import setup, find_packages


setup(name="opcua-modeler",
      version="0.5.13",
      description="OPC-UA Address Space Modeler",
      author="Olivier R-D et al.",
      url='https://github.com/FreeOpcUa/opcua-modeler',
      packages=["uamodeler"],
      license="GNU General Public License",
      install_requires=["python-opcua>=0.98.13", "opcua-widgets < 0.6.0"],
      entry_points={'console_scripts':
                    ['opcua-modeler = uamodeler.uamodeler:main']
                    }
      )
