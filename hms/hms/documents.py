"""Which documents a horse needs, and whether it has them.

A document used to be an ``Attach`` field on the Horse, one per category, one
upload each. It is now a **Horse Document** transaction: a horse takes as many
as its **Horse Document Category** allows, and the category -- not this file --
decides which horses need it and which details must come with it.

Everything above ``get_categories`` is pure, so ``_self_check`` runs the rules
without a database.
"""

import frappe

# horse.gender split the way the document rules talk about it: the mapping
# asks for a Covering Certificate from a "female/broodmare" and a Covering
# Agreement from a "male/stallion".
MALE_SEXES = {"Male", "Stallion", "Gelding", "Cryptorchid", "Monorchid"}
FEMALE_SEXES = {"Female", "Broodmare"}

# category flag -> the field on Horse Document it makes mandatory
COMPANIONS = {
	"needs_document_date": "document_date",
	"needs_reference_no": "reference_no",
	"needs_doc_status": "doc_status",
	"needs_season": "season",
	"needs_notes": "notes",
	"has_expiry": "expiry_date",
}

NOT_YET = "Not Yet"
PARTIAL = "Partially Completed"
COMPLETED = "Completed"

CACHE_KEY = "hms_document_categories"


# --------------------------------------------------------------------------
# the rules
# --------------------------------------------------------------------------
def is_applicable(category, horse):
	"""Does this category apply to this horse at all?"""
	if category.get("disabled"):
		return False

	origin = horse.get("origin") or "Local"
	if origin == "Imported":
		if not category.get("applies_to_imported"):
			return False
	elif not category.get("applies_to_local"):
		return False

	sex = category.get("applies_to_sex") or "All"
	if sex == "Males" and horse.get("gender") not in MALE_SEXES:
		return False
	if sex == "Females" and horse.get("gender") not in FEMALE_SEXES:
		return False

	breed = category.get("applies_to_breed") or "All"
	# every horse here is a Thoroughbred; the Horse has no breed field
	if breed != "All" and (horse.get("breed") or "Thoroughbred") != breed:
		return False

	country = category.get("applies_to_country")
	if country and horse.get("birthplace_country") != country:
		return False

	return True


def is_required(category, horse):
	"""Applicable *and* starred for this horse's origin."""
	if not is_applicable(category, horse):
		return False
	if (horse.get("origin") or "Local") == "Imported":
		return bool(category.get("required_for_imported"))
	return bool(category.get("required_for_local"))


def document_is_complete(document, category):
	"""An attachment on its own is not a document. The details come with it."""
	if not any(row.get("file") for row in document.get("attachments") or []):
		return False
	return all(
		document.get(field)
		for flag, field in COMPANIONS.items()
		if category.get(flag)
	)


def compute_status(horse, categories, complete_categories):
	"""``complete_categories``: names of categories with >=1 complete document."""
	required = [c["category"] for c in categories if is_required(c, horse)]
	if not required:
		return COMPLETED if complete_categories else NOT_YET
	done = sum(1 for name in required if name in complete_categories)
	if done == len(required):
		return COMPLETED
	return PARTIAL if done else NOT_YET


def over_limit(category, existing_count):
	"""``max_count`` of 0 means no limit."""
	limit = category.get("max_count") or 0
	return bool(limit) and existing_count >= limit


# --------------------------------------------------------------------------
# the database side
# --------------------------------------------------------------------------
FIELDS = [
	"name", "category", "disabled", "sort_order",
	"applies_to_local", "required_for_local",
	"applies_to_imported", "required_for_imported",
	"applies_to_sex", "applies_to_breed", "applies_to_country",
	"max_count", *COMPANIONS,
]


def get_categories():
	"""Every category, cached. Read on each Horse save, so it earns the cache."""
	def load():
		return frappe.get_all("Horse Document Category", fields=FIELDS,
		                      order_by="sort_order asc, category asc")

	return frappe.cache().get_value(CACHE_KEY, load)


def clear_category_cache(doc=None, method=None):
	frappe.cache().delete_value(CACHE_KEY)


def get_category(name):
	for category in get_categories():
		if category["category"] == name:
			return category
	return None


