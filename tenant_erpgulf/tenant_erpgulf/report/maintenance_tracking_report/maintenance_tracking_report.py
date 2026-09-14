import frappe
from frappe import _
from frappe.utils import getdate
 
 
def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data
 
 
def get_columns():
	return [
		{
			"label": _("Tracking #"),
			"fieldname": "tracking_no",
			"fieldtype": "Link",
			"options": "Maintenance Request",
			"width": 150,
		},
		{
			"label": _("Issues / Problems / Deficiencies / Tasks"),
			"fieldname": "issue",
			"fieldtype": "Data",
			"width": 260,
		},
		{
			"label": _("Tower#"),
			"fieldname": "tower",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": _("Floor"),
			"fieldname": "floor",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": _("Location"),
			"fieldname": "location",
			"fieldtype": "Link",
			"options": "Location",
			"width": 160,
		},
		{
			"label": _("Category"),
			"fieldname": "category",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Date"),
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Requested By"),
			"fieldname": "requested_by",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Closure Date"),
			"fieldname": "closure_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Remarks"),
			"fieldname": "remarks",
			"fieldtype": "Data",
			"width": 220,
		},
	]
 
 
def get_conditions(filters):
	"""Build a filters dict for frappe.db.get_all() against Maintenance Request."""
	conditions = {}
 
	if filters.get("from_date") and filters.get("to_date"):
		conditions["date_of_submit"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		conditions["date_of_submit"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		conditions["date_of_submit"] = ["<=", filters.get("to_date")]
 
	if filters.get("customer"):
		conditions["customer"] = filters.get("customer")
 
	if filters.get("status"):
		conditions["status"] = filters.get("status")
 
	if filters.get("maintenance_type"):
		conditions["maintenance_type"] = filters.get("maintenance_type")
 
	if filters.get("location"):
		conditions["location"] = filters.get("location")
 
	if filters.get("priority"):
		conditions["priority"] = filters.get("priority")
 
	return conditions
 
 
def get_data(filters):
	conditions = get_conditions(filters)
 
	mr_fields = [
		"name",
		"description",
		"location",
		"maintenance_log",
		"maintenance_type",
		"customer",
		"date_of_submit",
		"status",
		"custom_status_changed_date",
	]
 
	requests = frappe.db.get_all(
		"Maintenance Request",
		filters=conditions,
		fields=mr_fields,
		order_by="date_of_submit desc, creation desc",
	)
 
	if not requests:
		return []
 
	# ---- batch-fetch linked Asset Maintenance Log rows ------------------
	log_names = sorted({r.maintenance_log for r in requests if r.maintenance_log})
	logs_by_name = {}
	if log_names:
		log_rows = frappe.db.get_all(
			"Asset Maintenance Log",
			filters={"name": ["in", log_names]},
			fields=[
				"name",
				"custom_name_of_task",
				"description",
				"custom_feedback",
				"completion_date",
				"maintenance_status",
			],
		)
		logs_by_name = {row.name: row for row in log_rows}
 
	# ---- batch-fetch linked Location rows --------------------------------
	location_names = sorted({r.location for r in requests if r.location})
	locations_by_name = {}
	if location_names:
		location_fields = ["name", "location_name", "custom_building"]
		if frappe.db.has_column("Location", "custom_floor"):
			location_fields.append("custom_floor")
		location_rows = frappe.db.get_all(
			"Location",
			filters={"name": ["in", location_names]},
			fields=location_fields,
		)
		locations_by_name = {row.name: row for row in location_rows}
 
		if filters.get("tower"):
			# filter the Maintenance Requests down to only those whose Location
			# belongs to the requested tower, after we resolve buildings below
			pass
 
	# ---- batch-fetch linked Building rows --------------------------------
	building_names = sorted(
		{loc.custom_building for loc in locations_by_name.values() if loc.get("custom_building")}
	)
	buildings_by_name = {}
	if building_names:
		building_rows = frappe.db.get_all(
			"Building",
			filters={"name": ["in", building_names]},
			fields=["name", "building_name", "tower_preference"],
		)
		buildings_by_name = {row.name: row for row in building_rows}
 
	# ---- batch-fetch Floor labels (only if the Floor doctype exists) -----
	floor_labels_by_name = {}
	floor_codes = sorted(
		{loc.custom_floor for loc in locations_by_name.values() if loc.get("custom_floor")}
	)
	if floor_codes and frappe.db.exists("DocType", "Floor"):
		floor_meta = frappe.get_meta("Floor")
		floor_label_field = None
		for candidate in ("floor_name", "floor_number", "title"):
			if floor_meta.has_field(candidate):
				floor_label_field = candidate
				break
		if floor_label_field:
			floor_rows = frappe.db.get_all(
				"Floor",
				filters={"name": ["in", floor_codes]},
				fields=["name", floor_label_field],
			)
			floor_labels_by_name = {row.name: row.get(floor_label_field) for row in floor_rows}
 
	closed_statuses = {"Closed", "Completed", "Resolved", "Cancelled"}
 
	data = []
	for r in requests:
		log = logs_by_name.get(r.maintenance_log) or frappe._dict()
		loc = locations_by_name.get(r.location) or frappe._dict()
		building = buildings_by_name.get(loc.get("custom_building")) or frappe._dict()
 
		tower = building.get("tower_preference") or ""
 
		if filters.get("tower") and tower != filters.get("tower"):
			continue
 
		floor_code = loc.get("custom_floor")
		floor = floor_labels_by_name.get(floor_code, floor_code) or ""
 
		issue = log.get("custom_name_of_task") or r.description or ""
		remarks = r.description or log.get("description") or log.get("custom_feedback") or ""
 
		closure_date = log.get("completion_date")
		if not closure_date and r.status in closed_statuses:
			closure_date = r.custom_status_changed_date
 
		data.append(
			{
				"tracking_no": r.name,
				"issue": issue,
				"tower": tower,
				"floor": floor,
				"location": loc.get("location_name") or r.location or "",
				"category": r.maintenance_type or "",
				"date": getdate(r.date_of_submit) if r.date_of_submit else None,
				"requested_by": r.customer or "",
				"status": r.status or "",
				"closure_date": getdate(closure_date) if closure_date else None,
				"remarks": remarks,
			}
		)
 
	return data
 