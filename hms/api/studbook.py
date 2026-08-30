"""Read-only bridge to the external studbook API.

Configure the endpoint in site_config.json:

	"hms_studbook_api_url": "https://studbook.example.ly/api/v1",
	"hms_studbook_api_key": "..."

With no URL configured the module answers from the horses already in this site,
so the type-ahead works before the real API exists. Swapping to the real one is
a config change plus, if their payload differs, the two maps below.
"""

import frappe
from frappe import _

TIMEOUT = 10

# api payload key -> Horse fieldname. Anything not listed is ignored, so an API
# that sends extra keys costs nothing.
FIELD_MAP = {
	"name_ar": "name_ar",
	"name_en": "name_en",
	"ueln": "ueln_no",
	"microchip": "microchip_no",
	"origin": "origin",
	"sex": "gender",
	"colour": "color",
	"breed": "breed",
	"date_of_birth": "date_of_birth",
	"place_of_birth": "place_of_birth",
	"current_location": "current_location",
	"life_status": "life_status",
	"sire_name_ar": "sire_name_ar",
	"sire_name_en": "sire_name_en",
	"sire_registration_no": "sire_registration_no",
	"sire_origin": "sire_origin",
	"sire_date_of_birth": "sire_date_of_birth",
	"sire_place_of_birth": "sire_place_of_birth",
	"sire_colour": "sire_color",
	"sire_breed": "sire_breed",
	"sire_microchip": "sire_microchip_no",
	"dam_name_ar": "dam_name_ar",
	"dam_name_en": "dam_name_en",
	"dam_registration_no": "dam_registration_no",
	"dam_origin": "dam_origin",
	"dam_date_of_birth": "dam_date_of_birth",
	"dam_place_of_birth": "dam_place_of_birth",
	"dam_colour": "dam_color",
	"dam_breed": "dam_breed",
	"dam_microchip": "dam_microchip_no",
	"owner_name_ar": "owner_name_ar",
	"owner_name_en": "owner_name_en",
	"owner_national_id": "owner_national_id",
	"owner_phone": "owner_phone",
	"owner_city": "owner_city",
	"owner_address": "owner_address",
	"owner_since": "owner_since",
	"breeder_name_ar": "breeder_name_ar",
	"breeder_name_en": "breeder_name_en",
	"breeder_national_id": "breeder_national_id",
	"breeder_phone": "breeder_phone",
	"breeder_city": "breeder_city",
	"breeder_address": "breeder_address",
}

# api payload key -> suffix of a sire / dam block. The horse the user picks
# becomes the parent, so its own identity fills the parent fields.
PARENT_FIELDS = {
	"name_ar": "name_ar",
	"name_en": "name_en",
	"registration_no": "registration_no",
	"origin": "origin",
	"date_of_birth": "date_of_birth",
	"place_of_birth": "place_of_birth",
	"colour": "color",
	"breed": "breed",
	"microchip": "microchip_no",
	"life_status": "life_status",
	"current_location": "current_location",
}

# the reverse direction, used by the offline fallback to build a payload out of
# a local Horse record
LOCAL_MAP = {api_field: fieldname for api_field, fieldname in FIELD_MAP.items()}


def _config():
	return frappe.conf.get("hms_studbook_api_url"), frappe.conf.get("hms_studbook_api_key")


def _get(path, params):
	import requests

	url, key = _config()
	headers = {"Accept": "application/json"}
	if key:
		headers["Authorization"] = f"Bearer {key}"
	response = requests.get(f"{url.rstrip('/')}{path}", params=params, headers=headers,
	                        timeout=TIMEOUT)
	response.raise_for_status()
	payload = response.json()
	return payload.get("data", payload)


@frappe.whitelist()
def search_horses(txt, lang="en", limit=20):
	"""Names matching what the user typed, for the name field type-ahead."""
	frappe.has_permission("Horse", "read", throw=True)

	txt = (txt or "").strip()
	if not txt:
		return []
	limit = min(int(limit), 50)

	url, _key = _config()
	if not url:
		return _local_search(txt, limit)

	try:
		rows = _get("/horses", {"q": txt, "lang": lang, "limit": limit})
	except Exception:
		frappe.log_error(title="Studbook API search failed")
		frappe.msgprint(_("The studbook API is not reachable, showing local horses instead."),
		                indicator="orange", alert=True)
		return _local_search(txt, limit)

	return [
		{
			"ref": str(row.get("id") or row.get("registration_no") or ""),
			"name_ar": row.get("name_ar"),
			"name_en": row.get("name_en"),
			"registration_no": row.get("registration_no"),
		}
		for row in rows
	]


def _payload(ref):
	url, _key = _config()
	payload = _local_horse(ref) if not url else _get(f"/horses/{ref}", {})
	if not payload:
		frappe.throw(_("Horse {0} was not found in the studbook").format(ref))
	return payload


def _values(payload, mapping, doctype):
	"""Only the mapped fields that this doctype actually has."""
	meta = frappe.get_meta(doctype)
	values = {}
	for api_field, fieldname in mapping.items():
		value = payload.get(api_field)
		if value not in (None, "") and meta.has_field(fieldname):
			values[fieldname] = value
	return values


@frappe.whitelist()
def get_horse(ref, doctype="Horse"):
	"""Every field the studbook holds for one horse, keyed by fieldname."""
	frappe.has_permission("Horse", "read", throw=True)
	return _values(_payload(ref), FIELD_MAP, doctype)


@frappe.whitelist()
def get_parent(ref, prefix, doctype="Registration Form for Local Horses"):
	"""The picked horse as a sire or dam block, keyed by <prefix>_<field>."""
	frappe.has_permission("Horse", "read", throw=True)
	if prefix not in ("sire", "dam"):
		frappe.throw(_("{0} is not a parent block").format(prefix))

	mapping = {api_field: f"{prefix}_{suffix}" for api_field, suffix in PARENT_FIELDS.items()}
	return _values(_payload(ref), mapping, doctype)


# --------------------------------------------------------------------------
# offline fallback: answer from this site's own horses
# --------------------------------------------------------------------------
def _local_search(txt, limit):
	like = f"%{txt}%"
	rows = frappe.get_all(
		"Horse",
		or_filters={"name_ar": ("like", like), "name_en": ("like", like), "name": ("like", like)},
		fields=["name as ref", "name_ar", "name_en", "name as registration_no"],
		limit=limit,
		order_by="name_en asc",
	)
	return rows


def _local_horse(ref):
	if not frappe.db.exists("Horse", ref):
		return None
	horse = frappe.get_doc("Horse", ref)
	payload = {api_field: horse.get(fieldname) for api_field, fieldname in LOCAL_MAP.items()}
	# the registration number is the horse's own name here
	payload["registration_no"] = horse.name
	return payload
