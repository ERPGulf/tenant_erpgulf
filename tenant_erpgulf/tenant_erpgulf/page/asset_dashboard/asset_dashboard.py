import frappe
from frappe.utils import getdate

WORK_STATUSES = ["New", "In Progress", "On Hold", "Completed"]
OPEN_STATUSES = ["New", "In Progress", "On Hold"]
MAINTENANCE_TYPES = ["Planned", "Reactive"]

# custom_quotation_status values are stored with inconsistent casing
# ("Quotation approved" / "Quotation Approved"), so compare lower-cased.
QUOTE_NOT_REQD = "quotation not reqd"
QUOTE_ISSUED = "quotation issued"
QUOTE_APPROVED = "quotation approved"
QUOTE_PAID = "paid"


@frappe.whitelist()
def get_dashboard_data(from_date=None, to_date=None, building=None, maintenance_type=None):
	frappe.has_permission("Asset Maintenance Log", "read", throw=True)

	conditions, values = _build_conditions(from_date, to_date, building, maintenance_type)

	rows = frappe.db.sql(
		f"""
		SELECT
			l.custom_asset_maintenance_type AS maintenance_type,
			l.custom_employee_work_status AS work_status,
			LOWER(TRIM(l.custom_quotation_status)) AS quotation_status,
			COUNT(*) AS cnt
		FROM `tabAsset Maintenance Log` l
		{_building_join(building)}
		WHERE {conditions}
		GROUP BY 1, 2, 3
		""",
		values,
		as_dict=True,
	)

	durations = frappe.db.sql(
		f"""
		SELECT
			l.custom_asset_maintenance_type AS maintenance_type,
			SUM(l.custom_task_duration) AS total_seconds,
			COUNT(*) AS jobs
		FROM `tabAsset Maintenance Log` l
		{_building_join(building)}
		WHERE {conditions}
			AND l.custom_employee_work_status = 'Completed'
			AND IFNULL(l.custom_task_duration, 0) > 0
		GROUP BY 1
		""",
		values,
		as_dict=True,
	)

	return {
		"status": _status_breakdown(rows),
		"quotations": _quotation_pipeline(rows),
		"duration": _duration_summary(durations),
		"trend": _duration_trend(conditions, values, building),
		"unassigned": {
			"work_orders": sum(r.cnt for r in rows if not r.work_status),
			"quotations": sum(
				r.cnt for r in rows if not r.quotation_status and r.maintenance_type
			),
		},
	}


@frappe.whitelist()
def get_buildings():
	return frappe.get_all(
		"Building", fields=["name", "building_name"], order_by="building_name asc"
	)


def _build_conditions(from_date, to_date, building, maintenance_type):
	conditions = ["l.docstatus < 2"]
	values = {}

	if from_date:
		conditions.append("DATE(l.creation) >= %(from_date)s")
		values["from_date"] = getdate(from_date)
	if to_date:
		conditions.append("DATE(l.creation) <= %(to_date)s")
		values["to_date"] = getdate(to_date)
	if building:
		conditions.append("loc.custom_building = %(building)s")
		values["building"] = building
	if maintenance_type in MAINTENANCE_TYPES:
		conditions.append("l.custom_asset_maintenance_type = %(maintenance_type)s")
		values["maintenance_type"] = maintenance_type

	return " AND ".join(conditions), values


def _building_join(building):
	# Building is only reachable through Asset -> Location, so skip the joins
	# when no building filter is applied.
	if not building:
		return ""
	return """
		LEFT JOIN `tabAsset` a ON a.name = l.asset_name
		LEFT JOIN `tabLocation` loc ON loc.name = a.location
	"""


def _status_breakdown(rows):
	result = {}
	for mtype in MAINTENANCE_TYPES:
		counts = dict.fromkeys(WORK_STATUSES + ["Unassigned"], 0)
		for r in rows:
			if r.maintenance_type != mtype:
				continue
			key = r.work_status if r.work_status in WORK_STATUSES else "Unassigned"
			counts[key] += r.cnt
		result[mtype] = {"counts": counts, "total": sum(counts.values())}
	return result


def _quotation_pipeline(rows):
	issued = approved = paid = no_status = 0
	for r in rows:
		if not r.maintenance_type:
			continue
		if r.quotation_status == QUOTE_ISSUED:
			issued += r.cnt
		elif r.quotation_status == QUOTE_APPROVED:
			approved += r.cnt
		elif r.quotation_status == QUOTE_PAID:
			paid += r.cnt
		elif not r.quotation_status:
			no_status += r.cnt

	# Each stage includes every quote that has moved past it.
	reached_paid = paid
	reached_approved = approved + reached_paid
	reached_issued = issued + reached_approved
	return {
		"requested": reached_issued + no_status,
		"issued": reached_issued,
		"approved": reached_approved,
		"paid": reached_paid,
		"awaiting_approval": issued,
	}


def _duration_summary(durations):
	by_type = {d.maintenance_type: d for d in durations}
	summary = {
		mtype: _to_hours(by_type[mtype].total_seconds / by_type[mtype].jobs)
		if mtype in by_type
		else None
		for mtype in MAINTENANCE_TYPES
	}

	total_jobs = sum(d.jobs for d in durations if d.maintenance_type in MAINTENANCE_TYPES)
	total_seconds = sum(
		d.total_seconds for d in durations if d.maintenance_type in MAINTENANCE_TYPES
	)
	summary["Overall"] = _to_hours(total_seconds / total_jobs if total_jobs else None)
	return summary


def _duration_trend(conditions, values, building):
	return frappe.db.sql(
		f"""
		SELECT
			DATE_FORMAT(COALESCE(l.completion_date, l.modified), '%%Y-%%m') AS month,
			AVG(l.custom_task_duration) / 3600 AS hours
		FROM `tabAsset Maintenance Log` l
		{_building_join(building)}
		WHERE {conditions}
			AND l.custom_employee_work_status = 'Completed'
			AND IFNULL(l.custom_task_duration, 0) > 0
		GROUP BY 1
		ORDER BY 1
		""",
		values,
		as_dict=True,
	)


def _to_hours(seconds):
	return round(seconds / 3600, 1) if seconds else None
