"""Pull horses out of the StudLib studbook Postgres into the Horse doctype.

Connection details live on HMS Settings. The sync is an upsert keyed on the
studbook ``uuid`` -- not the registry number, because a foal exists in StudLib
long before it is given one. Running it twice changes nothing the second time.

Only the fields the studbook owns are written. Everything Frappe owns -- the
Horse Documents, ``documents_status``, the paper forms -- is left alone, so a
re-sync never costs a user their uploads.

StudLib is normalised: colors, countries and book types are their own tables
and owners hang off M:N joins. Those are mirrored into their own doctypes first
so the Horse can Link at them.
"""

import time

import frappe
from frappe import _
from frappe.utils import cint, get_time, now_datetime

# the scheduled jobs registered in hooks.py, whose crons this module rewrites
SCHEDULED_JOB = "hms.api.legacy_sync.scheduled_sync"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# --------------------------------------------------------------------------
# StudLib enums -> the labels the Select fields carry
# --------------------------------------------------------------------------
BREED = {"ARABIAN": "Arabian", "THOROUGHBRED": "Thoroughbred"}

SEX = {
	"MALE": "Male", "FEMALE": "Female", "STALLION": "Stallion",
	"BROODMARE": "Broodmare", "GELDING": "Gelding",
	"CRYPTORCHID": "Cryptorchid", "MONORCHID": "Monorchid",
}

STATUS = {
	"NEW_FOAL": "New Foal",
	"NEW_IMPORTED": "New Imported",
	"WAITING_FOR_MARKING_DATA": "Waiting for Marking Data",
	"WAITING_FOR_LABORATORY": "Waiting for Laboratory",
	"LABORATORY_DATA_ENTERED": "Laboratory Data Entered",
	"REGISTER_IN_STUDBOOK": "Register in Studbook",
	"REJECTED": "Rejected",
	"EXTERNAL": "External",
}

CLASSIFICATION = {
	"RACING": "Racing", "JUMPING": "Jumping", "BEAUTY": "Beauty", "UNKNOWN": "Unknown",
}

COLOR_RULE = {"BOTH_PARENTS": "Both Parents", "AT_LEAST_ONE_PARENT": "At Least One Parent"}

ENUMS = {
	"breed": BREED, "gender": SEX, "status": STATUS,
	"horse_classification": CLASSIFICATION,
}

# --------------------------------------------------------------------------
# StudLib horse column -> Horse fieldname.
#
# Two aliases, kept because the print formats and paper forms are built on
# them: StudLib ``name`` is our ``name_en`` (``name`` is the Frappe docname)
# and StudLib ``local_name`` is our ``name_ar``.
# --------------------------------------------------------------------------
COLUMNS = {
	"name": "name_en",
	"local_name": "name_ar",
	"name_suffix": "name_suffix",
	"breed": "breed",
	"sex": "gender",
	"status": "status",
	"horse_classification": "horse_classification",
	"ueln": "ueln_no",
	"registry_id": "registry_id",
	"previous_registry_id": "previous_registry_id",
	"legacy_registry_id": "legacy_registry_id",
	"legacy_ueln": "legacy_ueln",
	"transponder_code": "microchip_no",
	"second_transponder_code": "second_microchip_no",
	"transponder_site": "transponder_site",
	"blood_code": "blood_code",
	"strain": "strain",
	"date_of_birth": "date_of_birth",
	"date_of_death": "date_of_death",
	"date_of_registration": "date_of_registration",
	"date_of_importing": "date_of_importing",
	"date_of_exporting": "date_of_exporting",
	"date_of_control": "date_of_control",
	"date_of_declaration": "date_of_declaration",
	"dna_sample_exists": "dna_sample_exists",
	"book_number": "book_number",
	"book_page": "book_page",
	"book_appendix_number": "book_appendix_number",
	"previous_book_number": "previous_book_number",
	"previous_book_page": "previous_book_page",
	"previous_book_appendix_number": "previous_book_appendix_number",
	"notes": "notes",
}

# a Horse the studbook says nothing about; never written by the sync
FRAPPE_OWNED = ("documents_status", "ownership_history", "name_history")

HISTORY_LIMIT = 20
CONNECT_TIMEOUT = 5

