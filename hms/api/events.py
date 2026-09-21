"""Watch the studbook for lifecycle events and raise them here as notifications.

StudLib is a Java application we hold read-only Postgres on: no webhook, no
LISTEN/NOTIFY. So we poll, on the same scheduler the horse sync already uses.

**Why the poll looks back instead of asking for ``id > watermark``.** Postgres
hands out sequence values before the transaction commits, so a transaction
holding event 500 can commit *after* one holding 505. Read at that moment and
505 moves the watermark past 500, which is then never seen again. The query
therefore re-reads a window below the watermark and drops anything whose
``studbook_event_id`` is already here. Re-reading is cheap; a lost change of
owner is not.
"""

import frappe
from frappe import _
from frappe.utils import cint

from hms.api.legacy_sync import _connect, _settings

# how far below the watermark to re-read. Comfortably more than the number of
# events one in-flight transaction window can hold.
LOOKBACK = 200

# StudLib event.horse_sex is a numeric enum
FOAL_SEX = ["Male", "Female", "Stallion", "Broodmare", "Gelding", "Cryptorchid", "Monorchid"]

EVENTS_SQL = """
SELECT e.id, e.date, e.description, e.additional_information,
       e.cover, e.pregnant, e.twins, e.horse_sex,
       et.type AS event_type,
       hp.uuid AS primary_uuid, hs.uuid AS secondary_uuid, ho.uuid AS offspring_uuid,
       c.name AS country_name
FROM event e
LEFT JOIN event_type et ON et.id = e.type_id
LEFT JOIN horse hp ON hp.id = e.horse_primary_id
LEFT JOIN horse hs ON hs.id = e.horse_secondary_id
LEFT JOIN horse ho ON ho.id = e.horse_offspring_id
LEFT JOIN country c ON c.id = e.country_id
WHERE e.id > %s
ORDER BY e.id
"""

OWNERS_SQL = """
SELECT j.event_id, o.id, o.full_name, o.national_id_number
FROM {table} j JOIN owner o ON o.id = j.owner_id
WHERE j.event_id > %s
"""


@frappe.whitelist()
def poll_events():
	"""Read new studbook events. Safe to run again; it skips what it has."""
	frappe.only_for("System Manager")

	settings = _settings()
	if not settings.events_enabled:
		frappe.throw(_("Event polling is turned off in HMS Settings."))

	connection = _connect(settings)
	try:
		watermark = max(cint(settings.last_event_id) - LOOKBACK, 0)

		if not cint(settings.last_event_id) and not settings.event_backfill:
			# First run. Importing years of history would fire a notification
			# per row, so the watermark starts at the end and we notify from
			# here on. Tick "Backfill Past Events" to take the history instead.
			return _skip_history(connection, settings)

		cursor = connection.cursor()
		cursor.execute(EVENTS_SQL, (watermark,))
		columns = [c[0] for c in cursor.description]
		rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
		owners = _owners(connection, watermark)
	finally:
		connection.close()

	created = skipped = 0
	highest = cint(settings.last_event_id)
	for row in rows:
		highest = max(highest, row["id"])
		if frappe.db.exists("Horse Event", {"studbook_event_id": row["id"]}):
			skipped += 1
			continue
		try:
			_insert(row, owners)
			created += 1
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Studbook event {row['id']} failed to import")

	_set_watermark(highest)
	frappe.db.commit()

	return {"created": created, "skipped": skipped, "read": len(rows),
	        "last_event_id": highest}


def _skip_history(connection, settings):
	cursor = connection.cursor()
	cursor.execute("SELECT coalesce(max(id), 0) FROM event")
	highest = cursor.fetchone()[0]
	_set_watermark(highest)
	frappe.db.commit()
	return {"created": 0, "skipped": 0, "read": 0, "last_event_id": highest,
	        "message": _("Starting from event {0}. Past events were not imported.").format(
		        highest)}


def _set_watermark(value):
	frappe.db.set_single_value("HMS Settings", "last_event_id", value)
	frappe.db.set_single_value("HMS Settings", "last_event_poll", frappe.utils.now_datetime())


def _owners(connection, watermark):
	"""Old and new owners for every event in the window, by event id."""
	out = {}
	for side, table in (("old_owners", "event_old_owner"), ("new_owners", "event_new_owner")):
		cursor = connection.cursor()
		cursor.execute(OWNERS_SQL.format(table=table), (watermark,))
		for event_id, owner_id, full_name, national_id in cursor.fetchall():
			out.setdefault(event_id, {}).setdefault(side, []).append({
				"studbook_owner_id": owner_id,
				"owner_name": full_name,
				"national_id": national_id,
				"party": _local_owner(owner_id),
			})
	return out


