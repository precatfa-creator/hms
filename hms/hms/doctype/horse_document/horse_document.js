// Copyright (c) 2026, ARD and contributors
// For license information, please see license.txt

// The category decides which details this document needs, and what they are
// called. Asking the server once per category keeps that rule in one place.
frappe.ui.form.on("Horse Document", {
	refresh: (frm) => apply_category(frm),
	category: (frm) => apply_category(frm),
});

const FLAGS = {
	needs_document_date: "document_date",
	needs_reference_no: "reference_no",
	needs_doc_status: "doc_status",
	needs_season: "season",
	needs_notes: "notes",
	has_expiry: "expiry_date",
};

function apply_category(frm) {
	const fields = Object.values(FLAGS);
	if (!frm.doc.category) {
		fields.forEach((f) => frm.set_df_property(f, "hidden", 1));
		return;
	}

	frappe.db.get_doc("Horse Document Category", frm.doc.category).then((category) => {
		for (const [flag, field] of Object.entries(FLAGS)) {
			const wanted = Boolean(category[flag]);
			frm.set_df_property(field, "hidden", wanted ? 0 : 1);
			// a note is never mandatory, and expiry is a date the category
			// merely permits
			const required = wanted && field !== "notes" && field !== "expiry_date";
			frm.set_df_property(field, "reqd", required ? 1 : 0);
		}
		if (category.document_date_label) {
			frm.set_df_property("document_date", "label", category.document_date_label);
		}
		if (category.reference_no_label) {
			frm.set_df_property("reference_no", "label", category.reference_no_label);
		}
		frm.refresh_fields();
	});
}