def complete_categories_for(horse_name):
	rows = frappe.get_all("Horse Document",
	                      filters={"horse": horse_name, "is_complete": 1},
	                      pluck="category")
	return set(rows)


def set_status(doc):
	"""Called from Horse.validate. A new Horse has no documents yet."""
	complete = complete_categories_for(doc.name) if not doc.is_new() else set()
	doc.documents_status = compute_status(doc.as_dict(), get_categories(), complete)


def recalculate(horse_name):
	"""Re-derive a horse's documents status after its documents changed."""
	if not horse_name or not frappe.db.exists("Horse", horse_name):
		return
	horse = frappe.db.get_value("Horse", horse_name,
	                            ["origin", "gender", "birthplace_country",
	                             "documents_status"], as_dict=True)
	status = compute_status(horse, get_categories(), complete_categories_for(horse_name))
	if status != horse.documents_status:
		frappe.db.set_value("Horse", horse_name, "documents_status", status,
		                    update_modified=False)


# --------------------------------------------------------------------------
def _self_check():
	def category(name, **kw):
		base = {"category": name, "applies_to_local": 1, "applies_to_imported": 1,
		        "max_count": 1}
		base.update(kw)
		return base

	cats = [
		category("Registration Form", required_for_local=1, required_for_imported=1,
		         needs_document_date=1),
		category("Passport", applies_to_local=0, required_for_imported=1,
		         needs_reference_no=1),
		category("Covering Certificate", applies_to_sex="Females", needs_season=1,
		         max_count=0),
		category("Covering Agreement", applies_to_sex="Males", needs_season=1),
		category("Others", max_count=0, needs_notes=1),
		category("Retired", disabled=1, required_for_local=1),
	]
	names = {c["category"]: c for c in cats}

	mare = {"origin": "Local", "gender": "Broodmare", "breed": "Arabian"}
	stallion = {"origin": "Imported", "gender": "Stallion", "breed": "Arabian"}

	# applicability
	assert is_applicable(names["Covering Certificate"], mare)
	assert not is_applicable(names["Covering Certificate"], stallion)
	assert is_applicable(names["Covering Agreement"], stallion)
	assert not is_applicable(names["Passport"], mare), "passport is imported-only"
	assert is_applicable(names["Passport"], stallion)
	assert not is_applicable(names["Retired"], mare), "disabled applies to nobody"

	# a disabled category can never be required
	assert not is_required(names["Retired"], mare)
	assert is_required(names["Registration Form"], mare)
	assert is_required(names["Passport"], stallion)
	assert not is_required(names["Covering Certificate"], mare), "optional stays optional"

	# breed and country narrowing
	thoroughbred_only = category("TB Only", applies_to_breed="Thoroughbred")
	assert not is_applicable(thoroughbred_only, mare)
	libya_only = category("Libya Only", applies_to_country="Libya")
	assert not is_applicable(libya_only, mare)
	assert is_applicable(libya_only, dict(mare, birthplace_country="Libya"))

	# completeness
	reg = names["Registration Form"]
	assert not document_is_complete({}, reg), "no attachment, no document"
	assert not document_is_complete({"attachments": [{"file": "/files/a.pdf"}]}, reg), \
		"attachment without its date is not done"
	assert document_is_complete({"attachments": [{"file": "/files/a.pdf"}],
	                             "document_date": "2026-01-01"}, reg)

	# status
	assert compute_status(mare, cats, set()) == NOT_YET
	assert compute_status(mare, cats, {"Registration Form"}) == COMPLETED
	assert compute_status(stallion, cats, {"Registration Form"}) == PARTIAL, \
		"imported still owes a passport"
	assert compute_status(stallion, cats, {"Registration Form", "Passport"}) == COMPLETED
	# an optional document alone never completes anything
	assert compute_status(mare, cats, {"Others"}) == NOT_YET

	# limits
	assert over_limit(names["Registration Form"], 1)
	assert not over_limit(names["Registration Form"], 0)
	assert not over_limit(names["Others"], 99), "max_count 0 means no limit"

	print("documents self-check ok")


if __name__ == "__main__":
	_self_check()
