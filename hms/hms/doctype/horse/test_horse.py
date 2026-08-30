# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms.hms.documents import REQUIRED
from hms.hms.testing import complete_documents, documents, make_horse, owner, pedigree


class TestHorse(FrappeTestCase):
	def test_status_is_recomputed_on_save(self):
		horse = make_horse("Status Horse")
		self.assertEqual(horse.status, "Not Yet")

		horse.doc_registration_form = "/files/test.pdf"
		horse.save()
		self.assertEqual(horse.status, "Not Yet", "attachment alone is not enough")

		horse.doc_registration_date = "2026-01-01"
		horse.save()
		self.assertEqual(horse.status, "Partially Completed")

		horse.update(documents(*REQUIRED["Local"]))
		horse.save()
		self.assertEqual(horse.status, "Completed")

	def test_imported_horse_needs_its_own_document_set(self):
		horse = make_horse("Imported Horse", origin="Imported")
		horse.update(documents(*REQUIRED["Local"]))
		horse.save()
		self.assertEqual(horse.status, "Partially Completed")

		horse.update(documents(*REQUIRED["Imported"]))
		horse.save()
		self.assertEqual(horse.status, "Completed")

	def test_complete_documents_helper_matches_the_origin(self):
		self.assertEqual(complete_documents(make_horse("Local One")).status, "Completed")
		self.assertEqual(
			complete_documents(make_horse("Imported One", origin="Imported")).status, "Completed"
		)

	def test_pedigree_is_free_text(self):
		"""Sire and dam are filled from the studbook API, not linked to Horse records."""
		horse = make_horse("Pedigree Horse", **pedigree())
		self.assertEqual(horse.sire_name_en, "Test Sire")
		self.assertEqual(horse.sire_registration_no, "LY-2015-00001")
		self.assertEqual(horse.dam_origin, "Imported")
		self.assertEqual(horse.dam_color, "Grey")

		# a registration number that is not a Horse record is accepted
		horse.sire_registration_no = "GB-1998-12345"
		horse.save()
		self.assertEqual(horse.sire_registration_no, "GB-1998-12345")

	def test_ownership_is_free_text(self):
		"""Owner and breeder come from the studbook API, they are not linked records."""
		horse = make_horse("Owned Horse", **owner("breeder", "Test Breeder"))
		self.assertEqual(horse.owner_name_en, "Test Owner")
		self.assertEqual(horse.owner_phone, "0912618821")
		self.assertEqual(horse.breeder_name_en, "Test Breeder")

		horse.owner_name_en = "Someone Not In Our Registry"
		horse.owner_national_id = "999999"
		horse.save()
		self.assertEqual(horse.owner_name_en, "Someone Not In Our Registry")

		self.assertFalse(horse.meta.has_field("horse_owner"))
		self.assertTrue(frappe.db.exists("Color", horse.color))

	def test_unknown_color_is_rejected(self):
		horse = make_horse("Color Horse")
		horse.color = "Not A Colour"
		self.assertRaises(frappe.LinkValidationError, horse.save)
