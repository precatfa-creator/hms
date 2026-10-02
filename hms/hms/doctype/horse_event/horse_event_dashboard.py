# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

"""The Horse Event's Connections tab: what Create Transaction made from it."""


def get_data():
	return {
		# each of these points back through `source_event`
		"fieldname": "source_event",
		"transactions": [
			{"label": "Documents", "items": ["Horse Document"]},
			{
				"label": "Forms",
				"items": [
					"Registration Form for Local Horses",
					"Owner Change Form",
					"Name Change Form",
				],
			},
		],
	}
