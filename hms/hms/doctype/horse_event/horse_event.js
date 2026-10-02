// Copyright (c) 2026, ARD and contributors
// For license information, please see license.txt

// An event is a notice. This is the one button that turns it into paperwork.
frappe.ui.form.on("Horse Event", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.notification_status !== "Processed") {
			frm.add_custom_button(__("Create Transaction"), () => create(frm)).addClass(
				"btn-primary"
			);
		}
		if (frm.doc.notification_status === "New") {
			frm.add_custom_button(__("Acknowledge"), () => set_status(frm, "Acknowledged"));
			frm.add_custom_button(__("Ignore"), () => set_status(frm, "Ignored"));
		}
		if (!frm.doc.horse && frm.doc.unresolved_horse) {
			frm.dashboard.set_headline_alert(
				__("This event names a studbook horse that has not been synced yet."),
				"orange"
			);
		}
	},
});

function set_status(frm, status) {
	frm.set_value("notification_status", status).then(() => frm.save());
}

function create(frm) {
	frm.call({ doc: frm.doc, method: "create_transaction", freeze: true }).then((r) => {
		if (!r.message) return;
		const links = Object.values(r.message).map(([doctype, name]) => {
			const url = frappe.utils.get_form_link(doctype, name);
			// the browser may block a second tab; the alert links it either way
			window.open(url, "_blank");
			return `<a href="${url}" target="_blank">${doctype} ${name}</a>`;
		});
		frappe.show_alert({ message: __("Created {0}", [links.join(", ")]), indicator: "green" });
		frm.reload_doc();
	});
}
