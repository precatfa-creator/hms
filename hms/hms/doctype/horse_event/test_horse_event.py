# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms.api.events import resolve_unlinked
from hms.hms.testing import make_horse


def make_event(event_type="CHANGE_OWNER", **kwargs):
	values = {
		"doctype": "Horse Event",
		"event_type": event_type,
		"event_date": "2026-02-09",
		"notification_status": "New",
	}
	values.update(kwargs)
	return frappe.get_doc(values).insert()


class TestHorseEvent(FrappeTestCase):
	def test_an_event_raises_a_notification(self):
		horse = make_horse("Notified Horse")
		event = make_event(horse=horse.name)
		self.assertEqual(
			frappe.db.count("Notification Log",
			                {"document_type": "Horse Event", "document_name": event.name}),
			len(non_admin_system_managers()),
		)

	def test_change_of_owner_becomes_a_form_and_a_document(self):
		horse = make_horse("Transferred Horse")
		event = make_event(horse=horse.name)
		event.append("new_owners", {"owner_name": "New Owner Ltd",
		                            "national_id": "99887766"})
		event.save()

		made = event.create_transaction()
		event.reload()

		self.assertEqual(event.notification_status, "Processed")
		self.assertEqual(made["form"], event.created_form)
		self.assertEqual(event.created_form_type, "Owner Change Form")

		form = frappe.get_doc("Owner Change Form", event.created_form)
		self.assertEqual(form.horse, horse.name)
		self.assertEqual(form.new_owner_name_en, "New Owner Ltd")
		self.assertEqual(form.new_owner_national_id, "99887766")
		self.assertEqual(str(form.new_ownership_date), "2026-02-09")
		self.assertEqual(form.source_event, event.name)

		document = frappe.get_doc("Horse Document", event.created_document)
		self.assertEqual(document.category, "Owner Change Form")
		self.assertEqual(document.source_event, event.name)
		self.assertEqual(document.horse, horse.name)

	def test_processing_twice_is_refused(self):
		event = make_event(horse=make_horse("Twice Horse").name)
		event.create_transaction()
		event.reload()
		self.assertRaises(frappe.ValidationError, event.create_transaction)

	def test_an_event_without_a_horse_cannot_be_processed(self):
		event = make_event(unresolved_horse="deadbeef-0000-4000-8000-000000000000")
		self.assertRaises(frappe.ValidationError, event.create_transaction)

	def test_an_event_type_with_no_action_is_refused(self):
		settings = frappe.get_single("HMS Settings")
		for row in settings.event_actions:
			if row.event_type == "GELDING":
				row.enabled = 0
		settings.save()

		event = make_event("GELDING", horse=make_horse("Gelded Horse").name)
		self.assertRaises(frappe.ValidationError, event.create_transaction)

	def test_an_event_finds_its_horse_on_a_later_sync(self):
		"""An event can arrive before the horse it names."""
		uuid = "abcdef01-0000-4000-8000-000000000001"
		event = make_event(unresolved_horse=uuid)
		self.assertFalse(event.horse)

		self.assertEqual(resolve_unlinked(), 0, "nothing to link to yet")

		horse = make_horse("Late Horse", studbook_uuid=uuid)
		self.assertEqual(resolve_unlinked(), 1)

		event.reload()
		self.assertEqual(event.horse, horse.name)
		self.assertFalse(event.unresolved_horse)


def non_admin_system_managers():
	role = frappe.db.get_single_value("HMS Settings", "event_notify_role") or "System Manager"
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"},
	                       pluck="parent")
	return [u for u in set(users) if u not in ("Administrator", "Guest")]
