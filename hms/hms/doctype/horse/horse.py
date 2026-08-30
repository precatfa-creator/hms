# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from hms.hms.documents import set_status


class Horse(Document):
	def validate(self):
		set_status(self)
