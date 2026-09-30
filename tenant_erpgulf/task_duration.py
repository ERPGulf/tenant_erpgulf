
# import json
 
# import frappe
# from frappe.utils import now_datetime, time_diff_in_seconds
 
# COMPLETED_STATUS = "Completed"
# DURATION_FIELD = "custom_task_duration"
 
# # Which field holds "who it was assigned to" for each maintenance type.
# ASSIGN_FIELD_BY_TYPE = {
#     "Planned": "assign_to_name",
#     "Reactive": "custom_assign_to",
# }
 
 
# # ---------------------------------------------------------------------------
# # Live hook - wire this to "validate" in hooks.py (see module docstring)
# # ---------------------------------------------------------------------------
 
# def set_task_duration_fields(doc, method):
#     """doc_events hook - call on 'validate' for 'Asset Maintenance Log'.
 
#     Computes custom_task_duration (in seconds) the first time
#     custom_employee_work_status is saved as "Completed", using the
#     Activity/Version log to find when the technician was assigned.
#     """
 
#     maintenance_type = doc.get("custom_asset_maintenance_type")
#     assign_field = ASSIGN_FIELD_BY_TYPE.get(maintenance_type)
 
#     # Unknown / blank maintenance type - nothing we can key off, skip.
#     if not assign_field:
#         return
 
#     # Only act once the task is actually completed.
#     if doc.get("custom_employee_work_status") != COMPLETED_STATUS:
#         return
 
#     # Already computed on an earlier save - don't keep recalculating (and
#     # drifting) every time the document is saved again afterwards.
#     if doc.get(DURATION_FIELD):
#         return
 
#     # Nothing to diff against on the very first insert of a brand-new doc.
#     if doc.is_new():
#         return
 
#     # --- Guard against the "value disappears after refresh" trap ---------
#     # If this field can't actually be persisted, fail loudly here instead
#     # of silently computing a value that will vanish on the next reload.
#     field_meta = doc.meta.get_field(DURATION_FIELD)
#     if not field_meta:
#         frappe.log_error(
#             title="Asset Maintenance Log: duration field missing",
#             message=(
#                 f"{doc.doctype} {doc.name}: field '{DURATION_FIELD}' does "
#                 f"not exist on this DocType (check for a typo, or that the "
#                 f"Custom Field was created on 'Asset Maintenance Log' and "
#                 f"not some other doctype). custom_task_duration was not set."
#             ),
#         )
#         return
 
#     if getattr(field_meta, "is_virtual", 0):
#         frappe.log_error(
#             title="Asset Maintenance Log: duration field is virtual",
#             message=(
#                 f"{doc.doctype} {doc.name}: field '{DURATION_FIELD}' is "
#                 f"marked 'Is Virtual', so it has no real DB column and any "
#                 f"value assigned to it will never be saved. Uncheck 'Is "
#                 f"Virtual' on the Custom Field / Customize Form entry for "
#                 f"this field, then re-save this document."
#             ),
#         )
#         return
#     # ----------------------------------------------------------------------
 
#     completion_time = now_datetime()
#     assignment_time = _get_first_change_timestamp(doc.doctype, doc.name, assign_field)
 
#     if not assignment_time and doc.get(assign_field):
#         # Edge case: the assign-to field is being set for the very first
#         # time in this SAME save that also completes the task (so there's
#         # no earlier Version entry, and the pre-write DB value is still
#         # empty). Treat "assigned" and "completed" as happening together.
#         assignment_time = completion_time
 
#     if not assignment_time:
#         frappe.log_error(
#             title="Asset Maintenance Log: could not determine assignment time",
#             message=(
#                 f"{doc.doctype} {doc.name}: no Activity/Version entry or "
#                 f"existing value found for '{assign_field}', so "
#                 f"{DURATION_FIELD} was not calculated."
#             ),
#         )
#         return
 
#     seconds = time_diff_in_seconds(completion_time, assignment_time)
 
#     # Guard against clock skew / bad data producing a negative duration.
#     if seconds < 0:
#         frappe.log_error(
#             title="Asset Maintenance Log: negative task duration",
#             message=(
#                 f"{doc.doctype} {doc.name}: completion time "
#                 f"({completion_time}) is before assignment time "
#                 f"({assignment_time})."
#             ),
#         )
#         seconds = 0
 
