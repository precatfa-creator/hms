# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

"""An event is a notice, not a state.

The studbook records a DEATH event *and* writes ``horse.date_of_death``; an
EXPORT event *and* ``date_of_exporting``. The horse sync already carries all of
that. So nothing here writes to the Horse -- an event exists to raise a
notification and to start the paperwork, and the two pipelines stay
independent.
"""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document

NEW = "New"
PROCESSED = "Processed"


class HorseEvent(Document):
	def after_insert(self):
		if self.notification_status == NEW:
			self.notify()

	def notify(self):
		"""Frappe's own notification log. No second bell to maintain."""
		role = self.action().get("notify_role") or default_role()
		users = role_users(role)
		if not users:
			return

		subject = _("{0}: {1}").format(
			frappe.db.get_value("Horse Event Type", self.event_type, "description")
			or self.event_type,
			self.horse or self.unresolved_horse or _("unknown horse"),
		)
		enqueue_create_notification(users, {
			"type": "Alert",
			"document_type": self.doctype,
			"document_name": self.name,
			"subject": subject,
			"from_user": frappe.session.user,
		})

	def action(self):
		"""How HMS Settings says to handle this event type."""
		settings = frappe.get_single("HMS Settings")
		for row in settings.event_actions or []:
			if row.event_type == self.event_type and row.enabled:
				return row.as_dict()
		return {}

	@frappe.whitelist()
	def create_transaction(self):
		"""Turn the notice into paperwork: the configured form, the configured
		document category, or both. Returns what it made."""
		if not self.horse:
			frappe.throw(_("Link this event to a horse before creating anything from it."))

		action = self.action()
		if not action:
			frappe.throw(
				_("No enabled action is configured for {0} in HMS Settings.").format(
					self.event_type)
			)

		made = {}
		if action.get("target_doctype") and not self.created_form:
			form = self.build_form(action["target_doctype"])
			self.created_form_type = action["target_doctype"]
			self.created_form = form.name
			made["form"] = form.name

		if action.get("document_category") and not self.created_document:
			document = frappe.get_doc({
				"doctype": "Horse Document",
				"horse": self.horse,
				"category": action["document_category"],
				"document_date": self.event_date,
				"source_event": self.name,
			})
			# the attachment arrives later, so the draft is saved unvalidated
			# for the missing file
			document.flags.ignore_mandatory = True
			document.insert(ignore_permissions=True)
			self.created_document = document.name
			made["document"] = document.name

		if not made:
			frappe.throw(_("This event has already been processed."))

		self.notification_status = PROCESSED
		self.save(ignore_permissions=True)
		return made

	def build_form(self, doctype):
		form = frappe.new_doc(doctype)
		form.horse = self.horse
		if form.meta.has_field("source_event"):
			form.source_event = self.name

		# ponytail: one special case rather than a mapping engine. Add another
		# when a second form needs more than the horse link.
		if doctype == "Owner Change Form":
			new_owner = (self.new_owners or [None])[0]
			if new_owner:
				form.new_owner_name_ar = new_owner.owner_name
				form.new_owner_name_en = new_owner.owner_name
				form.new_owner_national_id = new_owner.national_id
			form.new_ownership_date = self.event_date

		form.flags.ignore_mandatory = True
		form.insert(ignore_permissions=True)
		return form


def default_role():
	return frappe.db.get_single_value("HMS Settings", "event_notify_role") or "System Manager"


def role_users(role):
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"},
	                       pluck="parent")
	return [u for u in set(users) if u not in ("Administrator", "Guest")]
