#!/usr/bin/env python3
"""Seed a site with demo studbook data: owners, horses at every document status,
and a few forms.

	cd frappe-bench/sites && ../env/bin/python ../apps/hms/scripts/seed_demo_data.py <site>

Attachments reuse public files already on the site, so nothing has to be
uploaded. Re-running is a no-op once the data is there.
"""

import random
import sys

import frappe

from hms.hms import documents

SITE = sys.argv[1] if len(sys.argv) > 1 else "losand.local"
MARKER = "Al Wathba"

OWNERS = [
	("محمد الفيتوري", "Mohamed Al Fituri", "119820304551", "طرابلس", "Tripoli", "0912618821"),
	("أحمد الزوي", "Ahmed Al Zwai", "119750112998", "بنغازي", "Benghazi", "0913447120"),
	("خالد المصراتي", "Khaled Al Misrati", "119880921436", "مصراتة", "Misrata", "0925510394"),
	("سالم بن نايل", "Salem Ben Nayel", "119690715220", "سبها", "Sebha", "0918872043"),
	("يوسف الترهوني", "Youssef Al Tarhouni", "119910408117", "الزاوية", "Zawiya", "0942203877"),
	("عبدالله السنوسي", "Abdullah Al Senussi", "119730629805", "طرابلس", "Tripoli", "0911903654"),
]

# name_ar, name_en, sex, colour, origin, year, place, documents
HORSES = [
	("الوثبة", "Al Wathba", "Female", "Grey", "Local", 2018, "طرابلس", "full"),
	("الشقب", "Al Shaqab", "Male", "Bay", "Local", 2016, "بنغازي", "full"),
	("نجم الليل", "Najm Al Layl", "Male", "Black", "Imported", 2015, "الدوحة", "full"),
	("صحراء", "Sahra", "Female", "Chestnut", "Local", 2019, "مصراتة", "full"),
	("الريح", "Al Reeh", "Male", "Bay", "Local", 2017, "الزاوية", "partial"),
	("جوهرة", "Jawhara", "Female", "Grey", "Imported", 2014, "القاهرة", "partial"),
	("عنترة", "Antara", "Male", "Black", "Local", 2020, "سبها", "partial"),
	("زمزم", "Zamzam", "Female", "Chestnut", "Local", 2021, "طرابلس", "partial"),
	("الفارس", "Al Faris", "Gelding", "Bay", "Local", 2013, "بنغازي", "partial"),
	("ليلى", "Layla", "Female", "Grey", "Local", 2022, "مصراتة", "none"),
	("الرعد", "Al Raad", "Male", "Black", "Imported", 2019, "الرياض", "none"),
	("سلمى", "Salma", "Female", "Bay", "Local", 2023, "طرابلس", "none"),
	("بشير", "Bashir", "Male", "Chestnut", "Local", 2012, "الزاوية", "full"),
	("الأمير", "Al Amir", "Male", "Grey", "Local", 2011, "بنغازي", "partial"),
]

SIRES = [
	("مرواس", "Marwas", "LY-2008-00114", "Local", "Bay"),
	("الجزيرة", "Al Jazeera", "QA-2007-00431", "Imported", "Grey"),
	("سيف النصر", "Saif Al Nasr", "LY-2009-00287", "Local", "Chestnut"),
	("برق", "Barq", "EG-2006-01120", "Imported", "Black"),
]
DAMS = [
	("نورة", "Noura", "LY-2010-00512", "Local", "Grey"),
	("الحرة", "Al Hurra", "LY-2011-00633", "Local", "Bay"),
	("مسك", "Misk", "SA-2009-00877", "Imported", "Chestnut"),
	("غزال", "Ghazal", "LY-2012-00741", "Local", "Grey"),
]


def ensure_countries():
	"""The sync brings these; a site that has never synced still needs them."""
	for name, alpha2, alpha3, code, local in (("Libya", "LY", "LBY", "434", 1),
	                                          ("Egypt", "EG", "EGY", "818", 0)):
		if not frappe.db.exists("Studbook Country", name):
			frappe.get_doc({"doctype": "Studbook Country", "country_name": name,
			                "alpha2": alpha2, "alpha3": alpha3,
			                "numeric_code": code, "is_local": local}).insert()
	for color in ("Bay", "Grey", "Black", "Chestnut"):
		if not frappe.db.exists("Horse Color", f"{color} (Arabian)"):
			frappe.get_doc({"doctype": "Horse Color", "color_name": color,
			                "short_name": color[:2].lower() + ".",
			                "horse_breed": "Arabian"}).insert()


def public_files():
	files = frappe.get_all(
		"File",
		filters={"is_folder": 0, "is_private": 0},
		fields=["file_url"],
		order_by="file_size desc",
		limit=12,
	)
	if not files:
		frappe.throw("No public files on this site to use as attachments")
	return [f.file_url for f in files]


DOCTORS = ["د. عمر الشريف", "د. ناصر الفقيه", "د. هالة بن عمران"]


