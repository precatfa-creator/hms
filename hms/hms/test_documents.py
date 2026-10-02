# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

"""The document rules, exercised without a database.

Every rule here is decided by a Horse Document Category row, so the fixtures
below stand in for those rows. The shipped categories come from the documents
mapping and live in ``hms/fixtures/horse_document_category.json``.
"""

import unittest

from hms.hms.documents import (
	COMPLETED,
	NOT_YET,
	PARTIAL,
	compute_status,
	document_is_complete,
	is_applicable,
	is_required,
	over_limit,
)


def category(name, **kw):
	base = {
		"category": name, "disabled": 0,
		"applies_to_local": 1, "required_for_local": 0,
		"applies_to_imported": 1, "required_for_imported": 0,
		"applies_to_sex": "All", "applies_to_breed": "All",
		"applies_to_country": None, "max_count": 1,
	}
	base.update(kw)
	return base


# the shipped set, trimmed to what these tests turn on
CATEGORIES = [
	category("Registration Form", required_for_local=1, required_for_imported=1,
	         needs_document_date=1),
	category("Breeding Certificate", required_for_local=1, applies_to_imported=0,
	         needs_reference_no=1),
	category("DNA Result / Card", required_for_local=1, required_for_imported=1,
	         needs_doc_status=1),
	category("Marking", required_for_local=1, needs_document_date=1,
	         needs_reference_no=1),
	category("Owner ID", required_for_local=1, required_for_imported=1, max_count=0,
	         needs_document_date=1),
	category("Passport", applies_to_local=0, required_for_imported=1,
	         needs_reference_no=1),
	category("Export Certificate", required_for_imported=1, max_count=0,
	         needs_document_date=1, needs_reference_no=1),
	category("Covering Certificate", applies_to_sex="Females", max_count=0,
	         needs_season=1),
	category("Covering Agreement", applies_to_sex="Males", max_count=0,
	         needs_season=1),
	category("Others", max_count=0, needs_notes=1),
]

BY_NAME = {c["category"]: c for c in CATEGORIES}

LOCAL_MARE = {"origin": "Local", "gender": "Broodmare", "breed": "Arabian"}
IMPORTED_STALLION = {"origin": "Imported", "gender": "Stallion", "breed": "Arabian"}


def required_for(horse):
	return {c["category"] for c in CATEGORIES if is_required(c, horse)}


class TestApplicability(unittest.TestCase):
	def test_origin_narrows(self):
		self.assertFalse(is_applicable(BY_NAME["Passport"], LOCAL_MARE))
		self.assertTrue(is_applicable(BY_NAME["Passport"], IMPORTED_STALLION))
		self.assertTrue(is_applicable(BY_NAME["Breeding Certificate"], LOCAL_MARE))
		self.assertFalse(is_applicable(BY_NAME["Breeding Certificate"], IMPORTED_STALLION))

	def test_sex_narrows(self):
		self.assertTrue(is_applicable(BY_NAME["Covering Certificate"], LOCAL_MARE))
		self.assertFalse(is_applicable(BY_NAME["Covering Certificate"], IMPORTED_STALLION))
		self.assertTrue(is_applicable(BY_NAME["Covering Agreement"], IMPORTED_STALLION))
		self.assertFalse(is_applicable(BY_NAME["Covering Agreement"], LOCAL_MARE))

	def test_gelding_counts_as_male(self):
		gelding = dict(LOCAL_MARE, gender="Gelding")
		self.assertTrue(is_applicable(BY_NAME["Covering Agreement"], gelding))
		self.assertFalse(is_applicable(BY_NAME["Covering Certificate"], gelding))

	def test_breed_narrows(self):
		tb_only = category("TB Only", applies_to_breed="Thoroughbred")
		self.assertFalse(is_applicable(tb_only, LOCAL_MARE))
		self.assertTrue(is_applicable(tb_only, dict(LOCAL_MARE, breed="Thoroughbred")))

	def test_country_narrows(self):
		libya_only = category("Libya Only", applies_to_country="Libya")
		self.assertFalse(is_applicable(libya_only, LOCAL_MARE))
		self.assertTrue(
			is_applicable(libya_only, dict(LOCAL_MARE, birthplace_country="Libya")))

	def test_disabled_applies_to_nobody(self):
		retired = category("Retired", disabled=1, required_for_local=1)
		self.assertFalse(is_applicable(retired, LOCAL_MARE))
		self.assertFalse(is_required(retired, LOCAL_MARE))