def _local_owner(studbook_owner_id):
	return frappe.db.get_value("Horse Owner", {"studbook_id": studbook_owner_id}, "name")


def _horse(uuid):
	if not uuid:
		return None
	return frappe.db.get_value("Horse", {"studbook_uuid": str(uuid)}, "name")


def _insert(row, owners):
	event_type = row.get("event_type")
	if event_type and not frappe.db.exists("Horse Event Type", event_type):
		frappe.get_doc({"doctype": "Horse Event Type", "event_type": event_type,
		                "description": event_type.replace("_", " ").title()}).insert(
			ignore_permissions=True)

	primary = _horse(row.get("primary_uuid"))
	sex = row.get("horse_sex")
	doc = frappe.get_doc({
		"doctype": "Horse Event",
		"studbook_event_id": row["id"],
		"event_type": event_type,
		"event_date": row.get("date"),
		"horse": primary,
		# an event can arrive before the horse it names; the next horse sync
		# calls resolve_unlinked() and fills this in
		"unresolved_horse": None if primary else (row.get("primary_uuid") and
		                                          str(row["primary_uuid"])),
		"secondary_horse": _horse(row.get("secondary_uuid")),
		"offspring_horse": _horse(row.get("offspring_uuid")),
		"event_country": _country(row.get("country_name")),
		"description": row.get("description"),
		"additional_information": row.get("additional_information"),
		"cover": 1 if row.get("cover") else 0,
		"pregnant": 1 if row.get("pregnant") else 0,
		"twins": 1 if row.get("twins") else 0,
		"foal_sex": FOAL_SEX[sex] if sex is not None and 0 <= sex < len(FOAL_SEX) else None,
		"old_owners": owners.get(row["id"], {}).get("old_owners", []),
		"new_owners": owners.get(row["id"], {}).get("new_owners", []),
	})
	doc.insert(ignore_permissions=True)
	return doc


def _country(name):
	return name if name and frappe.db.exists("Studbook Country", name) else None


def resolve_unlinked():
	"""Link events whose horse only arrived in a later sync."""
	pending = frappe.get_all("Horse Event",
	                         filters={"horse": ("is", "not set"),
	                                  "unresolved_horse": ("is", "set")},
	                         fields=["name", "unresolved_horse"])
	linked = 0
	for event in pending:
		horse = _horse(event.unresolved_horse)
		if not horse:
			continue
		frappe.db.set_value("Horse Event", event.name,
		                    {"horse": horse, "unresolved_horse": None})
		linked += 1
	return linked


# event type -> what it should create, as a starting point the user can rewire
DEFAULT_ACTIONS = [
	("CHANGE_OWNER", "Owner Change Form", "Owner Change Form"),
	("DEATH", None, "Death Form"),
	("EXPORT", None, "Export Certificate"),
	("NEW_FOAL", "Registration Form for Local Horses", None),
	("IMPORT", None, "Passport"),
	("GELDING", None, None),
	("COVERED", None, None),
	("FOAL_ABORTION", None, None),
]


def seed_default_actions():
	"""Give a fresh site one action per event type to start from.

	Runs after every migrate rather than from a patch, because the event types
	it points at arrive with the fixtures, which are synced after patches.
	Never touches a table that already has rows.
	"""
	settings = frappe.get_single("HMS Settings")
	if settings.event_actions:
		return 0

	for event_type, target, category in DEFAULT_ACTIONS:
		if not frappe.db.exists("Horse Event Type", event_type):
			continue
		settings.append("event_actions", {
			"event_type": event_type,
			"enabled": 1,
			"target_doctype": target if target and frappe.db.exists(
				"DocType", target) else None,
			"document_category": category if category and frappe.db.exists(
				"Horse Document Category", category) else None,
		})
	if not settings.event_actions:
		return 0
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	return len(settings.event_actions)


def scheduled_poll():
	"""Scheduler entry point. Quiet when there is nothing to do."""
	settings = frappe.get_single("HMS Settings")
	if not settings.studbook_enabled or not settings.events_enabled:
		return
	frappe.set_user("Administrator")
	poll_events()
