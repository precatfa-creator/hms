# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms.hms.testing import make_horse, make_registration


class TestRegistrationFormforLocalHorses(FrappeTestCase):
	def test_fetched_fields(self):
		reg = make_registration()
		self.assertEqual(reg.owner_phone, "0912618821")
		self.assertEqual(reg.owner_city, "Tripoli")
		self.assertEqual(reg.origin, "Local")

	def test_pedigree_is_free_text(self):
		reg = make_registration()
		self.assertEqual(reg.sire_name_en, "Test Sire")
		self.assertEqual(reg.sire_registration_no, "LY-2015-00001")
		self.assertEqual(reg.dam_name_en, "Test Dam")
		self.assertEqual(reg.dam_origin, "Imported")

		reg.sire_registration_no = "GB-1998-12345"
		reg.save()
		self.assertEqual(reg.sire_registration_no, "GB-1998-12345")

	def test_form_can_point_at_its_horse(self):
		reg = make_registration()
		self.assertFalse(reg.horse)

		horse = make_horse("Registered Horse")
		reg.horse = horse.name
		reg.save()
		self.assertEqual(reg.horse, horse.name)

	def test_documents_and_status_belong_to_the_horse(self):
		"""Documents are Horse Document rows now, not fields on either doctype."""
		reg = make_registration()
		horse = make_horse("Documented Horse")
		self.assertTrue(horse.meta.has_field("documents_status"))
		self.assertFalse(horse.meta.has_field("doc_registration_form"))
		self.assertFalse(reg.meta.has_field("documents_status"))

		document = frappe.get_doc({
			"doctype": "Horse Document", "horse": horse.name,
			"category": "Registration Form", "attachments": [{"file": "/files/test.pdf"}],
			"document_date": "2026-01-01",
		}).insert()
		self.assertEqual(document.horse, horse.name)
		horse.reload()
		self.assertEqual(horse.documents_status, "Partially Completed")

	def test_print_format_renders(self):
		reg = make_registration()
		html = frappe.get_print(reg.doctype, reg.name,
		                        print_format="Local-Bred Horse Registration Form")
		self.assertIn("Studbook Department", html)
		self.assertIn("First Name", html)
		self.assertIn("Test Sire", html)