class TestRequired(unittest.TestCase):
	def test_local_starred_set(self):
		self.assertEqual(required_for(LOCAL_MARE), {
			"Registration Form", "Breeding Certificate", "DNA Result / Card",
			"Marking", "Owner ID",
		})

	def test_imported_starred_set(self):
		# Marking applies to an imported horse but is not starred for it
		self.assertEqual(required_for(IMPORTED_STALLION), {
			"Registration Form", "DNA Result / Card", "Owner ID",
			"Passport", "Export Certificate",
		})
		self.assertTrue(is_applicable(BY_NAME["Marking"], IMPORTED_STALLION))

	def test_optional_stays_optional(self):
		self.assertFalse(is_required(BY_NAME["Covering Certificate"], LOCAL_MARE))
		self.assertFalse(is_required(BY_NAME["Others"], LOCAL_MARE))


class TestCompleteness(unittest.TestCase):
	def test_attachment_alone_is_not_a_document(self):
		reg = BY_NAME["Registration Form"]
		self.assertFalse(document_is_complete({}, reg))
		self.assertFalse(document_is_complete({"attachments": [{"file": "/files/a.pdf"}]}, reg))

	def test_companion_without_attachment_is_incomplete(self):
		reg = BY_NAME["Registration Form"]
		self.assertFalse(document_is_complete({"document_date": "2026-01-01"}, reg))

	def test_every_companion_counts(self):
		marking = BY_NAME["Marking"]
		document = {"attachments": [{"file": "/files/a.pdf"}], "reference_no": "Dr. A"}
		self.assertFalse(document_is_complete(document, marking))
		document["document_date"] = "2026-01-01"
		self.assertTrue(document_is_complete(document, marking))

	def test_category_without_companions_needs_only_the_file(self):
		plain = category("Plain")
		self.assertTrue(document_is_complete({"attachments": [{"file": "/files/a.pdf"}]}, plain))


class TestStatus(unittest.TestCase):
	def test_empty_is_not_yet(self):
		self.assertEqual(compute_status(LOCAL_MARE, CATEGORIES, set()), NOT_YET)
		self.assertEqual(compute_status(IMPORTED_STALLION, CATEGORIES, set()), NOT_YET)

	def test_partial_then_complete(self):
		done = {"Registration Form"}
		self.assertEqual(compute_status(LOCAL_MARE, CATEGORIES, done), PARTIAL)
		self.assertEqual(
			compute_status(LOCAL_MARE, CATEGORIES, required_for(LOCAL_MARE)), COMPLETED)

	def test_each_missing_one_is_partial(self):
		required = required_for(LOCAL_MARE)
		for missing in required:
			self.assertEqual(
				compute_status(LOCAL_MARE, CATEGORIES, required - {missing}), PARTIAL,
				f"missing {missing} should not read as Completed")

	def test_optional_documents_never_complete_anything(self):
		self.assertEqual(compute_status(LOCAL_MARE, CATEGORIES, {"Others"}), NOT_YET)

	def test_local_set_does_not_complete_an_imported_horse(self):
		self.assertEqual(
			compute_status(IMPORTED_STALLION, CATEGORIES, required_for(LOCAL_MARE)),
			PARTIAL)


class TestLimits(unittest.TestCase):
	def test_single_upload_category(self):
		self.assertFalse(over_limit(BY_NAME["Registration Form"], 0))
		self.assertTrue(over_limit(BY_NAME["Registration Form"], 1))

	def test_zero_means_unlimited(self):
		# a horse may carry one owner ID per co-owner
		self.assertFalse(over_limit(BY_NAME["Owner ID"], 99))