#     # IMPORTANT: if this hook is wired to "on_update" (fires AFTER the doc's
#     # own save/db-write already happened), plain attribute assignment here
#     # only changes the in-memory object - it is never written to the DB row,
#     # which is exactly why the value shows once and then disappears on
#     # refresh. db_set() issues its own immediate UPDATE, so it persists
#     # regardless of which event this runs on. If this is wired to
#     # "validate" instead (runs BEFORE the save), doc.set(...) alone would
#     # also work and avoid the extra query - but db_set() is safe either way.
#     doc.db_set(DURATION_FIELD, seconds, update_modified=False)
 
 
# # ---------------------------------------------------------------------------
# # Shared helper - reads the Activity/Version log
# # ---------------------------------------------------------------------------
 
# def _get_first_change_timestamp(doctype, docname, fieldname, expected_value=None):
#     """Scan this document's Version (Activity log) history for the earliest
#     save where `fieldname` changed to a truthy value (or to
#     `expected_value`, if given), and return that Version's creation
#     timestamp.
 
#     Falls back to the document's own `creation` timestamp if the field's
#     current value already satisfies the condition but no version entry
#     captured the change (e.g. it was set at the very first insert).
#     """
 
#     versions = frappe.get_all(
#         "Version",
#         filters={"ref_doctype": doctype, "docname": docname},
#         fields=["name", "data", "creation"],
#         order_by="creation asc",
#     )
 
#     for version in versions:
#         try:
#             data = json.loads(version.data or "{}")
#         except ValueError:
#             continue
 
#         for changed in data.get("changed", []) or []:
#             # Each entry looks like [fieldname, old_value, new_value].
#             if len(changed) < 3 or changed[0] != fieldname:
#                 continue
 
#             new_value = changed[2]
 
#             if expected_value is not None:
#                 if new_value == expected_value:
#                     return version.creation
#             elif new_value:
#                 return version.creation
 
#     # No matching version entry - check if the field already holds a
#     # qualifying value, in which case treat the document's own creation
#     # time as the assignment time.
#     current_value = frappe.db.get_value(doctype, docname, fieldname)
 
#     qualifies = (
#         current_value == expected_value
#         if expected_value is not None
#         else bool(current_value)
#     )
 
#     if qualifies:
#         return frappe.db.get_value(doctype, docname, "creation")
 
#     return None
 
 
# # ---------------------------------------------------------------------------
# # One-time backfill for logs that were Completed BEFORE this hook existed
# # ---------------------------------------------------------------------------
 
# def backfill_completed_logs(dry_run=False):
#     """Run once, from the bench console, to fill in custom_task_duration
#     for Asset Maintenance Log records that are already Completed but have
#     no duration recorded (because they were completed before this hook
#     was installed).
 
#     Unlike the live hook, this pulls BOTH the assignment time AND the
#     completion time from the Version log, since "now()" is meaningless
#     for a save that already happened in the past.
 
#     Usage:
#         bench --site <your-site> console
#         >>> from your_app.asset_maintenance_log import backfill_completed_logs
#         >>> backfill_completed_logs(dry_run=True)   # preview first
#         >>> backfill_completed_logs()                # then actually apply
#     """
 
#     meta = frappe.get_meta("Asset Maintenance Log")
#     field_meta = meta.get_field(DURATION_FIELD)
#     if not field_meta:
#         print(
#             f"ABORTING: field '{DURATION_FIELD}' does not exist on "
#             f"'Asset Maintenance Log'. Check for a typo or the wrong doctype."
#         )
#         return
#     if getattr(field_meta, "is_virtual", 0):
#         print(
#             f"ABORTING: field '{DURATION_FIELD}' is marked 'Is Virtual' - "
#             f"it has no DB column, so nothing written to it will persist. "
#             f"Uncheck 'Is Virtual' first."
#         )
#         return
 
#     logs = frappe.get_all(
#         "Asset Maintenance Log",
#         filters={
#             "custom_employee_work_status": COMPLETED_STATUS,
#             DURATION_FIELD: ["in", [None, 0, ""]],
#         },
#         fields=["name", "custom_asset_maintenance_type"],
#     )
 
#     updated, skipped = 0, []
 
#     for log in logs:
#         assign_field = ASSIGN_FIELD_BY_TYPE.get(log.custom_asset_maintenance_type)
#         if not assign_field:
#             skipped.append((log.name, "unknown/blank maintenance type"))
#             continue
 
#         assignment_time = _get_first_change_timestamp(
#             "Asset Maintenance Log", log.name, assign_field
#         )
#         completion_time = _get_first_change_timestamp(
#             "Asset Maintenance Log",
#             log.name,
#             "custom_employee_work_status",
#             expected_value=COMPLETED_STATUS,
#         )
 
