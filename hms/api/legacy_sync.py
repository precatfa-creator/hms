"""Pull horses out of the StudLib studbook Postgres into the Horse doctype.

Connection details live on HMS Settings. The sync is an upsert keyed on the
studbook ``uuid`` -- not the registry number, because a foal exists in StudLib
long before it is given one. Running it twice changes nothing the second time.

Only the fields the studbook owns are written. Everything Frappe owns -- the
Horse Documents, ``documents_status``, the paper forms -- is left alone, so a
re-sync never costs a user their uploads.

Only Thoroughbreds registered in the studbook are pulled; foals still in the
registration workflow, rejected and external horses stay in StudLib.

StudLib is normalised: colors and countries are their own tables and owners
hang off M:N joins. Those are mirrored into their own doctypes first so the
Horse can Link at them.
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

CLASSIFICATION = {
	"RACING": "Racing", "JUMPING": "Jumping", "BEAUTY": "Beauty", "UNKNOWN": "Unknown",
}

COLOR_RULE = {"BOTH_PARENTS": "Both Parents", "AT_LEAST_ONE_PARENT": "At Least One Parent"}

ENUMS = {"gender": SEX, "horse_classification": CLASSIFICATION}

# the only horses the sync reads
REGISTERED = "h.status = 'REGISTER_IN_STUDBOOK' AND h.breed = 'THOROUGHBRED'"

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
	"sex": "gender",
	"horse_classification": "horse_classification",
	"ueln": "ueln_no",
	"registry_id": "registry_id",
	"transponder_code": "microchip_no",
	"date_of_birth": "date_of_birth",
	"date_of_death": "date_of_death",
	"date_of_importing": "date_of_importing",
	"date_of_exporting": "date_of_exporting",
	"date_of_control": "date_of_control",
	"date_of_declaration": "date_of_declaration",
	"notes": "notes",
}

# a Horse the studbook says nothing about; never written by the sync
FRAPPE_OWNED = ("documents_status", "ownership_history", "name_history")

HISTORY_LIMIT = 20
CONNECT_TIMEOUT = 5

HORSE_SQL = f"""
SELECT h.id, h.uuid,
       h.name, h.local_name, h.sex, h.horse_classification,
       h.ueln, h.registry_id, h.transponder_code,
       h.date_of_birth, h.date_of_death,
       h.date_of_importing, h.date_of_exporting, h.date_of_control,
       h.date_of_declaration, h.notes,
       bc.name  AS birthplace_country,
       ic.name  AS import_country,
       ec.name  AS export_country,
       col.name AS color_name, col.horse_breed AS color_breed,
       cb.full_name AS controlled_by,
       sire.name AS sire_name_en, sire.transponder_code AS sire_microchip_no,
       dam.name  AS dam_name_en,  dam.transponder_code  AS dam_microchip_no,
       bc.local AS birthplace_local
FROM horse h
LEFT JOIN country    bc  ON bc.id  = h.birthplace_country_id
LEFT JOIN country    ic  ON ic.id  = h.import_country_id
LEFT JOIN country    ec  ON ec.id  = h.export_country_id
LEFT JOIN horse_color col ON col.id = h.color_id
LEFT JOIN application_user cb ON cb.id = h.controlled_by_id
LEFT JOIN horse sire ON sire.id = h.father_id
LEFT JOIN horse dam  ON dam.id  = h.mother_id
WHERE {REGISTERED}
ORDER BY h.id
"""

PARTIES_SQL = """
SELECT h.uuid, o.id, o.full_name, o.national_id_number
FROM {table} j
JOIN horse h ON h.id = j.horse_id
JOIN owner o ON o.id = j.owner_id
WHERE {registered}
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
		cursor.execute(f"SELECT count(*) FROM horse h WHERE {REGISTERED}")
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
	"""Countries, colors and owners, before the horses need them."""
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
	               "SELECT id, name, short_name, horse_breed, validation_rule FROM horse_color "
	               "WHERE horse_breed = 'THOROUGHBRED'")
	for row in colors:
		_upsert("Horse Color", row["id"], {
			"color_name": row["name"], "short_name": row["short_name"],
			"horse_breed": BREED.get(row["horse_breed"], row["horse_breed"]),
			"validation_rule": COLOR_RULE.get(row["validation_rule"]),
		})
	counts["colors"] = len(colors)

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


def _link_country(name):
	return name if name and frappe.db.exists("Studbook Country", name) else None


def _origin(is_local):
	if is_local is None:
		return None
	return "Local" if is_local else "Imported"


def _apply(doc, row, owners, breeders):
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
	values["controlled_by"] = row.get("controlled_by")
	values["origin"] = _origin(row.get("birthplace_local"))
	for field in ("sire_name_en", "sire_microchip_no", "dam_name_en", "dam_microchip_no"):
		values[field] = row.get(field)

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
	                                                   PARTIES_SQL.format(table=table, registered=REGISTERED)):
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
	"""Upsert every registered Thoroughbred. Safe to run again; it updates."""
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

	# uuid -> docname, so the loop below skips a lookup per horse
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
				if _apply(doc, row, owners.get(uuid), breeders.get(uuid)):
					doc.save(ignore_permissions=True)
					updated += 1
				else:
					skipped += 1
			else:
				doc = frappe.new_doc("Horse")
				_apply(doc, row, owners.get(uuid, []), breeders.get(uuid, []))
				doc.insert(ignore_permissions=True)
				created += 1
			horses_by_uuid[uuid] = doc.name
		except Exception as error:
			frappe.db.rollback()
			failures.append(f"{row.get('registry_id') or uuid}: {error}")
			frappe.log_error(title=f"Studbook sync failed for {uuid}")

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
