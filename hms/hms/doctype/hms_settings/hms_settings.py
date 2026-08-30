# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from hms.api.legacy_sync import apply_schedule


class HMSSettings(Document):
	def validate(self):
		if self.sync_frequency == "Monthly":
			day = cint(self.sync_day_of_month)
			if not 1 <= day <= 28:
				frappe.throw(_("The day of the month has to be between 1 and 28, "
				               "so the sync never skips February."))

	def on_update(self):
		self.next_sync_on = apply_schedule(self)
		self.db_set("next_sync_on", self.next_sync_on, update_modified=False)
