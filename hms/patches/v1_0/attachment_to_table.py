"""Horse Document.attachment (one file) -> the attachments table (many)."""

import frappe


def execute():
	if not frappe.db.has_column("Horse Document", "attachment"):
		return

	rows = frappe.db.sql(
		"""SELECT name, attachment FROM `tabHorse Document`
		   WHERE ifnull(attachment, '') != ''""",
		as_dict=True,
	)
	for row in rows:
		if frappe.db.exists("Horse Document Attachment", {"parent": row.name}):
			continue
		# insert the child row directly: saving the parent would re-run
		# validation on documents the user has not touched
		frappe.get_doc({
			"doctype": "Horse Document Attachment",
			"parent": row.name,
			"parenttype": "Horse Document",
			"parentfield": "attachments",
			"idx": 1,
			"file": row.attachment,
		}).db_insert()

