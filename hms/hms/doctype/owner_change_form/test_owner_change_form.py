# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms.hms.testing import make_horse, owner, pedigree


class TestOwnerChangeForm(FrappeTestCase):
	def setUp(self):
		self.horse = make_horse("Transfer Horse", owner_since="2026-01-01", **pedigree())

	def transfer(self, buyer="Buyer", date="2026-06-01", **kwargs):
		values = {
			"doctype": "Owner Change Form",
			"horse": self.horse.name,
			"new_owner_name_ar": "المشتري",
			"new_owner_name_en": buyer,
			"new_owner_national_id": "654321",
			"new_owner_city": "Benghazi",
			"new_owner_phone": "0913447120",
			"new_ownership_date": date,
			"legal_contract_officer": "Officer X",
			"endorsement_date": date,
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert()

	def test_current_owner_and_horse_data_are_fetched(self):
		doc = self.transfer()
		self.assertEqual(doc.current_owner_name_en, self.horse.owner_name_en)
		self.assertEqual(doc.current_owner_national_id, self.horse.owner_national_id)
		self.assertEqual(doc.current_owner_phone, "0912618821")
		self.assertEqual(str(doc.current_ownership_date), "2026-01-01")
		self.assertEqual(doc.horse_name_en, self.horse.name_en)
		self.assertEqual(doc.gender, self.horse.gender)
		self.assertEqual(doc.origin, "Local")

	def test_pedigree_is_fetched_as_text(self):
		doc = self.transfer()
		self.assertEqual(doc.sire_name_en, "Test Sire")
		self.assertEqual(doc.sire_registration_no, "LY-2015-00001")
		self.assertEqual(doc.dam_registration_no, "LY-2016-00002")

	def test_documents_and_status_stay_on_the_horse(self):
		doc = self.transfer()
		self.assertFalse(doc.meta.has_field("doc_registration_form"))
		self.assertFalse(doc.meta.has_field("status"))
		self.assertTrue(self.horse.meta.has_field("status"))

	def test_transfer_to_the_current_owner_is_rejected(self):
		doc = frappe.get_doc({
			"doctype": "Owner Change Form",
			"horse": self.horse.name,
			"new_owner_name_en": self.horse.owner_name_en,
			"new_owner_national_id": self.horse.owner_national_id,
			"new_ownership_date": "2026-06-01",
		})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_the_form_does_not_touch_the_horse(self):
		self.transfer()
		self.horse.reload()
		self.assertEqual(self.horse.owner_name_en, "Test Owner")
		self.assertEqual(len(self.horse.ownership_history), 0)

	def test_print_format_renders(self):
		doc = self.transfer()
		html = frappe.get_print(doc.doctype, doc.name,
		                        print_format="Horse Transfer of Ownership Form")
		self.assertIn("Transferor Information", html)
		self.assertIn("Buyer", html)
		self.assertIn("Test Owner", html)
