# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms.hms.testing import make_horse


class TestNameChangeForm(FrappeTestCase):
	def setUp(self):
		self.horse = make_horse("Rename Horse")

	def rename(self, name_en="New Name", name_ar="الاسم الجديد"):
		return frappe.get_doc({
			"doctype": "Name Change Form",
			"horse": self.horse.name,
			"name_1_ar": name_ar,
			"name_1_en": name_en,
			"approved_name_ar": name_ar,
			"approved_name_en": name_en,
			"approval_date": "2026-07-01",
		}).insert()

	def test_horse_and_owner_data_are_fetched(self):
		doc = self.rename()
		self.assertEqual(doc.horse_name_en, "Rename Horse")
		self.assertEqual(doc.owner_name_en, self.horse.owner_name_en)
		self.assertEqual(doc.owner_phone, "0912618821")
		self.assertEqual(doc.color, self.horse.color)

	def test_documents_and_status_stay_on_the_horse(self):
		doc = self.rename()
		self.assertFalse(doc.meta.has_field("doc_registration_form"))
		self.assertFalse(doc.meta.has_field("status"))
		self.assertTrue(self.horse.meta.has_field("status"))

	def test_approved_name_is_required(self):
		doc = frappe.get_doc({
			"doctype": "Name Change Form",
			"horse": self.horse.name,
			"name_1_ar": "اسم",
			"name_1_en": "Name",
		})
		self.assertRaises(frappe.MandatoryError, doc.insert)

	def test_the_form_does_not_rename_the_horse(self):
		self.rename()
		self.horse.reload()
		self.assertEqual(self.horse.name_en, "Rename Horse")
		self.assertEqual(len(self.horse.name_history), 0)
