"""
Validation for Asset Maintenance Log -> custom_reschedule_history_table

Rule:
- 1st reschedule entry: its scheduled_date must be >= 1 hour after the
  original Maintenance Request's (maintenance_date + time_slot start).
- Every next entry: its scheduled_date must be >= 1 hour after the
  previous row's scheduled_date.

Wire this up via hooks.py (see bottom of file) instead of editing core
ERPNext files, since Asset Maintenance Log is a standard doctype and
these are custom fields on top of it.
"""

import re
from datetime import timedelta

import frappe
from frappe.utils import get_datetime


def parse_time_slot_start(time_slot):
	"""
	'10-11 AM' -> 10 (24h), '2-3 PM' -> 14, '11-12 PM' -> 11
	Assumes the AM/PM label applies to both numbers in the slot.
	"""
	match = re.match(r"\s*(\d{1,2})\s*-\s*(\d{1,2})\s*(AM|PM)\s*", (time_slot or "").strip(), re.IGNORECASE)
	if not match:
		frappe.throw(f"Unable to parse time slot: {time_slot}")

	start_hour, _end_hour, period = match.groups()
	start_hour = int(start_hour)
	period = period.upper()

	if period == "PM" and start_hour != 12:
		start_hour += 12
	elif period == "AM" and start_hour == 12:
		start_hour = 0

	return start_hour


def get_base_schedule_datetime(asset_maintenance_log_name):
	"""
	Base datetime = the originating Maintenance Request's
	maintenance_date + time_slot start hour.
	Returns None if no Maintenance Request is linked yet.
	"""
	maintenance_request = frappe.db.get_value(
		"Maintenance Request",
		{"maintenance_log": asset_maintenance_log_name},
		["name", "maintenance_date", "time_slot"],
		as_dict=True,
	)

	if not maintenance_request or not maintenance_request.maintenance_date:
		return None

	start_hour = parse_time_slot_start(maintenance_request.time_slot)
	base_dt = get_datetime(maintenance_request.maintenance_date)
	return base_dt.replace(hour=start_hour, minute=0, second=0, microsecond=0)


def validate_reschedule_history(doc, method=None):
	"""
	doc_events hook target for Asset Maintenance Log -> validate.
	Enforces a minimum 1-hour gap, chained through the reschedule rows in order.
	"""
	rows = sorted(doc.get("custom_reschedule_history_table") or [], key=lambda r: r.idx)
	if not rows:
		return

	previous_dt = get_base_schedule_datetime(doc.name)

	for row in rows:
		if not row.scheduled_date:
			# Not mandatory — skip the gap check for this row, keep chaining
			# from whatever the last known scheduled_date was.
			continue

		current_dt = get_datetime(row.scheduled_date)

		if previous_dt:
			min_allowed_dt = previous_dt + timedelta(hours=1)
			if current_dt < min_allowed_dt:
				frappe.throw(
					"Row {0}: Rescheduled date/time must be at least 1 hour after {1} "
					"(earliest allowed: {2}).".format(
						row.idx,
						previous_dt.strftime("%Y-%m-%d %H:%M:%S"),
						min_allowed_dt.strftime("%Y-%m-%d %H:%M:%S"),
					)
				)

		previous_dt = current_dt


# --- hooks.py ---
# doc_events = {
#     "Asset Maintenance Log": {
#         "validate": "your_app.your_module.reschedule_validation.validate_reschedule_history"
#     }
# }