def add_documents(horse, coverage, files, rng):
	"""Raise Horse Documents until the horse reads Completed, or part way.

	Which categories a horse needs is the Horse Document Category's decision,
	not this script's -- so it asks.
	"""
	if coverage == "none":
		return

	values = horse.as_dict()
	required = [c for c in documents.get_categories() if documents.is_required(c, values)]
	wanted = required if coverage == "full" else required[: rng.randint(1, len(required) - 1)]

	for category in wanted:
		row = {
			"doctype": "Horse Document",
			"horse": horse.name,
			"category": category["category"],
			"attachments": [{"file": rng.choice(files)}],
		}
		if category.get("needs_document_date"):
			row["document_date"] = f"202{rng.randint(3, 6)}-0{rng.randint(1, 9)}-1{rng.randint(0, 8)}"
		if category.get("needs_reference_no"):
			row["reference_no"] = (rng.choice(DOCTORS) if category["category"] == "Marking"
			                       else f"{rng.randint(1000, 9999)}/{rng.randint(2018, 2026)}")
		if category.get("needs_doc_status"):
			row["doc_status"] = "Approved"
		if category.get("needs_season"):
			row["season"] = str(rng.randint(2022, 2026))
		if category.get("needs_notes"):
			row["notes"] = "صورة من ملف الجواد"
		frappe.get_doc(row).insert()

	if coverage == "partial":
		# an optional document on top, which must not move the status
		frappe.get_doc({
			"doctype": "Horse Document", "horse": horse.name, "category": "Others",
			"attachments": [{"file": rng.choice(files)}], "notes": "صورة من ملف الجواد",
		}).insert()

	horse.reload()