HORSE_SQL = """
SELECT h.id, h.uuid, h.version,
       h.name, h.local_name, h.name_suffix, h.breed, h.sex, h.status,
       h.horse_classification, h.ueln, h.registry_id, h.previous_registry_id,
       h.legacy_registry_id, h.legacy_ueln,
       h.transponder_code, h.second_transponder_code, h.transponder_site,
       h.blood_code, h.strain,
       h.date_of_birth, h.date_of_death, h.date_of_registration,
       h.date_of_importing, h.date_of_exporting, h.date_of_control,
       h.date_of_declaration, h.dna_sample_exists,
       h.book_number, h.book_page, h.book_appendix_number,
       h.previous_book_number, h.previous_book_page, h.previous_book_appendix_number,
       h.notes,
       bc.name  AS birthplace_country,
       ic.name  AS import_country,
       ec.name  AS export_country,
       col.name AS color_name, col.horse_breed AS color_breed,
       bt.code  AS book_code,  bt.horse_breed  AS book_breed,
       pbt.code AS previous_book_code, pbt.horse_breed AS previous_book_breed,
       cb.full_name AS controlled_by,
       sire.uuid AS sire_uuid, sire.name AS sire_name_en,
       sire.local_name AS sire_name_ar, sire.registry_id AS sire_registration_no,
       sire.date_of_birth AS sire_date_of_birth, sire.breed AS sire_breed,
       sire.transponder_code AS sire_microchip_no, sirec.name AS sire_color,
       sirebc.local AS sire_local,
       dam.uuid AS dam_uuid, dam.name AS dam_name_en,
       dam.local_name AS dam_name_ar, dam.registry_id AS dam_registration_no,
       dam.date_of_birth AS dam_date_of_birth, dam.breed AS dam_breed,
       dam.transponder_code AS dam_microchip_no, damc.name AS dam_color,
       dambc.local AS dam_local,
       bc.local AS birthplace_local
FROM horse h
LEFT JOIN country    bc  ON bc.id  = h.birthplace_country_id
LEFT JOIN country    ic  ON ic.id  = h.import_country_id
LEFT JOIN country    ec  ON ec.id  = h.export_country_id
LEFT JOIN horse_color col ON col.id = h.color_id
LEFT JOIN book_type  bt  ON bt.id  = h.book_type_id
LEFT JOIN book_type  pbt ON pbt.id = h.previous_book_type_id
LEFT JOIN application_user cb ON cb.id = h.controlled_by_id
LEFT JOIN horse sire ON sire.id = h.father_id
LEFT JOIN horse_color sirec ON sirec.id = sire.color_id
LEFT JOIN country sirebc ON sirebc.id = sire.birthplace_country_id
LEFT JOIN horse dam ON dam.id = h.mother_id
LEFT JOIN horse_color damc ON damc.id = dam.color_id
LEFT JOIN country dambc ON dambc.id = dam.birthplace_country_id
ORDER BY h.id
"""

PARTIES_SQL = """
SELECT h.uuid, o.id, o.full_name, o.national_id_number
FROM {table} j
JOIN horse h ON h.id = j.horse_id
JOIN owner o ON o.id = j.owner_id
ORDER BY h.uuid, o.id
"""


def _settings():
	settings = frappe.get_single("HMS Settings")
	if not settings.studbook_enabled:
		frappe.throw(_("The studbook connection is turned off in HMS Settings."))
	if not (settings.studbook_host and settings.studbook_database and settings.studbook_user):
		frappe.throw(_("Fill in the studbook host, database and user in HMS Settings."))
	return settings


def _connect(settings):
	import psycopg2

	return psycopg2.connect(
		host=settings.studbook_host,
		port=cint(settings.studbook_port) or 5432,
		dbname=settings.studbook_database,
		user=settings.studbook_user,
		password=settings.get_password("studbook_password", raise_exception=False) or "",
		connect_timeout=CONNECT_TIMEOUT,
	)


@frappe.whitelist()
def test_connection():
	"""Prove the credentials work before anyone waits on a full sync."""
	frappe.only_for("System Manager")
	settings = _settings()
	connection = _connect(settings)
	try:
		cursor = connection.cursor()
		cursor.execute("SELECT count(*) FROM horse")
		count = cursor.fetchone()[0]
	finally:
		connection.close()
	return {"horses": count}


def _rows(connection, sql, params=None):
	cursor = connection.cursor()
	cursor.execute(sql, params or ())
	columns = [c[0] for c in cursor.description]
	return [dict(zip(columns, row)) for row in cursor.fetchall()]


# --------------------------------------------------------------------------
# reference tables
# --------------------------------------------------------------------------
def _upsert(doctype, studbook_id, values, key=None):
	"""One mirrored reference row. Keyed on the studbook primary key."""
	name = frappe.db.get_value(doctype, {"studbook_id": studbook_id}, "name")
	if not name and key:
		name = frappe.db.get_value(doctype, key, "name")

	if name:
		doc = frappe.get_doc(doctype, name)
	else:
		doc = frappe.new_doc(doctype)
	doc.studbook_id = studbook_id
	for field, value in values.items():
		doc.set(field, value)
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return doc.name


