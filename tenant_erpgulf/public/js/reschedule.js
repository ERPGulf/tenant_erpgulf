// Client-side companion for the server-side check in reschedule_validation.py.
// Gives instant feedback in the child table instead of waiting for save.
// Add this to asset_maintenance_log.js (custom script or app JS file).

frappe.ui.form.on("Reschedule History", {
	scheduled_date: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.scheduled_date) return;

		const rows = (frm.doc.custom_reschedule_history_table || []).sort((a, b) => a.idx - b.idx);
		const idx = rows.findIndex((r) => r.name === cdn);

		frappe.call({
			method: "tenant_erpgulf.reschedule_validation.get_base_schedule_datetime",
			args: { asset_maintenance_log_name: frm.doc.name },
			callback: function (r) {
				let previous_dt = r.message; // base datetime from Maintenance Request, or null
				for (let i = 0; i < idx; i++) {
					if (rows[i].scheduled_date) previous_dt = rows[i].scheduled_date;
				}

				if (!previous_dt) return;

				const min_allowed = frappe.datetime.add_days(previous_dt, 0);
				const min_dt = moment(previous_dt).add(1, "hours");
				const current_dt = moment(row.scheduled_date);

				if (current_dt.isBefore(min_dt)) {
					frappe.model.set_value(cdt, cdn, "scheduled_date", "");
					frappe.msgprint(
						__("Rescheduled date/time must be at least 1 hour after {0} (earliest allowed: {1}).", [
							moment(previous_dt).format("YYYY-MM-DD HH:mm:ss"),
							min_dt.format("YYYY-MM-DD HH:mm:ss"),
						])
					);
				}
			},
		});
	},
});

// Note: get_base_schedule_datetime needs @frappe.whitelist() added if you
// expose it as a callable method for this client-side check. The server-side
// validate() in reschedule_validation.py is the source of truth either way —
// this JS is just UX, not a substitute for it.