def seed():
	rng = random.Random(20260726)
	files = public_files()

	def party(index, prefix):
		"""Owner / breeder values, the shape the studbook API delivers."""
		name_ar, name_en, national_id, city_ar, city_en, phone = OWNERS[index % len(OWNERS)]
		return {
			f"{prefix}_name_ar": name_ar,
			f"{prefix}_name_en": name_en,
			f"{prefix}_national_id": national_id,
			f"{prefix}_city": city_en,
			f"{prefix}_address": f"{city_ar} - شارع الجمهورية",
			f"{prefix}_phone": phone,
		}

	ensure_countries()
	horses = []
	for idx, (name_ar, name_en, sex, color, origin, year, place, coverage) in enumerate(HORSES):
		sire = SIRES[idx % len(SIRES)]
		dam = DAMS[idx % len(DAMS)]
		alive = name_en not in ("Bashir", "Al Amir")

		horse = frappe.get_doc({
			"doctype": "Horse",
			"name_ar": name_ar,
			"name_en": name_en,
			"gender": sex,
			# origin is derived from this, it is not stored
			"birthplace_country": "Libya" if origin == "Local" else "Egypt",
			"color": f"{color} (Arabian)",
			"breed": "Arabian",
			"status": rng.choice(["Register in Studbook", "Waiting for Laboratory",
			                      "Waiting for Marking Data"]),
			"date_of_birth": f"{year}-0{rng.randint(1, 9)}-1{rng.randint(0, 8)}",
			"place_of_birth": place,
			"current_location": rng.choice(["ميدان أبو سته", "إسطبل الفرنسية", "مزرعة الوادي"]),
			"microchip_no": f"9851{rng.randint(10**10, 10**11 - 1)}",
			"ueln_no": f"434{rng.randint(10**11, 10**12 - 1)}",
			"date_of_death": None if alive else f"{year + 9}-03-14",
			"notification_date": f"{year}-1{rng.randint(0, 2)}-05",
			"owner_since": f"{year}-0{rng.randint(1, 9)}-20",
			"sire_name_ar": sire[0], "sire_name_en": sire[1], "sire_registration_no": sire[2],
			"sire_origin": sire[3], "sire_color": sire[4], "sire_breed": "Arabian",
			"sire_date_of_birth": f"{year - 8}-04-11",
			"sire_place_of_birth": "طرابلس" if sire[3] == "Local" else "الدوحة",
			"sire_microchip_no": f"9851{rng.randint(10**10, 10**11 - 1)}",
			"dam_name_ar": dam[0], "dam_name_en": dam[1], "dam_registration_no": dam[2],
			"dam_origin": dam[3], "dam_color": dam[4], "dam_breed": "Arabian",
			"dam_date_of_birth": f"{year - 6}-09-02",
			"dam_place_of_birth": "بنغازي" if dam[3] == "Local" else "الرياض",
			"dam_microchip_no": f"9851{rng.randint(10**10, 10**11 - 1)}",
			"ownership_history": [{
				"owner_name_en": OWNERS[idx % len(OWNERS)][1],
				"owner_national_id": OWNERS[idx % len(OWNERS)][2],
				"from_date": f"{year}-0{rng.randint(1, 9)}-20",
			}],
		})
		horse.update(party(idx, "owner"))
		horse.update(party(idx + 3, "breeder"))
		horse.insert()
		add_documents(horse, coverage, files, rng)
		horses.append(horse)
		print(f"  {horse.name}  {name_en:<14} {origin:<8} {horse.documents_status}")

	# a registration form per young local horse, plus one still unlinked
	for horse in [h for h in horses if h.origin == "Local"][:4]:
		frappe.get_doc({
			"doctype": "Registration Form for Local Horses",
			"gender": horse.gender if horse.gender != "Gelding" else "Male",
			"color": horse.color, "breed": horse.breed,
			"date_of_birth": horse.date_of_birth, "place_of_birth": horse.place_of_birth,
			"microchip_no": horse.microchip_no, "current_location": horse.current_location,
			"notification_date": horse.notification_date,
			"covering_location": "Local",
			"covering_date_1": f"{str(horse.date_of_birth)[:4]}-02-14",
			"owner_name_ar": horse.owner_name_ar, "owner_name_en": horse.owner_name_en,
			"owner_national_id": horse.owner_national_id, "owner_phone": horse.owner_phone,
			"owner_city": horse.owner_city, "owner_address": horse.owner_address,
			"breeder_name_ar": horse.breeder_name_ar, "breeder_name_en": horse.breeder_name_en,
			"breeder_national_id": horse.breeder_national_id,
			"breeder_phone": horse.breeder_phone, "breeder_city": horse.breeder_city,
			"name_1_ar": horse.name_ar, "name_1_en": horse.name_en,
			"name_2_ar": "الصهباء", "name_2_en": "Al Sahba",
			"name_3_ar": "المهرة", "name_3_en": "Al Muhra",
			"approved_name_ar": horse.name_ar, "approved_name_en": horse.name_en,
			"sire_name_ar": horse.sire_name_ar, "sire_name_en": horse.sire_name_en,
			"sire_registration_no": horse.sire_registration_no, "sire_origin": horse.sire_origin,
			"sire_color": horse.sire_color, "sire_breed": horse.sire_breed,
			"dam_name_ar": horse.dam_name_ar, "dam_name_en": horse.dam_name_en,
			"dam_registration_no": horse.dam_registration_no, "dam_origin": horse.dam_origin,
			"dam_color": horse.dam_color, "dam_breed": horse.dam_breed,
			"dam_life_status": "Alive", "dam_current_location": "مزرعة الوادي",
			"horse": horse.name,
		}).insert()

	frappe.get_doc({
		"doctype": "Registration Form for Local Horses",
		"gender": "Female", "color": "Bay (Arabian)", "breed": "Arabian",
		"date_of_birth": "2026-03-02", "place_of_birth": "طرابلس",
		"current_location": "ميدان أبو سته",
		**party(1, "owner"), **party(4, "breeder"),
		"name_1_ar": "الشهباء", "name_1_en": "Al Shahba",
		"name_2_ar": "الندى", "name_2_en": "Al Nada",
		"sire_name_ar": SIRES[0][0], "sire_name_en": SIRES[0][1],
		"sire_registration_no": SIRES[0][2], "sire_origin": "Local",
		"dam_name_ar": DAMS[0][0], "dam_name_en": DAMS[0][1],
		"dam_registration_no": DAMS[0][2], "dam_origin": "Local",
	}).insert()

	# two transfers and a rename against documented horses
	for horse, buyer_index, date in [(horses[0], 2, "2026-04-18"), (horses[1], 5, "2026-05-30")]:
		buyer = OWNERS[buyer_index]
		frappe.get_doc({
			"doctype": "Owner Change Form",
			"horse": horse.name,
			"new_owner_name_ar": buyer[0], "new_owner_name_en": buyer[1],
			"new_owner_national_id": buyer[2], "new_owner_city": buyer[4],
			"new_owner_phone": buyer[5],
			"new_ownership_date": date,
			"legal_contract_officer": "محرر العقود / نبيل القمودي",
			"endorsement_date": date,
		}).insert()

	frappe.get_doc({
		"doctype": "Name Change Form",
		"horse": horses[3].name,
		"name_1_ar": "صحراء الجنوب", "name_1_en": "Sahra Al Janoub",
		"name_2_ar": "صحراء ليبيا", "name_2_en": "Sahra Libya",
		"approved_name_ar": "صحراء الجنوب", "approved_name_en": "Sahra Al Janoub",
		"approval_date": "2026-06-21",
	}).insert()

	frappe.db.commit()

	print("\ndocuments status spread:")
	for status in ("Completed", "Partially Completed", "Not Yet"):
		print(f"  {status:<22} {frappe.db.count('Horse', {'documents_status': status})}")
	for doctype in ("Horse", "Horse Document", "Horse Event",
	                "Registration Form for Local Horses",
	                "Owner Change Form", "Name Change Form"):
		print(f"  {doctype:<38} {frappe.db.count(doctype)}")


if __name__ == "__main__":
	frappe.init(site=SITE)
	frappe.connect()
	frappe.set_user("Administrator")

	if frappe.db.exists("Horse", {"name_en": MARKER}):
		print(f"{SITE} already seeded ({MARKER} exists), nothing to do")
	else:
		seed()
		print(f"\nseeded {SITE}")
