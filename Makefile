all:
	pyuic5 uamodeler/uamodeler_ui.ui -o uamodeler/uamodeler_ui.py
run:
	PYTHONPATH=$(shell pwd)
	python3 app.py
edit:
	qtcreator uamodeler/uamodeler_ui.ui
