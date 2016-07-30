all:
	pyuic5 uamodeler/uamodeler_ui.ui -o uamodeler/uamodeler_ui.py
	pyrcc5 uawidgets/resources.qrc -o uawidgets/resources.py

run:
	PYTHONPATH=$(shell pwd)
	python3 app.py
edit:
	qtcreator uamodeler/uamodeler_ui.ui
