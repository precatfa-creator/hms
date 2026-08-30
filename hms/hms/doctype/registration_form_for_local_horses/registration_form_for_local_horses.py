# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class RegistrationFormforLocalHorses(Document):
	def validate(self):
		self.origin = "Local"
