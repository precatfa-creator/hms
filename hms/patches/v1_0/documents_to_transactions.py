"""Move the Horse's Documents tab into Horse Document transactions.

Each document used to be an ``Attach`` field on the Horse -- one upload per
category, forever, with its companion fields beside it. This lifts every one of
those into a Horse Document row, re-points the File record at it, and only then
lets the old columns go.

The old columns are still in ``tabHorse`` when this runs: Frappe drops a field
from the DocType, not from the table.
"""

import frappe

# old doc_* key -> (category, {Horse Document field: old Horse column})
MOVES = {
	"registration_form": ("Registration Form", {"document_date": "doc_registration_date"}),
	"breeding_certificate": ("Breeding Certificate",
	                         {"reference_no": "doc_breeding_certificate_no"}),
	"dna_card": ("DNA Result / Card", {"doc_status": "doc_dna_status"}),
	"marking": ("Marking", {"document_date": "doc_marking_date",
	                        "reference_no": "doc_marking_by"}),
	"owner_id": ("Owner ID", {"document_date": "doc_owner_id_date"}),
	"passport": ("Passport", {"reference_no": "doc_passport_no"}),
	"export_certificate": ("Export Certificate",
	                       {"document_date": "doc_export_date",
	                        "reference_no": "doc_export_certificate_no"}),
	"covering_certificate": ("Covering Certificate", {"season": "doc_covering_season"}),
	"covering_agreement": ("Covering Agreement",
	                       {"season": "doc_covering_agreement_season"}),
	"owner_change_form": ("Owner Change Form", {"document_date": "doc_owner_change_date"}),
	"death_form": ("Death Form", {"document_date": "doc_death_event_date"}),
	"others": ("Others", {"notes": "doc_others_note"}),
}

def execute():
	rename_columns()
	move_documents()
	seed_event_actions()


def columns():
	return {row.Field for row in frappe.db.sql("DESC `tabHorse`", as_dict=True)}


def rename_columns():
	"""``status`` was our document tally. In StudLib it is the registration
	workflow, so ours moves aside and the name is handed over."""
	present = columns()
	for old, new in (("status", "documents_status"), ("death_date", "date_of_death")):
		if old in present and new in present:
			frappe.db.sql(f"UPDATE `tabHorse` SET `{new}` = `{old}` WHERE `{new}` IS NULL")

	# `status` now means something else entirely; do not leave the old values in it
	if "status" in present:
		frappe.db.sql("UPDATE `tabHorse` SET `status` = NULL WHERE `status` IN "
		              "('Not Yet', 'Partially Completed', 'Completed')")


def move_documents():
	present = columns()
	attach_columns = [f"doc_{key}" for key in MOVES if f"doc_{key}" in present]
	if not attach_columns:
		return

	companion_columns = [
		column for _, mapping in MOVES.values()
		for column in mapping.values() if column in present
	]
	selected = ["name", *attach_columns, *companion_columns]
	where = " OR ".join(f"`{c}` IS NOT NULL AND `{c}` != ''" for c in attach_columns)
	horses = frappe.db.sql(
		f"SELECT {', '.join(f'`{c}`' for c in selected)} FROM `tabHorse` WHERE {where}",
		as_dict=True,
	)

	moved = 0
	for horse in horses:
		for key, (category, mapping) in MOVES.items():
			attachment = horse.get(f"doc_{key}")
			if not attachment:
				continue
			if not frappe.db.exists("Horse Document Category", category):
				continue
			if frappe.db.exists("Horse Document",
			                    {"horse": horse.name, "category": category,
			                     "attachment": attachment}):
				continue

			document = frappe.get_doc({
				"doctype": "Horse Document",
				"horse": horse.name,
				"category": category,
				"attachment": attachment,
				**{field: horse.get(column) for field, column in mapping.items()
				   if horse.get(column)},
			})
			# the old data predates the category rules, so it is taken as it is
			document.flags.ignore_mandatory = True
			document.flags.ignore_validate = True
			document.insert(ignore_permissions=True)
			repoint_file(attachment, horse.name, document.name)
			moved += 1

	frappe.db.commit()
	print(f"moved {moved} document(s) off the Horse")


def repoint_file(url, horse, document):
	"""So the file still shows in the sidebar, and on the right record."""
	frappe.db.sql(
		"""UPDATE `tabFile`
		   SET attached_to_doctype = 'Horse Document',
		       attached_to_name = %s,
		       attached_to_field = 'attachment'
		   WHERE file_url = %s AND attached_to_doctype = 'Horse'
		     AND attached_to_name = %s""",
		(document, url, horse),
	)


def seed_event_actions():
	"""The event types arrive with the fixtures, which are synced after
	patches run, so the real seeding happens in the after_migrate hook. This
	call is here for a site that migrates with the fixtures already in."""
	from hms.api.events import seed_default_actions

	seed_default_actions()
