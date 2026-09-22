// // Copyright (c) 2026, ERPGulf and contributors
// // For license information, please see license.txt

// frappe.query_reports["Technician Performance Summary"] = {
// 	filters: [
// 		// {
// 		// 	"fieldname": "my_filter",
// 		// 	"label": __("My Filter"),
// 		// 	"fieldtype": "Data",
// 		// 	"reqd": 1,
// 		// },
// 	],
// };
// Copyright (c) 2026, ERPGulf and contributors
// For license information, please see license.txt

frappe.query_reports["Technician Performance Summary"] = {
	filters: [
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: frappe.datetime.now_date().split("-")[0],
			reqd: 1,
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
			reqd: 1,
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
};