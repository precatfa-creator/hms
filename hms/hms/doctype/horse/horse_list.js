frappe.listview_settings["Horse"] = {
	get_indicator(doc) {
		const colors = {
			"Not Yet": "red",
			"Partially Completed": "orange",
			"Completed": "green",
		};
		return [__(doc.documents_status), colors[doc.documents_status] || "grey", "documents_status,=," + doc.documents_status];
	},
};
