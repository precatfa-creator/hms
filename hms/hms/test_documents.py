# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import unittest

from hms.hms.documents import (
	COMPLETED,
	DOC_COMPANIONS,
	NOT_YET,
	PARTIAL,
	REQUIRED,
	compute_status,
	is_complete,
)


def fill(doc, *keys):
	for key in keys:
		doc[f"doc_{key}"] = "/files/test.pdf"
		for field in DOC_COMPANIONS[key]:
			doc[field] = "filled"
	return doc


class TestDocumentStatus(unittest.TestCase):
	def test_empty_is_not_yet(self):
		self.assertEqual(compute_status({"origin": "Local"}), NOT_YET)
		self.assertEqual(compute_status({"origin": "Imported"}), NOT_YET)

	def test_attachment_without_companion_is_incomplete(self):
		doc = {"origin": "Local", "doc_registration_form": "/files/test.pdf"}
		self.assertFalse(is_complete(doc, "registration_form"))
		self.assertEqual(compute_status(doc), NOT_YET)

		doc["doc_registration_date"] = "2026-01-01"
		self.assertTrue(is_complete(doc, "registration_form"))
		self.assertEqual(compute_status(doc), PARTIAL)

	def test_companion_without_attachment_is_incomplete(self):
		doc = {"origin": "Local", "doc_registration_date": "2026-01-01"}
		self.assertFalse(is_complete(doc, "registration_form"))
		self.assertEqual(compute_status(doc), NOT_YET)

	def test_both_marking_companions_are_needed(self):
		doc = {"origin": "Local", "doc_marking": "/files/test.pdf", "doc_marking_by": "Dr. A"}
		self.assertFalse(is_complete(doc, "marking"))
		doc["doc_marking_date"] = "2026-01-01"
		self.assertTrue(is_complete(doc, "marking"))

	def test_all_required_local_documents_complete(self):
		doc = fill({"origin": "Local"}, *REQUIRED["Local"])
		self.assertEqual(compute_status(doc), COMPLETED)

	def test_all_required_imported_documents_complete(self):
		doc = fill({"origin": "Imported"}, *REQUIRED["Imported"])
		self.assertEqual(compute_status(doc), COMPLETED)

	def test_required_set_depends_on_origin(self):
		"""A complete local set is only partial for an imported horse and the other way round."""
		local = fill({"origin": "Local"}, *REQUIRED["Local"])
		self.assertEqual(compute_status(dict(local, origin="Imported")), PARTIAL)

		imported = fill({"origin": "Imported"}, *REQUIRED["Imported"])
		self.assertEqual(compute_status(dict(imported, origin="Local")), PARTIAL)

	def test_one_missing_required_document_is_partial(self):
		for missing in REQUIRED["Local"]:
			keys = [key for key in REQUIRED["Local"] if key != missing]
			doc = fill({"origin": "Local"}, *keys)
			self.assertEqual(compute_status(doc), PARTIAL, f"missing {missing}")

	def test_optional_documents_do_not_change_status(self):
		optional = set(DOC_COMPANIONS) - set(REQUIRED["Local"])
		doc = fill({"origin": "Local"}, *optional)
		self.assertEqual(compute_status(doc), NOT_YET)

		full = fill({"origin": "Local"}, *REQUIRED["Local"])
		self.assertEqual(compute_status(fill(full, *optional)), COMPLETED)

	def test_missing_origin_falls_back_to_local(self):
		doc = fill({}, *REQUIRED["Local"])
		self.assertEqual(compute_status(doc), COMPLETED)
		self.assertEqual(compute_status({}), NOT_YET)
