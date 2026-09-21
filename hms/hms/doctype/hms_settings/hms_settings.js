// Copyright (c) 2026, ARD and contributors
// For license information, please see license.txt

frappe.ui.form.on("HMS Settings", {
	refresh(frm) {
		// top level rather than a group: two buttons do not earn a dropdown,
		// and a highlighted item inside one reads as a mistake
		frm.add_custom_button(__("Test Connection"), () => test_connection(frm));
		frm.add_custom_button(__("Sync Horses Now"), () => confirm_sync(frm));
		if (frm.doc.events_enabled) {
			frm.add_custom_button(__("Poll Events Now"), () => poll_events(frm));
		}

		show_last_sync(frm);
		show_schedule(frm);
	},

	sync_frequency: (frm) => show_schedule(frm),
	sync_time: (frm) => show_schedule(frm),
	sync_day_of_week: (frm) => show_schedule(frm),
	sync_day_of_month: (frm) => show_schedule(frm),
});

function show_schedule(frm) {
	const wrapper = frm.get_field("schedule_help")?.$wrapper;
	if (!wrapper) return;

	if (!frm.doc.sync_frequency || frm.doc.sync_frequency === "Never") {
		wrapper.empty();
		return;
	}

	const at = frappe.datetime.str_to_user(`2000-01-01 ${frm.doc.sync_time || "00:00:00"}`).split(" ").slice(1).join(" ");
	const when = {
		Hourly: __("Every hour, on the hour."),
		Daily: __("Every day at {0}.", [at]),
		Weekly: __("Every {0} at {1}.", [__(frm.doc.sync_day_of_week || "Monday"), at]),
		Monthly: __("Day {0} of every month at {1}.", [frm.doc.sync_day_of_month || 1, at]),
	}[frm.doc.sync_frequency];

	wrapper.html(`
		<div class="text-muted small">
			${when}
			${frm.is_dirty() ? `<br><b>${__("Save to apply.")}</b>` : ""}
			<br>
			<a href="/app/scheduled-job-type?method=hms.api.legacy_sync.scheduled_sync">
				${__("Scheduled Job")}
			</a>
			&middot;
			<a href="/app/scheduled-job-log?scheduled_job_type=legacy_sync.scheduled_sync">
				${__("Run history")}
			</a>
		</div>
	`);
}

function test_connection(frm) {
	frappe.call({
		method: "hms.api.legacy_sync.test_connection",
		freeze: true,
		freeze_message: __("Reaching the studbook…"),
		callback: ({ message }) => {
			frappe.msgprint({
				title: __("Connected"),
				indicator: "green",
				message: __("The studbook holds {0} horses.", [message.horses]),
			});
		},
	});
}

function confirm_sync(frm) {
	frappe.confirm(
		__("Read every horse from the studbook into this site?") +
			"<br><br>" +
			__("Horses already here are updated in place, so nothing you have uploaded is lost."),
		() => run_sync(frm)
	);
}

function run_sync(frm) {
	frappe.call({
		method: "hms.api.legacy_sync.sync_horses",
		freeze: true,
		freeze_message: __("Reading the studbook…"),
		callback: ({ message }) => {
			frm.reload_doc();
			frappe.msgprint({
				title: __("Sync finished"),
				indicator: message.outcome === "Success" ? "green" : "orange",
				message: [
					__("Created: {0}", [message.created]),
					__("Updated: {0}", [message.updated]),
					__("Unchanged: {0}", [message.skipped]),
					__("Failed: {0}", [message.failed]),
					"",
					message.message,
				].join("<br>"),
			});
		},
	});
}

function show_last_sync(frm) {
	if (!frm.doc.last_sync_on) {
		frm.dashboard.clear_headline();
		return;
	}

	const colours = { Success: "green", Partial: "orange", Failed: "red" };
	frm.dashboard.set_headline(
		__("Last synced {0} by {1} — {2} created, {3} updated, {4} unchanged", [
			frappe.datetime.comment_when(frm.doc.last_sync_on),
			frm.doc.last_sync_by,
			frm.doc.last_sync_created,
			frm.doc.last_sync_updated,
			frm.doc.last_sync_skipped,
		]),
		colours[frm.doc.last_sync_outcome] || "blue"
	);
}

function poll_events(frm) {
	frappe.call({ method: "hms.api.events.poll_events", freeze: true }).then((r) => {
		const result = r.message;
		if (!result) return;
		frappe.msgprint({
			title: __("Studbook Events"),
			indicator: "green",
			message:
				result.message ||
				__("{0} new, {1} already here, up to event {2}.", [
					result.created,
					result.skipped,
					result.last_event_id,
				]),
		});
		frm.reload_doc();
	});
}
