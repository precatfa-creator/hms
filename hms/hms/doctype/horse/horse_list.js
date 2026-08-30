frappe.listview_settings["Horse"] = {
	get_indicator(doc) {
		const colors = {
			"Not Yet": "red",
			"Partially Completed": "orange",
			"Completed": "green",
		};
		return [__(doc.status), colors[doc.status] || "grey", "status,=," + doc.status];
	},
};
