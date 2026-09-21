"""Factories shared by the HMS tests. Not a test module itself."""

import frappe

from hms.hms import documents

SHORT_NAMES = {"Grey": "gr.", "Bay": "b.", "Black": "bl.", "Chestnut": "ch."}


def ensure_country(name="Libya", is_local=True):
	if not frappe.db.exists("Studbook Country", name):
		frappe.get_doc({
			"doctype": "Studbook Country", "country_name": name,
			"alpha2": name[:2].upper(), "alpha3": name[:3].upper(),
			"numeric_code": str(abs(hash(name)) % 900 + 100),
			"is_local": 1 if is_local else 0,
		}).insert()
	return name


def ensure_color(name="Bay", breed="Arabian"):
	"""Horse Color is named "<color> (<breed>)": colors repeat per breed."""
	docname = f"{name} ({breed})"
	if not frappe.db.exists("Horse Color", docname):
		frappe.get_doc({
			"doctype": "Horse Color", "color_name": name,
			"short_name": SHORT_NAMES.get(name, name[:2].lower() + "."),
			"horse_breed": breed,
		}).insert()
	return docname


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


def add_document(horse, category, **kwargs):
	"""One Horse Document, with whatever details its category asks for."""
	values = {
		"doctype": "Horse Document",
		"horse": horse.name if hasattr(horse, "name") else horse,
		"category": category,
		"attachment": "/files/test.pdf",
	}
	rules = documents.get_category(category) or {}
	for flag, field in documents.COMPANIONS.items():
		if not rules.get(flag):
			continue
		if field == "doc_status":
			values[field] = "Approved"
		elif field.endswith("date"):
			values[field] = "2026-01-01"
		else:
			values[field] = "test"
	values.update(kwargs)
	return frappe.get_doc(values).insert()


def make_horse(name_en="Test Horse", gender="Male", origin="Local", **kwargs):
	"""Origin is derived from the birthplace country, so that is what is set."""
	values = {
		"doctype": "Horse",
		"name_ar": "جواد تجريبي",
		"name_en": name_en,
		"gender": gender,
		"breed": "Arabian",
		"birthplace_country": ensure_country("Libya", True) if origin == "Local"
		else ensure_country("Egypt", False),
		"color": ensure_color(),
		"date_of_birth": "2015-03-01",
		"place_of_birth": "Tripoli",
	}
	values.update(owner())
	values.update(kwargs)
	return frappe.get_doc(values).insert()


def complete_documents(horse):
	"""Add every starred document this horse needs, so it reads as Completed."""
	values = horse.as_dict()
	for category in documents.get_categories():
		name = category["category"]
		if not documents.is_required(category, values):
			continue
		if frappe.db.exists("Horse Document", {"horse": horse.name, "category": name}):
			# already added by the test; adding a second would hit max_count
			continue
		add_document(horse, name)
	horse.reload()
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
