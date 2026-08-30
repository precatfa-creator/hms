// Copyright (c) 2026, ARD and contributors
// For license information, please see license.txt

// Type a letter into either name field and the studbook API is searched. Picking
// a name fills identity, pedigree and ownership in one go.
frappe.ui.form.on("Horse", {
	refresh(frm) {
		hms.studbook.bind_search(frm, "name_ar", { lang: "ar" });
		hms.studbook.bind_search(frm, "name_en", { lang: "en" });
	},
});