def sync_reference(connection):
	"""Countries, colors, book types and owners, before the horses need them."""
	counts = {}

	countries = _rows(connection, "SELECT id, name, alpha2, alpha3, code, local FROM country")
	for row in countries:
		_upsert("Studbook Country", row["id"], {
			"country_name": row["name"], "alpha2": row["alpha2"],
			"alpha3": row["alpha3"], "numeric_code": row["code"],
			"is_local": 1 if row["local"] else 0,
		}, key={"country_name": row["name"]})
	counts["countries"] = len(countries)

	colors = _rows(connection,
	               "SELECT id, name, short_name, horse_breed, validation_rule FROM horse_color")
	for row in colors:
		_upsert("Horse Color", row["id"], {
			"color_name": row["name"], "short_name": row["short_name"],
			"horse_breed": BREED.get(row["horse_breed"], row["horse_breed"]),
			"validation_rule": COLOR_RULE.get(row["validation_rule"]),
		})
	counts["colors"] = len(colors)

	books = _rows(connection,
	              "SELECT b.id, b.code, b.authority, b.horse_breed, b.libyan, c.name AS country "
	              "FROM book_type b LEFT JOIN country c ON c.id = b.country_id")
	for row in books:
		_upsert("Book Type", row["id"], {
			"code": row["code"], "authority": row["authority"],
			"horse_breed": BREED.get(row["horse_breed"], row["horse_breed"]),
			"is_libyan": 1 if row["libyan"] else 0,
			"issuing_country": row["country"] if row["country"] and frappe.db.exists(
				"Studbook Country", row["country"]) else None,
		})
	counts["book_types"] = len(books)

	owners = _rows(connection,
	               "SELECT o.id, o.full_name, o.suffix, o.business, o.business_number, "
	               "o.national_id_number, o.farm_name, o.phone, o.note, o.street, o.city, "
	               "o.postal_code, o.region, o.latitude, o.longitude, c.name AS country "
	               "FROM owner o LEFT JOIN country c ON c.id = o.country_id")
	for row in owners:
		_upsert("Horse Owner", row["id"], {
			# StudLib keeps one name; the Arabic field mirrors it until a user
			# fills the local spelling in
			"owner_name_en": row["full_name"],
			"owner_name_ar": row["full_name"],
			"suffix": row["suffix"],
			"business": 1 if row["business"] else 0,
			"business_number": row["business_number"],
			"national_id": row["national_id_number"],
			"farm_name": row["farm_name"],
			"phone": row["phone"], "note": row["note"],
			"address": row["street"], "city": row["city"],
			"postal_code": row["postal_code"], "region": row["region"],
			"latitude": row["latitude"], "longitude": row["longitude"],
			"owner_country": row["country"] if row["country"] and frappe.db.exists(
				"Studbook Country", row["country"]) else None,
		})
	counts["owners"] = len(owners)

	return counts


# --------------------------------------------------------------------------
# horses
# --------------------------------------------------------------------------
def _enum(fieldname, value):
	return ENUMS[fieldname].get(value, value) if fieldname in ENUMS else value


def _color(row):
	"""Horse Color is named "<color> (<breed>)" because colors repeat per breed."""
	name = row.get("color_name")
	breed = BREED.get(row.get("color_breed"))
	if not name:
		return None
	candidate = f"{name} ({breed})" if breed else name
	return candidate if frappe.db.exists("Horse Color", candidate) else None


def _book(row, prefix):
	code = row.get(f"{prefix}code")
	breed = BREED.get(row.get(f"{prefix}breed"))
	if not code:
		return None
	candidate = f"{code} ({breed})" if breed else code
	return candidate if frappe.db.exists("Book Type", candidate) else None


def _link_country(name):
	return name if name and frappe.db.exists("Studbook Country", name) else None


def _origin(is_local):
	if is_local is None:
		return None
	return "Local" if is_local else "Imported"


