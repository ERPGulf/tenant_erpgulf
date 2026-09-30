# Copyright (c) 2026, ERPGulf and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, get_last_day, getdate

MONTH_OPTIONS = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]

# Change this if the "Completion Date" field on Asset Maintenance Log has another fieldname
COMPLETION_DATE_FIELD = "completion_date"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	return columns, data, None, chart


def get_columns():
	return [
		{"label": _("Technician Name"), "fieldname": "technician_name", "fieldtype": "Data", "width": 170},
		{"label": _("Department / Site"), "fieldname": "department", "fieldtype": "Data", "width": 150},
		{"label": _("Period"), "fieldname": "period", "fieldtype": "Data", "width": 120},
		{"label": _("Total Jobs Assigned"), "fieldname": "jobs_assigned", "fieldtype": "Int", "width": 140},
		{"label": _("Jobs Completed"), "fieldname": "jobs_completed", "fieldtype": "Int", "width": 120},
		{"label": _("Pending Jobs"), "fieldname": "pending_jobs", "fieldtype": "Int", "width": 110},
		{"label": _("Working Hours"), "fieldname": "working_hours", "fieldtype": "Float", "precision": 2, "width": 120},
		{"label": _("Productive Hours"), "fieldname": "productive_hours", "fieldtype": "Float", "precision": 2, "width": 130},
		{"label": _("Idle Hours"), "fieldname": "idle_hours", "fieldtype": "Float", "precision": 2, "width": 110},
	]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def get_data(filters):
	from_date, to_date, period_label = get_date_range(filters)

	logs = get_maintenance_logs(from_date, to_date)
	if not logs:
		return []

	# Technician filter (Employee -> user_id / email)
	if filters.get("technician"):
		wanted_email = frappe.db.get_value("Employee", filters.technician, "user_id")
		logs = [d for d in logs if get_technician_key(d) == wanted_email]
		if not logs:
			return []

	emails = list({get_technician_key(d) for d in logs if get_technician_key(d)})
	employees = {
		e.user_id: e
		for e in frappe.get_all(
			"Employee",
			filters={"user_id": ["in", emails or [""]]},
			fields=["name", "employee_name", "department", "user_id"],
		)
	}

	# Department filter
	if filters.get("department"):
		keep = {uid for uid, e in employees.items() if e.department == filters.department}
		logs = [d for d in logs if get_technician_key(d) in keep]
		if not logs:
			return []

	working_hours_by_emp = get_working_hours(
		[e.name for e in employees.values()], from_date, to_date
	)

	# Group logs by technician
	grouped = {}
	for log in logs:
		key = get_technician_key(log) or log.assign_to_name or "Unassigned"
		grouped.setdefault(key, []).append(log)

	rows = []
	for key, group in grouped.items():
		emp = employees.get(key)
		technician_name = emp.employee_name if emp else (group[0].assign_to_name or key)
		department = (emp.department if emp else None) or "-"

		jobs_assigned = len(group)
		jobs_completed = len([g for g in group if is_completed(g)])
		pending_jobs = jobs_assigned - jobs_completed

		# Working Hours  -> Attendance.working_hours
		working_hours = flt(working_hours_by_emp.get(emp.name), 2) if emp else 0.0

		# Productive Hours -> Asset Maintenance Log.custom_task_duration (seconds)
		productive_hours = flt(sum(flt(g.custom_task_duration) for g in group) / 3600, 2)

		# Idle Hours = WH - PH (never below 0)
		idle_hours = flt(max(working_hours - productive_hours, 0), 2)

		rows.append({
			"technician_name": technician_name,
			"department": department,
			"period": period_label,
			"jobs_assigned": jobs_assigned,
			"jobs_completed": jobs_completed,
			"pending_jobs": pending_jobs,
			"working_hours": working_hours,
			"productive_hours": productive_hours,
			"idle_hours": idle_hours,
		})

	rows.sort(key=lambda r: (r["technician_name"] or "").lower())
	return rows


def get_maintenance_logs(from_date, to_date):
	"""Logs whose due_date OR completion_date falls in the period
	(Reactive jobs often have no due_date). Cancelled logs excluded."""

	fields = [
		"name", "task_assignee_email", "custom_assign_to", "assign_to_name",
		"custom_completed", "maintenance_status", "custom_employee_work_status",
		"custom_task_duration",
	]
	base_filters = {"docstatus": ["!=", 2]}

	if frappe.get_meta("Asset Maintenance Log").has_field(COMPLETION_DATE_FIELD):
		return frappe.get_all(
			"Asset Maintenance Log",
			filters=base_filters,
			or_filters=[
				["due_date", "between", [from_date, to_date]],
				[COMPLETION_DATE_FIELD, "between", [from_date, to_date]],
			],
			fields=fields,
		)

	return frappe.get_all(
		"Asset Maintenance Log",
		filters=dict(base_filters, due_date=["between", [from_date, to_date]]),
		fields=fields,
	)


def get_working_hours(employee_names, from_date, to_date):
	"""Sum of Attendance.working_hours per employee for the period."""
	if not employee_names:
		return {}

	records = frappe.get_all(
		"Attendance",
		filters={
			"employee": ["in", employee_names],
			"attendance_date": ["between", [from_date, to_date]],
			"docstatus": 1,
		},
		fields=["employee", "working_hours"],
	)

	totals = {}
	for r in records:
		totals[r.employee] = totals.get(r.employee, 0.0) + flt(r.working_hours)
	return totals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_date_range(filters):
	"""Returns (from_date, to_date, label) for Daily / Monthly / Yearly."""
	period = filters.get("period") or "Monthly"
	today = getdate()

	if period == "Daily":
		day = getdate(filters.get("date") or today)
		return day, day, day.strftime("%d-%m-%Y")

	year = cint(filters.get("year")) or today.year

	if period == "Yearly":
		return getdate(f"{year}-01-01"), getdate(f"{year}-12-31"), str(year)

	# Monthly
	month_val = filters.get("month")
	if month_val in MONTH_OPTIONS:
		month_no = MONTH_OPTIONS.index(month_val) + 1
	else:
		month_no = cint(month_val) or today.month

	from_date = get_first_day(getdate(f"{year}-{month_no:02d}-01"))
	return from_date, get_last_day(from_date), from_date.strftime("%B %Y")


def is_email(value):
	return bool(value) and bool(_EMAIL_RE.match(str(value).strip()))


def get_technician_key(log):
	"""task_assignee_email first, custom_assign_to as fallback (if it's an email)."""
	for candidate in (log.get("task_assignee_email"), log.get("custom_assign_to")):
		if is_email(candidate):
			return candidate.strip()
	return log.get("task_assignee_email") or log.get("custom_assign_to") or None


def is_completed(log):
	return (
		cint(log.custom_completed) == 1
		or log.maintenance_status == "Completed"
		or log.custom_employee_work_status == "Completed"
	)


def get_chart(data):
	if not data:
		return None
	return {
		"data": {
			"labels": [d["technician_name"] for d in data],
			"datasets": [
				{"name": _("Working Hours"), "values": [d["working_hours"] for d in data]},
				{"name": _("Productive Hours"), "values": [d["productive_hours"] for d in data]},
				{"name": _("Idle Hours"), "values": [d["idle_hours"] for d in data]},
			],
		},
		"type": "bar",
		"colors": ["#a6b1c2", "#28a745", "#ffa00a"],
	}