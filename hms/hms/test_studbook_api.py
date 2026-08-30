# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms.api.studbook import FIELD_MAP, PARENT_FIELDS, get_horse, get_parent, search_horses
from hms.hms.testing import make_horse, owner, pedigree


class TestStudbookApi(FrappeTestCase):
	"""With no API configured the bridge answers from this site's own horses."""

	def setUp(self):
		self.horse = make_horse("Al Wathba Test", "Female", name_ar="الوثبة اختبار",
		                        **pedigree(), **owner("breeder", "Breeder Test"))

	def test_search_matches_either_language(self):
		for txt in ("Al Wathba", "الوثبة", "a"):
			refs = [row["ref"] for row in search_horses(txt)]
			self.assertIn(self.horse.name, refs, f"searching {txt!r}")

	def test_search_returns_both_names_for_the_dropdown(self):
		row = next(r for r in search_horses("Al Wathba Test") if r["ref"] == self.horse.name)
		self.assertEqual(row["name_en"], "Al Wathba Test")
		self.assertEqual(row["name_ar"], "الوثبة اختبار")

	def test_empty_search_returns_nothing(self):
		self.assertEqual(search_horses(""), [])
		self.assertEqual(search_horses("   "), [])

	def test_fetch_fills_identity_pedigree_and_ownership(self):
		values = get_horse(self.horse.name)
		self.assertEqual(values["name_en"], "Al Wathba Test")
		self.assertEqual(values["gender"], "Female")
		self.assertEqual(values["sire_name_en"], "Test Sire")
		self.assertEqual(values["dam_registration_no"], "LY-2016-00002")
		self.assertEqual(values["owner_name_en"], "Test Owner")
		self.assertEqual(values["breeder_name_en"], "Breeder Test")

	def test_every_mapped_field_exists_on_horse(self):
		meta = frappe.get_meta("Horse")
		missing = [f for f in FIELD_MAP.values() if not meta.has_field(f)]
		self.assertEqual(missing, [])

	def test_unknown_reference_is_reported(self):
		self.assertRaises(frappe.ValidationError, get_horse, "LY-9999-99999")

	def test_picked_horse_becomes_a_sire_block(self):
		values = get_parent(self.horse.name, "sire")
		self.assertEqual(values["sire_name_en"], "Al Wathba Test")
		self.assertEqual(values["sire_name_ar"], "الوثبة اختبار")
		self.assertEqual(values["sire_registration_no"], self.horse.name)
		self.assertEqual(values["sire_origin"], self.horse.origin)
		self.assertEqual(values["sire_color"], self.horse.color)
		self.assertEqual(values["sire_breed"], self.horse.breed)

	def test_picked_horse_becomes_a_dam_block(self):
		values = get_parent(self.horse.name, "dam")
		self.assertEqual(values["dam_name_en"], "Al Wathba Test")
		self.assertEqual(values["dam_registration_no"], self.horse.name)
		# the dam block is the only one with these two on the registration form
		self.assertEqual(values["dam_life_status"], self.horse.life_status)
		self.assertTrue(all(key.startswith("dam_") for key in values))

	def test_parent_values_never_include_fields_the_doctype_lacks(self):
		meta = frappe.get_meta("Registration Form for Local Horses")
		for prefix in ("sire", "dam"):
			for fieldname in get_parent(self.horse.name, prefix):
				self.assertTrue(meta.has_field(fieldname), fieldname)

	def test_only_sire_and_dam_are_accepted(self):
		self.assertRaises(frappe.ValidationError, get_parent, self.horse.name, "owner")

	def test_every_parent_field_exists_on_the_horse_doctype(self):
		meta = frappe.get_meta("Horse")
		missing = [f"sire_{suffix}" for suffix in PARENT_FIELDS.values()
		           if not meta.has_field(f"sire_{suffix}")]
		self.assertEqual(missing, ["sire_life_status", "sire_current_location"])
