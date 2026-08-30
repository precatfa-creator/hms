"""Factories shared by the HMS tests. Not a test module itself."""

import frappe

from hms.hms.documents import DOC_COMPANIONS, REQUIRED

COLORS = {"Grey": "#B2BEB5", "Bay": "#7B3F00", "Black": "#000000", "Chestnut": "#954535"}


def ensure_color(name="Bay"):
	if not frappe.db.exists("Color", name):
		frappe.get_doc({"doctype": "Color", "name": name, "color": COLORS.get(name, "#000000")}).insert()
	return name


def owner(prefix="owner", name_en="Test Owner"):
	"""Owner / breeder values as the studbook API would deliver them."""
	return {
		f"{prefix}_name_ar": "مالك تجريبي",
		f"{prefix}_name_en": name_en,
		f"{prefix}_national_id": "123456",
		f"{prefix}_city": "Tripoli",
		f"{prefix}_address": "Sidi Almasri St",
		f"{prefix}_phone": "0912618821",
	}


def pedigree():
	"""Sire and dam data as the studbook API would deliver it."""
	return {
		"sire_name_ar": "الاب",
		"sire_name_en": "Test Sire",
		"sire_registration_no": "LY-2015-00001",
		"sire_origin": "Local",
		"sire_date_of_birth": "2015-03-01",
		"sire_place_of_birth": "Tripoli",
		"sire_color": "Bay",
		"sire_breed": "Arabian",
		"sire_microchip_no": "985000000000001",
		"dam_name_ar": "الام",
		"dam_name_en": "Test Dam",
		"dam_registration_no": "LY-2016-00002",
		"dam_origin": "Imported",
		"dam_date_of_birth": "2016-04-01",
		"dam_place_of_birth": "Cairo",
		"dam_color": "Grey",
		"dam_breed": "Arabian",
		"dam_microchip_no": "985000000000002",
	}


def documents(*keys):
	"""Fully filled document fields for the given document keys."""
	values = {}
	for key in keys:
		values[f"doc_{key}"] = "/files/test.pdf"
		for field in DOC_COMPANIONS[key]:
			values[field] = "2026-01-01" if field.endswith("_date") else "test"
	if "dna_card" in keys:
		values["doc_dna_status"] = "Approved"
	return values


def make_horse(name_en="Test Horse", gender="Male", **kwargs):
	values = {
		"doctype": "Horse",
		"name_ar": "جواد تجريبي",
		"name_en": name_en,
		"gender": gender,
		"origin": "Local",
		"color": ensure_color(),
		"breed": "Arabian",
		"date_of_birth": "2015-03-01",
		"place_of_birth": "Tripoli",
	}
	values.update(owner())
	values.update(kwargs)
	return frappe.get_doc(values).insert()


def complete_documents(horse):
	"""Attach every starred document of the horse's origin, so its status is Completed."""
	horse.update(documents(*REQUIRED[horse.origin or "Local"]))
	horse.save()
	return horse


def make_registration(**kwargs):
	values = {
		"doctype": "Registration Form for Local Horses",
		"gender": "Female",
		"color": ensure_color("Grey"),
		"breed": "Arabian",
		"date_of_birth": "2026-02-01",
		"place_of_birth": "Tripoli",
		"microchip_no": "985111222333444",
		"current_location": "Tripoli",
		"covering_location": "Local",
		"covering_date_1": "2025-03-01",
		"name_1_ar": "الاسم الاول",
		"name_1_en": "First Name",
		"name_2_ar": "الاسم الثاني",
		"name_2_en": "Second Name",
	}
	values.update(pedigree())
	values.update(owner("owner", "Registration Owner"))
	values.update(owner("breeder", "Registration Breeder"))
	values.update(kwargs)

	return frappe.get_doc(values).insert()