def _apply(doc, row, owners, breeders, horses_by_uuid):
	"""Copy the studbook's fields onto a Horse. Returns True if anything moved."""
	values = {}

	for column, fieldname in COLUMNS.items():
		value = row.get(column)
		if value is None or value == "":
			continue
		values[fieldname] = _enum(fieldname, value)

	values["studbook_id"] = row["id"]
	values["studbook_uuid"] = str(row["uuid"])
	values["birthplace_country"] = _link_country(row.get("birthplace_country"))
	values["import_country"] = _link_country(row.get("import_country"))
	values["export_country"] = _link_country(row.get("export_country"))
	values["color"] = _color(row)
	values["book_type"] = _book(row, "book_")
	values["previous_book_type"] = _book(row, "previous_book_")
	values["controlled_by"] = row.get("controlled_by")
	values["origin"] = _origin(row.get("birthplace_local"))
	values["dna_sample_exists"] = 1 if row.get("dna_sample_exists") else 0

	# pedigree: the Links where we have the parent, the flat block always, so
	# a parent outside this studbook still prints
	for prefix in ("sire", "dam"):
		parent_uuid = row.get(f"{prefix}_uuid")
		values[prefix] = horses_by_uuid.get(str(parent_uuid)) if parent_uuid else None
		for field in ("name_en", "name_ar", "registration_no", "date_of_birth",
		              "microchip_no", "color"):
			value = row.get(f"{prefix}_{field}")
			if value is not None:
				values[f"{prefix}_{field}"] = value
		values[f"{prefix}_breed"] = BREED.get(row.get(f"{prefix}_breed"))
		values[f"{prefix}_origin"] = _origin(row.get(f"{prefix}_local"))

	changed = False
	for fieldname, value in values.items():
		if fieldname in FRAPPE_OWNED:
			continue
		if doc.get(fieldname) != value:
			doc.set(fieldname, value)
			changed = True

	# M:N tables are replaced wholesale: the studbook is their only writer and
	# diffing rows without a stable key would be guesswork
	for fieldname, rows in (("owners", owners), ("breeders", breeders)):
		if rows is not None and _differs(doc.get(fieldname), rows):
			doc.set(fieldname, rows)
			changed = True

	return changed


def _differs(existing, incoming):
	if len(existing) != len(incoming):
		return True
	for current, new in zip(existing, incoming):
		for field, value in new.items():
			if str(current.get(field) or "") != str(value or ""):
				return True
	return False


def _parties(connection, table):
	"""Owner or breeder rows for every horse at once, keyed by studbook uuid."""
	rows = {}
	for uuid, owner_id, full_name, national_id in _raw(connection,
	                                                   PARTIES_SQL.format(table=table)):
		local = frappe.db.get_value("Horse Owner", {"studbook_id": owner_id}, "name")
		if not local:
			continue
		rows.setdefault(str(uuid), []).append({
			"party": local, "owner_name_en": full_name,
			"national_id": national_id, "studbook_owner_id": owner_id,
		})
	return rows


def _raw(connection, sql):
	cursor = connection.cursor()
	cursor.execute(sql)
	return cursor.fetchall()


@frappe.whitelist()
def sync_horses():
	"""Upsert every horse in the studbook. Safe to run again; it updates."""
	frappe.only_for("System Manager")

	started = time.monotonic()
	settings = _settings()
	created = updated = skipped = 0
	failures = []

	connection = _connect(settings)
	try:
		sync_reference(connection)
		frappe.db.commit()

		rows = _rows(connection, HORSE_SQL)
		owners = _parties(connection, "horse_owner")
		breeders = _parties(connection, "horse_breeder")
	finally:
		connection.close()

	# uuid -> docname, so a horse can Link at its sire in the same pass. Built
	# up as we go, then a second pass fixes the parents that came after their
	# foal in id order.
	horses_by_uuid = dict(frappe.get_all("Horse", fields=["studbook_uuid", "name"],
	                                     filters={"studbook_uuid": ("is", "set")},
	                                     as_list=True))

	for row in rows:
		uuid = str(row["uuid"])
		try:
			name = horses_by_uuid.get(uuid) or frappe.db.get_value(
				"Horse", {"studbook_uuid": uuid}, "name")
			if name:
				doc = frappe.get_doc("Horse", name)
				if _apply(doc, row, owners.get(uuid), breeders.get(uuid), horses_by_uuid):
					doc.save(ignore_permissions=True)
					updated += 1
				else:
					skipped += 1
			else:
				doc = frappe.new_doc("Horse")
				_apply(doc, row, owners.get(uuid, []), breeders.get(uuid, []),
				       horses_by_uuid)
				doc.insert(ignore_permissions=True)
				created += 1
			horses_by_uuid[uuid] = doc.name
		except Exception as error:
			frappe.db.rollback()
			failures.append(f"{row.get('registry_id') or uuid}: {error}")
			frappe.log_error(title=f"Studbook sync failed for {uuid}")

	_link_parents(rows, horses_by_uuid)

	# an event may have arrived before the horse it names
	from hms.api.events import resolve_unlinked
	resolve_unlinked()

	frappe.db.commit()

	outcome = "Failed" if failures and not (created or updated) else (
		"Partial" if failures else "Success")
	message = _("{0} of {1} horses failed").format(len(failures), len(rows)) if failures else \
		_("{0} horses read from the studbook").format(len(rows))
	if failures:
		message += "\n" + "\n".join(failures[:5])

	_record(settings, created, updated, skipped, time.monotonic() - started, outcome, message)

	return {
		"created": created,
		"updated": updated,
		"skipped": skipped,
		"failed": len(failures),
		"total": len(rows),
		"outcome": outcome,
		"message": message,
	}


