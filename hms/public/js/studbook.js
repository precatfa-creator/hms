// Copyright (c) 2026, ARD and contributors
// For license information, please see license.txt

// Type-ahead against the studbook API. Bound to a name field, it searches as you
// type and fills a whole block of fields once you pick a horse.
//
//   hms.studbook.bind_search(frm, "name_en", { lang: "en" });            // the horse itself
//   hms.studbook.bind_search(frm, "sire_name_en", { prefix: "sire" });   // its sire

frappe.provide("hms.studbook");

hms.studbook.bind_search = function (frm, fieldname, options = {}) {
	const { lang = "en", prefix = null } = options;
	const field = frm.fields_dict[fieldname];
	if (!field || !field.$input || field.$input.data("studbook-bound")) return;

	const input = field.$input;
	const awesomplete = new Awesomplete(input.get(0), {
		minChars: 1,
		maxItems: 25,
		autoFirst: false,
		filter: () => true,
		item(item) {
			const el = document.createElement("li");
			el.textContent = item.label;
			return el;
		},
	});
	input.data("studbook-bound", true);

	const search = frappe.utils.debounce(() => {
		const txt = input.val();
		if (!txt) return;
		frappe
			.call({ method: "hms.api.studbook.search_horses", args: { txt, lang }, quiet: true })
			.then((r) => {
				awesomplete.list = (r.message || []).map((horse) => ({
					label: [horse.name_ar, horse.name_en, horse.registration_no]
						.filter(Boolean)
						.join("  ·  "),
					value: horse.ref,
				}));
			});
	}, 300);

	input.on("input", search);
	input.on("awesomplete-selectcomplete", (event) => {
		const ref = event.originalEvent.text.value;
		const method = prefix ? "hms.api.studbook.get_parent" : "hms.api.studbook.get_horse";
		const args = prefix
			? { ref, prefix, doctype: frm.doctype }
			: { ref, doctype: frm.doctype };

		frappe
			.call({
				method,
				args,
				freeze: true,
				freeze_message: __("Reading the studbook…"),
			})
			.then((r) => {
				if (!r.message || !Object.keys(r.message).length) return;
				frm.set_value(r.message);
				frm.refresh();
				frappe.show_alert({
					message: prefix
						? __("{0} filled from the studbook", [frappe.unscrub(prefix)])
						: __("Filled from the studbook"),
					indicator: "green",
				});
			});
	});
};
