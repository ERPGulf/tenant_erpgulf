// Copyright (c) 2026, ERPGulf and contributors
// For license information, please see license.txt

frappe.query_reports["Technician Performance Summary"] = {
	filters: [
		{
			fieldname: "period",
			label: __("Report Type"),
			fieldtype: "Select",
			options: ["Daily", "Monthly", "Yearly"].join("\n"),
			default: "Monthly",
			reqd: 1,
		},
		{
			fieldname: "date",
			label: __("Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			depends_on: "eval:doc.period == 'Daily'",
			mandatory_depends_on: "eval:doc.period == 'Daily'",
		},
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: [
				"January", "February", "March", "April", "May", "June",
				"July", "August", "September", "October", "November", "December",
			].join("\n"),
			default: new Date().toLocaleString("en-US", { month: "long" }),
			depends_on: "eval:doc.period == 'Monthly'",
			mandatory_depends_on: "eval:doc.period == 'Monthly'",
		},
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: frappe.datetime.get_today().split("-")[0],
			depends_on: "eval:['Monthly', 'Yearly'].includes(doc.period)",
			mandatory_depends_on: "eval:['Monthly', 'Yearly'].includes(doc.period)",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{
			fieldname: "technician",
			label: __("Technician"),
			fieldtype: "Link",
			options: "Employee",
			get_query: () => ({
				filters: { status: "Active" },
			}),
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "idle_hours" && data && data.idle_hours > 0) {
			value = `<span style="color: var(--orange-600)">${value}</span>`;
		}
		if (column.fieldname === "productive_hours" && data && data.productive_hours > 0) {
			value = `<span style="color: var(--green-600)">${value}</span>`;
		}
		return value;
	},
};