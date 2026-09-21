# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms.hms.testing import (
	add_document,
	complete_documents,
	ensure_country,
	make_horse,
	owner,
	pedigree,
)


class TestHorseDocuments(FrappeTestCase):
	def test_status_is_recomputed_as_documents_arrive(self):
		horse = make_horse("Status Horse")
		self.assertEqual(horse.documents_status, "Not Yet")

		# an attachment on its own does not satisfy a category that wants a date
		partial = add_document(horse, "Registration Form", document_date=None)
		self.assertFalse(partial.is_complete)
		horse.reload()
		self.assertEqual(horse.documents_status, "Not Yet")

		partial.document_date = "2026-01-01"
		partial.save()
		horse.reload()
		self.assertEqual(horse.documents_status, "Partially Completed")

		complete_documents(horse)
		self.assertEqual(horse.documents_status, "Completed")

	def test_imported_horse_needs_its_own_document_set(self):
		local = make_horse("Local For Compare")
		complete_documents(local)
		self.assertEqual(local.documents_status, "Completed")

		imported = make_horse("Imported Horse", origin="Imported")
		for category in ("Registration Form", "DNA Result / Card", "Owner ID"):
			add_document(imported, category)
		imported.reload()
		self.assertEqual(imported.documents_status, "Partially Completed",
		                 "an imported horse still owes a passport and export certificate")

		complete_documents(imported)
		self.assertEqual(imported.documents_status, "Completed")

	def test_deleting_a_document_drops_the_status_back(self):
		horse = complete_documents(make_horse("Deleting Horse"))
		self.assertEqual(horse.documents_status, "Completed")

		document = frappe.get_all("Horse Document",
		                          filters={"horse": horse.name,
		                                   "category": "Registration Form"},
		                          pluck="name")[0]
		frappe.delete_doc("Horse Document", document)
		horse.reload()
		self.assertEqual(horse.documents_status, "Partially Completed")

	def test_a_category_that_does_not_apply_is_refused(self):
		mare = make_horse("Refusing Mare", gender="Broodmare")
		self.assertRaises(frappe.ValidationError,
		                  add_document, mare, "Covering Agreement")

	def test_the_upload_limit_is_enforced(self):
		horse = make_horse("Limited Horse")
		add_document(horse, "Registration Form")
		self.assertRaises(frappe.ValidationError,
		                  add_document, horse, "Registration Form")

	def test_a_category_with_no_limit_takes_many(self):
		horse = make_horse("Many IDs Horse")
		add_document(horse, "Owner ID")
		add_document(horse, "Owner ID")
		self.assertEqual(
			frappe.db.count("Horse Document",
			                {"horse": horse.name, "category": "Owner ID"}), 2)


