# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class OwnerChangeForm(Document):
	def validate(self):
		self.validate_new_owner()

	def validate_new_owner(self):
		"""Owners are free text now, so match on the id first and the name second."""
		same_id = (
			self.new_owner_national_id
			and self.new_owner_national_id == self.current_owner_national_id
		)
		same_name = (
			self.new_owner_name_en
			and self.new_owner_name_en == self.current_owner_name_en
		)
		if same_id or same_name:
			frappe.throw(_("The new owner is already the current owner of {0}").format(self.horse))
