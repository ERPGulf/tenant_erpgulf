// Copyright (c) 2026, ERPGulf and contributors
// Client-side filter config for the "Maintenance Tracking Report" Script Report.

frappe.query_reports["Maintenance Tracking Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "location",
			label: __("Location"),
			fieldtype: "Link",
			options: "Location",
		},
		{
			fieldname: "tower",
			label: __("Tower#"),
			fieldtype: "Data",
			// Change to a Link/Select against your Building/Tower list if you
			// maintain a fixed set of tower codes (e.g. T1, T2, T3 ...).
		},
		{
			fieldname: "maintenance_type",
			label: __("Category (Maintenance Type)"),
			fieldtype: "Link",
			options: "Maintenance Type",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Open", "Under Process", "Completed", "Closed", "Cancelled"].join("\n"),
		},
		{
			fieldname: "priority",
			label: __("Priority"),
			fieldtype: "Select",
			options: ["", "Low", "Medium", "High"].join("\n"),
		},
	],
};