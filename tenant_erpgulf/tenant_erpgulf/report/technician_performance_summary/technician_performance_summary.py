# Copyright (c) 2026, ERPGulf and contributors
# For license information, please see license.txt
#
# Technician Performance Summary  -  Script Report
# ==================================================
# Built from the doctypes described for this app:
#   - Employee                  -> technician identity / department / designation
#   - ToDo                      -> (not queried directly here; Asset Maintenance Log
#                                    already carries task_assignee_email, so we read
#                                    from there instead of re-deriving it from ToDo)
#   - Asset Maintenance Log     -> one row per job: task_assignee_email, custom_rating,
#                                   custom_completed, maintenance_status, due_date, creation
#   - Maintenance Request       -> maintenance_log (link back to the AML), time_slot,
#                                   maintenance_date  ->  used to work out how promptly
#                                   the technician responded to a scheduled job
#
# A few columns in the requested layout (Safety Compliance, and to a lesser extent
# Supervisor Remarks) have no corresponding field anywhere in the schema that was
# shared, so they are best-effort / placeholders. Search this file for "ASSUMPTION"
# and "TODO" to see every place a judgement call was made — adjust freely once you
# confirm the real field/doctype names in your app.

import re

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, get_last_day, getdate, time_diff_in_hours

MONTH_OPTIONS = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]

# rating (0-5 scale, see normalize_rating) -> label, checked top to bottom
RATING_BUCKETS = [
	(4.0, "Excellent"),
	(3.0, "Good"),
	(2.0, "Average"),
	(0.0, "Needs Improvement"),
]

# ASSUMPTION: "custom_supervisor_alert" is a child table on Asset Maintenance Log.
# Since its child doctype fields weren't confirmed, we probe a few likely
# fieldnames and use the first one that has a value. Update this list (or just
# hardcode the real fieldname) once you check the child doctype definition.
SUPERVISOR_REMARK_FIELDS = ["remark", "remarks", "note", "comment", "alert", "description"]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	return columns, data, None, chart


