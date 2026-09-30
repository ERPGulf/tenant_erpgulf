// Copyright (c) 2026, ERPGulf and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer Move Log", {
	refresh(frm) {
		if (frm.doc.location && !frm.is_new()) {
			frm.add_custom_button(__("View Location"), () =>
				frappe.set_route("Form", "Location", frm.doc.location)
			);
		}
	},

	move_in_date(frm) {
		frm.trigger("check_dates");
	},

	move_out_date(frm) {
		frm.trigger("check_dates");
	},

	check_dates(frm) {
		const { move_in_date, move_out_date } = frm.doc;
		if (move_in_date && move_out_date && move_out_date < move_in_date) {
			frappe.msgprint(__("Move Out Date cannot be before Move In Date"));
			frm.set_value("move_out_date", null);
		}
	},

	after_save(frm) {
		if (!frm.doc.location) return;
		const msg = frm.doc.move_out_date && frm.doc.move_out_date <= frappe.datetime.get_today()
			? __("Customer moved out of {0}", [frm.doc.location])
			: __("Location {0} updated with {1}", [frm.doc.location, frm.doc.customer_name || frm.doc.customer]);
		frappe.show_alert({ message: msg, indicator: "green" });
	},
});