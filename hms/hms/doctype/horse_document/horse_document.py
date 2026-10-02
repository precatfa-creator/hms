# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from hms.hms import documents


class HorseDocument(Document):
	def validate(self):
		category = documents.get_category(self.category)
		if not category:
			frappe.throw(_("Unknown document category {0}").format(self.category))

		horse = self.horse_values()
		if not documents.is_applicable(category, horse):
			frappe.throw(
				_("{0} does not apply to {1}: it is a {2} {3} horse.").format(
					self.category, self.horse, horse.get("origin"), horse.get("gender")
				)
			)

		self.check_limit(category)
		self.clear_unused_details(category)
		self.validate_season()
		self.is_complete = 1 if documents.document_is_complete(self.as_dict(), category) else 0

	def horse_values(self):
		return frappe.db.get_value(
			"Horse", self.horse,
			["origin", "gender", "birthplace_country"], as_dict=True,
		) or {}

	def check_limit(self, category):
		existing = frappe.db.count("Horse Document", {
			"horse": self.horse,
			"category": self.category,
			"name": ("!=", self.name or ""),
		})
		if documents.over_limit(category, existing):
			frappe.throw(
				_("{0} already has {1} document(s) of category {2}, which is the limit.").format(
					self.horse, existing, self.category
				)
			)

	def clear_unused_details(self, category):
		"""A season on a Marking is noise, and it would print.

		``notes`` is spared: a category that does not ask for one is no reason
		to throw away something a user typed.
		"""
		for flag, field in documents.COMPANIONS.items():
			if field != "notes" and not category.get(flag):
				self.set(field, None)

	def validate_season(self):
		if not self.season:
			return
		self.season = self.season.strip()
		if not (self.season.isdigit() and len(self.season) == 4
		        and 1900 <= int(self.season) <= getdate().year + 1):
			frappe.throw(_("Season must be a year, e.g. {0}").format(getdate().year))

	def on_update(self):
		documents.recalculate(self.horse)

	def after_delete(self):
		documents.recalculate(self.horse)