#         if not assignment_time or not completion_time:
#             skipped.append((log.name, "missing assignment or completion timestamp"))
#             continue
 
#         seconds = time_diff_in_seconds(completion_time, assignment_time)
#         if seconds < 0:
#             skipped.append((log.name, "negative duration - skipped"))
#             continue
 
#         if dry_run:
#             print(f"{log.name}: would set {DURATION_FIELD} = {seconds} sec")
#         else:
#             frappe.db.set_value(
#                 "Asset Maintenance Log", log.name, DURATION_FIELD, seconds
#             )
#             updated += 1
 
#     if not dry_run:
#         frappe.db.commit()
 
#     print(f"Backfill done. Updated: {updated}. Skipped: {len(skipped)}.")
#     for name, reason in skipped:
#         print(f"  - {name}: {reason}")
"""
Asset Maintenance Log - Task Duration (working time only)
=========================================================

custom_task_duration (seconds) = total time spent in "In Progress"

    In Progress --(counted)--> On Hold --(NOT counted)--> In Progress --(counted)--> Completed

Example:
    10:00 In Progress   -> timer starts
    11:00 On Hold       -> +1h, timer paused
    13:00 In Progress   -> timer resumes (11:00-13:00 excluded)
    14:30 Completed     -> +1.5h
    custom_task_duration = 2.5h = 9000 sec

Any status other than "In Progress" (On Hold, Open, etc.) pauses the timer.

Timestamps come from the Version (Activity) log, so "Track Changes" MUST be
enabled on Asset Maintenance Log.

hooks.py
--------
    doc_events = {
        "Asset Maintenance Log": {
            "validate": "your_app.asset_maintenance_log.set_task_duration_fields",
        }
    }
"""

import json

import frappe
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds

DOCTYPE = "Asset Maintenance Log"
STATUS_FIELD = "custom_employee_work_status"
DURATION_FIELD = "custom_task_duration"

IN_PROGRESS_STATUS = "In Progress"
COMPLETED_STATUS = "Completed"


# ---------------------------------------------------------------------------
# Live hook
# ---------------------------------------------------------------------------

def set_task_duration_fields(doc, method=None):
	"""Hook on 'validate' of Asset Maintenance Log.

	Runs only on the save where the status changes to "Completed".
	"""

	if doc.get(STATUS_FIELD) != COMPLETED_STATUS:
		return

	# Already calculated earlier - don't recalculate
	if doc.get(DURATION_FIELD):
		return

	# Brand-new doc created directly as Completed - no In Progress history
	if doc.is_new():
		return

	# Only on the save where status is actually changing to Completed
	before = doc.get_doc_before_save()
	if before and before.get(STATUS_FIELD) == COMPLETED_STATUS:
		return

	if not _duration_field_ok(doc.meta, doc.name):
		return

	timeline = _get_status_timeline(doc.doctype, doc.name, before)
	# The current save (-> Completed) isn't in the Version log yet
	timeline.append((now_datetime(), COMPLETED_STATUS))

	seconds = _calculate_working_seconds(timeline)

	if seconds is None:
		frappe.log_error(
			title="Asset Maintenance Log: no 'In Progress' found",
			message=(
				f"{doc.name}: status reached '{COMPLETED_STATUS}' but no "
				f"'{IN_PROGRESS_STATUS}' entry was found in the Activity log. "
				f"{DURATION_FIELD} was not calculated."
			),
		)
		return

	if method == "validate":
		# validate runs BEFORE the DB write - normal set is enough
		doc.set(DURATION_FIELD, seconds)
	else:
		# on_update / other after-save events - must write directly
		doc.db_set(DURATION_FIELD, seconds, update_modified=False)


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

def _calculate_working_seconds(timeline):
	"""Sum only the In Progress periods, up to the first Completed.

	timeline: [(timestamp, new_status), ...] oldest first.
	Returns total seconds, or None if it never went In Progress.
	"""

	total = 0
	running_since = None
	started = False

	for ts, status in timeline:
		if status == IN_PROGRESS_STATUS:
			if running_since is None:
				running_since = ts  # start / resume timer
				started = True
			continue

		# Any other status -> pause (or stop) the timer
		if running_since is not None:
			diff = time_diff_in_seconds(ts, running_since)
			if diff > 0:
				total += diff
			running_since = None

		if status == COMPLETED_STATUS and started:
			break

	if not started:
		return None

	return int(total)