def get_columns():
	return [
		{"label": _("Technician Name"), "fieldname": "technician_name", "fieldtype": "Data", "width": 160},
		{"label": _("Department / Site"), "fieldname": "department", "fieldtype": "Data", "width": 150},
		{"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 110},
		{"label": _("Total Jobs Assigned"), "fieldname": "jobs_assigned", "fieldtype": "Int", "width": 130},
		{"label": _("Jobs Completed"), "fieldname": "jobs_completed", "fieldtype": "Int", "width": 120},
		{"label": _("Pending Jobs"), "fieldname": "pending_jobs", "fieldtype": "Int", "width": 110},
		{"label": _("Attendance %"), "fieldname": "attendance", "fieldtype": "Data", "width": 110},
		{"label": _("Punctuality %"), "fieldname": "punctuality", "fieldtype": "Data", "width": 110},
		{"label": _("Avg Response Time"), "fieldname": "response_time", "fieldtype": "Data", "width": 140},
		{"label": _("Quality of Work"), "fieldname": "quality_of_work", "fieldtype": "Data", "width": 130},
		{"label": _("Safety Compliance"), "fieldname": "safety_compliance", "fieldtype": "Data", "width": 130},
		{"label": _("Supervisor Remarks"), "fieldname": "supervisor_remarks", "fieldtype": "Data", "width": 220},
		{"label": _("Overall Performance Rating"), "fieldname": "overall_rating", "fieldtype": "Data", "width": 180},
	]


def get_data(filters):
	from_date, to_date, month_label = get_date_range(filters)

	log_filters = {"due_date": ["between", [from_date, to_date]]}

	if filters.get("technician"):
		email = frappe.db.get_value("Employee", filters.get("technician"), "user_id")
		if email:
			log_filters["task_assignee_email"] = email

	logs = frappe.get_all(
		"Asset Maintenance Log",
		filters=log_filters,
		fields=[
			"name", "task_assignee_email", "assign_to_name", "custom_rating",
			"custom_completed", "maintenance_status", "due_date", "creation",
		],
	)
	if not logs:
		return []

	emails = list({d.task_assignee_email for d in logs if d.task_assignee_email})
	employees = {
		e.user_id: e
		for e in frappe.get_all(
			"Employee",
			filters={"user_id": ["in", emails]} if emails else {"name": ["in", []]},
			fields=["employee_name", "department", "designation", "user_id"],
		)
	}

	if filters.get("department"):
		wanted_dept = filters.get("department")
		keep_emails = {uid for uid, e in employees.items() if e.department == wanted_dept}
		logs = [d for d in logs if d.task_assignee_email in keep_emails]
		if not logs:
			return []

	log_names = [d.name for d in logs]

	# Maintenance Request carries the *scheduled* slot for a job (maintenance_date +
	# time_slot). We use that to see how promptly the technician's logged work
	# (Asset Maintenance Log.creation) followed the scheduled slot start.
	mr_records = frappe.get_all(
		"Maintenance Request",
		filters={"maintenance_log": ["in", log_names]},
		fields=["maintenance_log", "time_slot", "maintenance_date"],
	)
	mr_by_log = {}
	for mr in mr_records:
		mr_by_log.setdefault(mr.maintenance_log, []).append(mr)

	grouped = {}
	for log in logs:
		key = log.task_assignee_email or log.assign_to_name or "Unassigned"
		grouped.setdefault(key, []).append(log)

	rows = []
	for key, group in grouped.items():
		emp = employees.get(key)
		technician_name = emp.employee_name if emp else (group[0].assign_to_name or key)
		department = (emp.department if emp else None) or "-"

		jobs_assigned = len(group)
		jobs_completed = len(
			[g for g in group if cint(g.custom_completed) == 1 or g.maintenance_status == "Completed"]
		)
		pending_jobs = jobs_assigned - jobs_completed

		# ASSUMPTION: "Punctuality" is approximated as the share of jobs that never
		# carried the "Overdue" maintenance_status. There was no attendance-clock /
		# check-in-time field in the shared schema to measure punctuality directly.
		overdue = len([g for g in group if g.maintenance_status == "Overdue"])
		punctuality = round((jobs_assigned - overdue) / jobs_assigned * 100, 1) if jobs_assigned else 0

		avg_rating_raw = average([flt(g.custom_rating) for g in group if flt(g.custom_rating) > 0])
		rating_0_to_5 = normalize_rating(avg_rating_raw)
		overall_rating = f"{rating_0_to_5} / 5" if rating_0_to_5 is not None else "N/A"
		quality_of_work = rating_to_label(rating_0_to_5)

		response_hours = []
		for g in group:
			for mr in mr_by_log.get(g.name, []):
				slot_start = combine_slot_start(mr.maintenance_date, mr.time_slot)
				if slot_start and g.creation:
					diff = time_diff_in_hours(get_datetime(g.creation), slot_start)
					if diff >= 0:
						response_hours.append(diff)
		avg_response = average(response_hours)
		response_time = f"{round(avg_response, 2)} hrs" if avg_response is not None else "N/A"

		attendance = get_attendance_pct(key, from_date, to_date)

		# TODO: no safety-inspection / incident doctype was shared, so this column
		# is left as a placeholder. Wire it up once that source is confirmed.
		safety_compliance = "N/A"

		supervisor_remarks = get_supervisor_remarks(group)

		rows.append(
			{
				"technician_name": technician_name,
				"department": department,
				"month": month_label,
				"jobs_assigned": jobs_assigned,
				"jobs_completed": jobs_completed,
				"pending_jobs": pending_jobs,
				"attendance": attendance,
				"punctuality": f"{punctuality}%",
				"response_time": response_time,
				"quality_of_work": quality_of_work,
				"safety_compliance": safety_compliance,
				"supervisor_remarks": supervisor_remarks,
				"overall_rating": overall_rating,
			}
		)

	rows.sort(key=lambda r: (r["technician_name"] or "").lower())
	return rows


def get_date_range(filters):
	year = cint(filters.get("year")) or getdate().year
	month_val = filters.get("month")
	if month_val:
		month_no = MONTH_OPTIONS.index(month_val) + 1 if month_val in MONTH_OPTIONS else cint(month_val)
	else:
		month_no = getdate().month
	from_date = getdate(f"{year}-{month_no:02d}-01")
	to_date = get_last_day(from_date)
	month_label = from_date.strftime("%B %Y")
	return from_date, to_date, month_label


def parse_slot_start_hour(time_slot):
	"""Best-effort parser for strings like '10-11 AM', '2-3 PM', '11-1 PM'.

	ASSUMPTION: this covers the "H-H AM/PM" style seen in the sample data
	(time_slot: "10-11 AM"). If your slots are formatted differently
	(e.g. "10:00 - 11:00"), extend the regex below.
	"""
	if not time_slot:
		return None
	slot = time_slot.strip().replace("–", "-")
	m = re.match(r"^\s*(\d{1,2})(?::(\d{2}))?\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?\s*$", slot, re.IGNORECASE)
	if not m:
		return None
	h1, m1, h2, _h2m, ap = m.groups()
	h1 = int(h1)
	m1 = int(m1 or 0)
	ap = (ap or "AM").upper()
	h2 = int(h2)
	if ap == "PM":
		# e.g. "11-1 PM" => slot runs 11 AM to 1 PM, so the first hour (11) is
		# still in the AM side of the clock when it's larger than the second.
		hour_24 = h1 % 12 if h2 < h1 else (h1 % 12) + 12
	else:
		hour_24 = h1 % 12
	return hour_24, m1


def combine_slot_start(maintenance_date, time_slot):
	if not maintenance_date:
		return None
	parsed = parse_slot_start_hour(time_slot)
	if not parsed:
		return get_datetime(maintenance_date)
	hour, minute = parsed
	return get_datetime(f"{getdate(maintenance_date)} {hour:02d}:{minute:02d}:00")


def normalize_rating(avg_raw):
	"""Frappe's standard 'Rating' fieldtype stores a fraction between 0 and 1
	(e.g. 3 of 5 stars = 0.6). If custom_rating uses that fieldtype, this
	converts the average to a 0-5 scale for display. If custom_rating already
	stores 0-5 directly, values above 1 pass through unchanged.
	"""
	if avg_raw is None:
		return None
	return round(avg_raw * 5, 2) if avg_raw <= 1 else round(avg_raw, 2)


def rating_to_label(rating_0_to_5):
	if rating_0_to_5 is None:
		return "N/A"
	for threshold, label in RATING_BUCKETS:
		if rating_0_to_5 >= threshold:
			return label
	return "Needs Improvement"


def get_attendance_pct(email, from_date, to_date):
	"""ASSUMPTION: attendance is tracked in the standard Attendance doctype
	(employee, attendance_date, status, docstatus). If your app doesn't use
	it, or uses a different doctype, this quietly returns 'N/A' instead of
	failing the whole report.
	"""
	employee_name = frappe.db.get_value("Employee", {"user_id": email}, "name")
	if not employee_name:
		return "N/A"
	try:
		records = frappe.get_all(
			"Attendance",
			filters={
				"employee": employee_name,
				"attendance_date": ["between", [from_date, to_date]],
				"docstatus": 1,
			},
			fields=["status"],
		)
	except Exception:
		return "N/A"
	if not records:
		return "N/A"
	present_weight = {"Present": 1, "Work From Home": 1, "Half Day": 0.5, "On Leave": 0, "Absent": 0}
	present = sum(present_weight.get(r.status, 0) for r in records)
	total_marked = len(records)
	return f"{round(present / total_marked * 100, 1)}%" if total_marked else "N/A"


def get_supervisor_remarks(group):
	remarks = []
	for g in group:
		try:
			doc = frappe.get_doc("Asset Maintenance Log", g.name)
			for row in doc.get("custom_supervisor_alert") or []:
				for fname in SUPERVISOR_REMARK_FIELDS:
					val = row.get(fname)
					if val:
						remarks.append(val)
						break
		except Exception:
			continue
	seen = []
	for r in remarks:
		if r not in seen:
			seen.append(r)
	return "; ".join(seen[:3]) if seen else "-"


def average(values):
	values = [v for v in values if v is not None]
	return round(sum(values) / len(values), 4) if values else None


def get_chart(data):
	if not data:
		return None
	return {
		"data": {
			"labels": [d["technician_name"] for d in data],
			"datasets": [
				{"name": _("Jobs Assigned"), "values": [d["jobs_assigned"] for d in data]},
				{"name": _("Jobs Completed"), "values": [d["jobs_completed"] for d in data]},
			],
		},
		"type": "bar",
		"colors": ["#a6b1c2", "#28a745"],
	}