def _link_parents(rows, horses_by_uuid):
	"""Second pass: a foal read before its sire had nothing to Link at yet."""
	for row in rows:
		child = horses_by_uuid.get(str(row["uuid"]))
		if not child:
			continue
		for prefix in ("sire", "dam"):
			parent_uuid = row.get(f"{prefix}_uuid")
			if not parent_uuid:
				continue
			parent = horses_by_uuid.get(str(parent_uuid))
			if parent and frappe.db.get_value("Horse", child, prefix) != parent:
				frappe.db.set_value("Horse", child, prefix, parent,
				                    update_modified=False)


def scheduled_sync():
	"""Entry point for the scheduler. Quiet when there is nothing to do.

	The job is registered in hooks.py with a daily cron and re-pointed by
	HMS Settings, so it should only ever fire when it is meant to. It still
	checks, because a stopped job that gets re-enabled by a migrate would
	otherwise sync behind the user's back.
	"""
	settings = frappe.get_single("HMS Settings")
	if not settings.studbook_enabled or settings.sync_frequency in (None, "", "Never"):
		return

	frappe.set_user("Administrator")
	sync_horses()


def cron_for(settings):
	"""The cron expression the chosen frequency works out to, or None."""
	frequency = settings.sync_frequency
	if not frequency or frequency == "Never":
		return None
	if frequency == "Hourly":
		return "0 * * * *"

	at = get_time(settings.sync_time or "00:00:00")
	if frequency == "Daily":
		return f"{at.minute} {at.hour} * * *"
	if frequency == "Weekly":
		# cron counts Sunday as 0, the field lists Monday first
		day = (WEEKDAYS.index(settings.sync_day_of_week or "Monday") + 1) % 7
		return f"{at.minute} {at.hour} * * {day}"
	if frequency == "Monthly":
		# capped at 28 so the job cannot skip February
		day = min(max(cint(settings.sync_day_of_month) or 1, 1), 28)
		return f"{at.minute} {at.hour} {day} * *"

	frappe.throw(_("{0} is not a sync frequency this app knows").format(frequency))


def apply_schedule(settings):
	"""Point the scheduled job at whatever HMS Settings now says.

	Frappe owns the scheduling itself -- due times, deduplication and the
	Scheduled Job Log all come free. This only rewrites the cron and stops the
	job when the sync is turned off.
	"""
	if not frappe.db.exists("Scheduled Job Type", {"method": SCHEDULED_JOB}):
		# the job appears on the next migrate, when hooks are read
		return None

	job = frappe.get_doc("Scheduled Job Type", {"method": SCHEDULED_JOB})
	cron = cron_for(settings)

	job.stopped = 0 if cron else 1
	if cron:
		job.frequency = "Cron"
		job.cron_format = cron
	job.save(ignore_permissions=True)

	return job.get_next_execution() if cron else None


def _record(settings, created, updated, skipped, duration, outcome, message):
	"""Stamp the run onto HMS Settings and push a row onto the history."""
	settings.last_sync_on = now_datetime()
	settings.last_sync_by = frappe.session.user
	settings.last_sync_created = created
	settings.last_sync_updated = updated
	settings.last_sync_skipped = skipped
	settings.last_sync_outcome = outcome
	settings.last_sync_message = message

	settings.append("sync_history", {
		"synced_on": settings.last_sync_on,
		"synced_by": frappe.session.user,
		"created_count": created,
		"updated_count": updated,
		"skipped_count": skipped,
		"duration": round(duration, 2),
		"outcome": outcome,
		"message": message,
	})
	# newest first, and only the recent past: this is a single doctype and the
	# table is rewritten in full on every save
	settings.sync_history = sorted(
		settings.sync_history, key=lambda row: row.synced_on, reverse=True)[:HISTORY_LIMIT]
	for index, row in enumerate(settings.sync_history, start=1):
		row.idx = index

	settings.save(ignore_permissions=True)
	frappe.db.commit()
