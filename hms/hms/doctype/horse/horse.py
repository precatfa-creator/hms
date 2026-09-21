# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from hms.hms.documents import set_status


class Horse(Document):
	def validate(self):
		self.set_origin()
		self.set_life_status()
		set_status(self)

	def set_origin(self):
		"""StudLib derives origin rather than storing it: a horse born in the
		one country flagged Local is Local, anything else is Imported."""
		if not self.birthplace_country:
			return
		is_local = frappe.db.get_value("Studbook Country", self.birthplace_country, "is_local")
		self.origin = "Local" if is_local else "Imported"

	def set_life_status(self):
		self.life_status = "Deceased" if self.date_of_death else "Alive"

