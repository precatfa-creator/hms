# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

"""The Horse's Connections tab.

The Documents tab used to hold the attachments themselves. They are Horse
Document records now, and the events and paper forms hang off the horse the
same way, so all three are reached from here instead.

Frappe loads this by filename -- ``<doctype>_dashboard.py`` with ``get_data``.
A function in the controller is not picked up.
"""


def get_data():
	return {
		# every one of these links back through a field called `horse`, so no
		# non_standard_fieldnames entry is needed
		"fieldname": "horse",
		"transactions": [
			{"label": "Documents", "items": ["Horse Document"]},
			{"label": "Events", "items": ["Horse Event"]},
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