class TestHorseFields(FrappeTestCase):
	def test_origin_is_derived_from_the_birthplace_country(self):
		"""StudLib has no origin column; it falls out of country.local."""
		local = make_horse("Derived Local")
		self.assertEqual(local.birthplace_country, "Libya")
		self.assertEqual(local.origin, "Local")

		imported = make_horse("Derived Imported", origin="Imported")
		self.assertEqual(imported.origin, "Imported")

		imported.birthplace_country = ensure_country("Libya", True)
		imported.save()
		self.assertEqual(imported.origin, "Local", "changing the country changes the origin")

	def test_life_status_follows_the_date_of_death(self):
		horse = make_horse("Mortal Horse")
		self.assertEqual(horse.life_status, "Alive")

		horse.date_of_death = "2026-01-01"
		horse.save()
		self.assertEqual(horse.life_status, "Deceased")

		horse.date_of_death = None
		horse.save()
		self.assertEqual(horse.life_status, "Alive")

	def test_registration_status_is_the_studbook_workflow(self):
		"""`status` is StudLib's registration workflow, not our document tally."""
		horse = make_horse("Workflow Horse", status="Waiting for Laboratory")
		self.assertEqual(horse.status, "Waiting for Laboratory")
		self.assertEqual(horse.documents_status, "Not Yet")

	def test_the_extended_sex_values_are_accepted(self):
		for sex in ("Stallion", "Broodmare", "Cryptorchid", "Monorchid"):
			horse = make_horse(f"Sexed {sex}", gender=sex)
			self.assertEqual(horse.gender, sex)

	def test_pedigree_links_and_free_text_coexist(self):
		"""The Links carry StudLib's father_id/mother_id; the flat block still
		prints, and holds parents that have no Horse record here."""
		sire = make_horse("Linked Sire", gender="Stallion")
		dam = make_horse("Linked Dam", gender="Broodmare")
		foal = make_horse("Linked Foal", sire=sire.name, dam=dam.name, **pedigree())

		self.assertEqual(foal.sire, sire.name)
		self.assertEqual(foal.dam, dam.name)
		self.assertEqual(foal.sire_name_en, "Test Sire")
		self.assertEqual(foal.dam_origin, "Imported")

		# a foreign parent with no record here is still accepted as text
		foal.sire = None
		foal.sire_registration_no = "GB-1998-12345"
		foal.save()
		self.assertEqual(foal.sire_registration_no, "GB-1998-12345")

	def test_a_horse_can_have_several_owners_at_once(self):
		horse = make_horse("Syndicate Horse")
		for name_en in ("Party One", "Party Two"):
			party = frappe.get_doc({
				"doctype": "Horse Owner", "owner_name_ar": name_en,
				"owner_name_en": name_en,
			}).insert()
			horse.append("owners", {"party": party.name})
		horse.save()
		self.assertEqual(len(horse.owners), 2)

	def test_ownership_is_still_free_text_for_the_paper_forms(self):
		horse = make_horse("Owned Horse", **owner("breeder", "Test Breeder"))
		self.assertEqual(horse.owner_name_en, "Test Owner")
		self.assertEqual(horse.breeder_name_en, "Test Breeder")

		horse.owner_name_en = "Someone Not In Our Registry"
		horse.save()
		self.assertEqual(horse.owner_name_en, "Someone Not In Our Registry")

	def test_color_is_a_breed_scoped_link(self):
		horse = make_horse("Color Horse")
		self.assertTrue(frappe.db.exists("Horse Color", horse.color))
		self.assertEqual(
			frappe.db.get_value("Horse Color", horse.color, "horse_breed"), "Arabian")

		horse.color = "Not A Colour"
		self.assertRaises(frappe.LinkValidationError, horse.save)


class TestHorseConnections(FrappeTestCase):
	def test_the_connections_tab_is_wired(self):
		"""Frappe loads horse_dashboard.py by filename; a function in the
		controller is silently ignored, which is how this was wrong once."""
		frappe.clear_cache(doctype="Horse")
		data = frappe.get_meta("Horse").get_dashboard_data()

		groups = {g["label"]: g["items"] for g in data.get("transactions", [])}
		self.assertEqual(data.get("fieldname"), "horse")
		self.assertEqual(groups["Documents"], ["Horse Document"])
		self.assertEqual(groups["Events"], ["Horse Event"])
		self.assertIn("Owner Change Form", groups["Forms"])

		# every linked doctype really does have the field the tab counts on
		for items in groups.values():
			for doctype in items:
				self.assertTrue(frappe.get_meta(doctype).has_field("horse"),
				                f"{doctype} has no `horse` field to link back on")

	def test_a_document_shows_up_under_its_horse(self):
		from frappe.desk.notifications import get_open_count

		horse = make_horse("Connected Horse")
		add_document(horse, "Registration Form")

		found = get_open_count("Horse", horse.name)["count"]["external_links_found"]
		counts = {row["doctype"]: row["count"] for row in found}
		self.assertEqual(counts["Horse Document"], 1)
		self.assertEqual(counts["Horse Event"], 0)
