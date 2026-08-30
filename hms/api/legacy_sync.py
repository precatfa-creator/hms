"""Pull horses out of the legacy studbook Postgres into the Horse doctype.

Connection details live on HMS Settings, so the sandbox and the real system are
a form edit apart. The sync is an upsert keyed on the legacy registration
number, which is also the Horse docname: running it twice changes nothing the
second time.

Only the fields the studbook owns are written. Everything Frappe owns -- the
``doc_*`` attachments, ``status``, ``registration_form`` -- is left alone, so a
re-sync never costs a user their uploads.
"""

import time

import frappe
from frappe import _
from frappe.utils import cint, get_time, now_datetime

# the scheduled job registered in hooks.py, whose cron this module rewrites
SCHEDULED_JOB = "hms.api.legacy_sync.scheduled_sync"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# legacy column -> Horse fieldname. Same-named on both sides today; when the
# real studbook lands with its own names, this is the only thing that moves.
COLUMNS = {
	"name_ar": "name_ar",
	"name_en": "name_en",
	"ueln_no": "ueln_no",
	"microchip_no": "microchip_no",
	"origin": "origin",
	"gender": "gender",
	"color": "color",
	"breed": "breed",
	"date_of_birth": "date_of_birth",
	"place_of_birth": "place_of_birth",
	"current_location": "current_location",
	"life_status": "life_status",
	"death_date": "death_date",
	"notification_date": "notification_date",
	"sire_name_ar": "sire_name_ar",
	"sire_name_en": "sire_name_en",
	"sire_registration_no": "sire_registration_no",
	"sire_origin": "sire_origin",
	"sire_date_of_birth": "sire_date_of_birth",
	"sire_place_of_birth": "sire_place_of_birth",
	"sire_color": "sire_color",
	"sire_breed": "sire_breed",
	"sire_microchip_no": "sire_microchip_no",
	"dam_name_ar": "dam_name_ar",
	"dam_name_en": "dam_name_en",
	"dam_registration_no": "dam_registration_no",
	"dam_origin": "dam_origin",
	"dam_date_of_birth": "dam_date_of_birth",
	"dam_place_of_birth": "dam_place_of_birth",
	"dam_color": "dam_color",
	"dam_breed": "dam_breed",
	"dam_microchip_no": "dam_microchip_no",
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

# a Horse the studbook says nothing about; never written by the sync
FRAPPE_OWNED = ("status", "registration_form", "ownership_history", "name_history")

HISTORY_LIMIT = 20
CONNECT_TIMEOUT = 5


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


def _fetch(connection):
	cursor = connection.cursor()
	cursor.execute(
		f"SELECT registration_no, {', '.join(COLUMNS)} FROM horse ORDER BY registration_no")
	names = ["registration_no"] + list(COLUMNS)
	return [dict(zip(names, row)) for row in cursor.fetchall()]


def _child_rows(connection, table, columns):
	"""Child-table rows for every horse at once, keyed by registration number."""
	cursor = connection.cursor()
	cursor.execute(
		f"SELECT h.registration_no, {', '.join('c.' + c for c in columns)} "
		f"FROM {table} c JOIN horse h ON h.id = c.horse_id ORDER BY h.registration_no, c.idx")
	rows = {}
	for row in cursor.fetchall():
		rows.setdefault(row[0], []).append(dict(zip(columns, row[1:])))
	return rows


def _colors(values):
	"""Make sure every colour the studbook uses exists as a Color, once."""
	wanted = {value for value in values if value}
	existing = set(frappe.get_all("Color", filters={"name": ("in", list(wanted))}, pluck="name"))
	for color in wanted - existing:
		frappe.get_doc({"doctype": "Color", "color": color}).insert(ignore_permissions=True)


def _apply(doc, row, ownership, names):
	"""Copy the studbook's fields onto a Horse. Returns True if anything moved."""
	changed = False
	for column, fieldname in COLUMNS.items():
		value = row.get(column)
		if value in (None, ""):
			continue
		if doc.get(fieldname) != value:
			doc.set(fieldname, value)
			changed = True

	# child tables are replaced wholesale: the studbook is the only writer of
	# them, and diffing rows without a stable key would be guesswork
	if ownership is not None and _differs(doc.ownership_history, ownership):
		doc.set("ownership_history", ownership)
		changed = True
	if names is not None and _differs(doc.name_history, names):
		doc.set("name_history", names)
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
		rows = _fetch(connection)
		ownership = _child_rows(connection, "ownership_log",
		                        ["owner_name_en", "owner_national_id", "from_date", "to_date"])
		names = _child_rows(connection, "name_log", ["name_ar", "name_en", "changed_on"])
	finally:
		connection.close()

	_colors(row.get("color") for row in rows)

	for row in rows:
		registration_no = row["registration_no"]
		try:
			if frappe.db.exists("Horse", registration_no):
				doc = frappe.get_doc("Horse", registration_no)
				if _apply(doc, row, ownership.get(registration_no), names.get(registration_no)):
					doc.save(ignore_permissions=True)
					updated += 1
				else:
					skipped += 1
			else:
				doc = frappe.new_doc("Horse")
				_apply(doc, row, ownership.get(registration_no, []),
				       names.get(registration_no, []))
				# the legacy registration number is the docname, which is what
				# makes a second run an update instead of a duplicate
				doc.insert(ignore_permissions=True, set_name=registration_no)
				created += 1
		except Exception as error:
			frappe.db.rollback()
			failures.append(f"{registration_no}: {error}")
			frappe.log_error(title=f"Studbook sync failed for {registration_no}")

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