# ---------------------------------------------------------------------------
# Version log helpers
# ---------------------------------------------------------------------------

def _get_status_history(doctype, docname):
	"""[(timestamp, old_value, new_value), ...] for STATUS_FIELD, oldest first."""

	versions = frappe.get_all(
		"Version",
		filters={"ref_doctype": doctype, "docname": docname},
		fields=["data", "creation"],
		order_by="creation asc",
	)

	history = []
	for v in versions:
		try:
			data = json.loads(v.data or "{}")
		except ValueError:
			continue

		for changed in data.get("changed") or []:
			# [fieldname, old_value, new_value]
			if len(changed) >= 3 and changed[0] == STATUS_FIELD:
				history.append((get_datetime(v.creation), changed[1], changed[2]))

	return history


def _get_status_timeline(doctype, docname, doc_before_save=None):
	"""[(timestamp, status), ...] - every status the doc entered, oldest first.

	If the doc was created already "In Progress" (no change entry for that),
	the creation time is added as the first In Progress.
	"""

	history = _get_status_history(doctype, docname)
	timeline = [(ts, new) for ts, _old, new in history]

	created_in_progress = (
		(history and history[0][1] == IN_PROGRESS_STATUS)
		or (
			not history
			and doc_before_save
			and doc_before_save.get(STATUS_FIELD) == IN_PROGRESS_STATUS
		)
	)
	if created_in_progress:
		creation = get_datetime(frappe.db.get_value(doctype, docname, "creation"))
		timeline.insert(0, (creation, IN_PROGRESS_STATUS))

	return timeline


def _duration_field_ok(meta, docname=""):
	"""Make sure the duration field exists and is a real DB column."""

	field = meta.get_field(DURATION_FIELD)
	if not field:
		frappe.log_error(
			title="Asset Maintenance Log: duration field missing",
			message=f"{docname}: field '{DURATION_FIELD}' not found on {DOCTYPE}.",
		)
		return False

	if getattr(field, "is_virtual", 0):
		frappe.log_error(
			title="Asset Maintenance Log: duration field is virtual",
			message=(
				f"{docname}: '{DURATION_FIELD}' is marked 'Is Virtual' so it "
				f"cannot be saved. Uncheck 'Is Virtual' on the Custom Field."
			),
		)
		return False

	return True


# ---------------------------------------------------------------------------
# One-time backfill / recalculation
# ---------------------------------------------------------------------------

def backfill_completed_logs(dry_run=False, recalculate=False):
	"""Fill custom_task_duration for Completed logs from the Activity log.

	recalculate=True also re-computes logs that already have a duration
	(use once to convert old values that included On Hold time).

	bench --site <site> console
	>>> from your_app.asset_maintenance_log import backfill_completed_logs
	>>> backfill_completed_logs(dry_run=True)                    # preview empty ones
	>>> backfill_completed_logs(dry_run=True, recalculate=True)  # preview all
	>>> backfill_completed_logs(recalculate=True)                # apply to all
	"""

	if not _duration_field_ok(frappe.get_meta(DOCTYPE)):
		print(f"ABORTING: '{DURATION_FIELD}' missing or virtual - see Error Log.")
		return

	kwargs = {"filters": {STATUS_FIELD: COMPLETED_STATUS}, "pluck": "name"}
	if not recalculate:
		kwargs["or_filters"] = [[DURATION_FIELD, "is", "not set"], [DURATION_FIELD, "=", 0]]

	logs = frappe.get_all(DOCTYPE, **kwargs)

	updated, skipped = 0, []

	for name in logs:
		timeline = _get_status_timeline(DOCTYPE, name)

		if not any(s == COMPLETED_STATUS for _ts, s in timeline):
			skipped.append((name, "no 'Completed' in Activity log"))
			continue

		seconds = _calculate_working_seconds(timeline)
		if seconds is None:
			skipped.append((name, "no 'In Progress' in Activity log"))
			continue

		if dry_run:
			print(f"{name}: {seconds} sec ({round(seconds / 3600, 2)} hrs)")
		else:
			frappe.db.set_value(
				DOCTYPE, name, DURATION_FIELD, seconds, update_modified=False
			)
			updated += 1

	if not dry_run:
		frappe.db.commit()

	print(f"Backfill done. Updated: {updated}. Skipped: {len(skipped)}.")
	for name, reason in skipped:
		print(f"  - {name}: {reason}")