// Copyright (c) 2026, ARD and contributors
// For license information, please see license.txt

// The sire and dam name fields search the same studbook API. Picking a horse
// fills that whole parent block: registration number, origin, birth, colour,
// breed and microchip.
frappe.ui.form.on("Registration Form for Local Horses", {
	refresh(frm) {
		hms.studbook.bind_search(frm, "sire_name_ar", { lang: "ar", prefix: "sire" });
		hms.studbook.bind_search(frm, "sire_name_en", { lang: "en", prefix: "sire" });
		hms.studbook.bind_search(frm, "dam_name_ar", { lang: "ar", prefix: "dam" });
		hms.studbook.bind_search(frm, "dam_name_en", { lang: "en", prefix: "dam" });
	},
});
