import csvtoxml.builder as builder

CSV_FILENAME = 'csv-to-xml-example-config.csv'
XML_FILENAME = 'csv-to-xml-example-model.xml'

# TODO make into command line tool
builder.csv_to_xml(CSV_FILENAME, XML_FILENAME)
