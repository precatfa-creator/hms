frappe.listview_settings["Horse Event"] = {
	get_indicator(doc) {
		const colors = {
			New: "orange",
			Acknowledged: "blue",
			Processed: "green",
			Ignored: "grey",
		};
		return [
			__(doc.notification_status),
			colors[doc.notification_status] || "grey",
			"notification_status,=," + doc.notification_status,
		];
	},
};
