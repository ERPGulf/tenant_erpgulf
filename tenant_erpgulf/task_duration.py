
# import json
 
# import frappe
# from frappe.utils import now_datetime, time_diff_in_seconds
 
# COMPLETED_STATUS = "Completed"
 
# # Which field holds "who it was assigned to" for each maintenance type.
# ASSIGN_FIELD_BY_TYPE = {
#     "Planned": "assign_to_name",
#     "Reactive": "custom_assign_to",
# }
 
 
# # ---------------------------------------------------------------------------
# # Live hook - wire this to "validate" in hooks.py (see hooks_snippet.py)
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
#     if doc.get("custom_task_duration"):
#         return
 
#     # Nothing to diff against on the very first insert of a brand-new doc.
#     if doc.is_new():
#         return
 
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
#                 f"custom_task_duration was not calculated."
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
 
#     doc.custom_task_duration = seconds
 
 
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
 
#     logs = frappe.get_all(
#         "Asset Maintenance Log",
#         filters={
#             "custom_employee_work_status": COMPLETED_STATUS,
#             "custom_task_duration": ["in", [None, 0, ""]],
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
#             print(f"{log.name}: would set custom_task_duration = {seconds} sec")
#         else:
#             frappe.db.set_value(
#                 "Asset Maintenance Log", log.name, "custom_task_duration", seconds
#             )
#             updated += 1
 
#     if not dry_run:
#         frappe.db.commit()
 
#     print(f"Backfill done. Updated: {updated}. Skipped: {len(skipped)}.")
#     for name, reason in skipped:
#         print(f"  - {name}: {reason}")
import json
 
import frappe
from frappe.utils import now_datetime, time_diff_in_seconds
 
COMPLETED_STATUS = "Completed"
DURATION_FIELD = "custom_task_duration"
 
# Which field holds "who it was assigned to" for each maintenance type.
ASSIGN_FIELD_BY_TYPE = {
    "Planned": "assign_to_name",
    "Reactive": "custom_assign_to",
}
 
 
# ---------------------------------------------------------------------------
# Live hook - wire this to "validate" in hooks.py (see module docstring)
# ---------------------------------------------------------------------------
 
def set_task_duration_fields(doc, method):
    """doc_events hook - call on 'validate' for 'Asset Maintenance Log'.
 
    Computes custom_task_duration (in seconds) the first time
    custom_employee_work_status is saved as "Completed", using the
    Activity/Version log to find when the technician was assigned.
    """
 
    maintenance_type = doc.get("custom_asset_maintenance_type")
    assign_field = ASSIGN_FIELD_BY_TYPE.get(maintenance_type)
 
    # Unknown / blank maintenance type - nothing we can key off, skip.
    if not assign_field:
        return
 
    # Only act once the task is actually completed.
    if doc.get("custom_employee_work_status") != COMPLETED_STATUS:
        return
 
    # Already computed on an earlier save - don't keep recalculating (and
    # drifting) every time the document is saved again afterwards.
    if doc.get(DURATION_FIELD):
        return
 
    # Nothing to diff against on the very first insert of a brand-new doc.
    if doc.is_new():
        return
 
    # --- Guard against the "value disappears after refresh" trap ---------
    # If this field can't actually be persisted, fail loudly here instead
    # of silently computing a value that will vanish on the next reload.
    field_meta = doc.meta.get_field(DURATION_FIELD)
    if not field_meta:
        frappe.log_error(
            title="Asset Maintenance Log: duration field missing",
            message=(
                f"{doc.doctype} {doc.name}: field '{DURATION_FIELD}' does "
                f"not exist on this DocType (check for a typo, or that the "
                f"Custom Field was created on 'Asset Maintenance Log' and "
                f"not some other doctype). custom_task_duration was not set."
            ),
        )
        return
 
    if getattr(field_meta, "is_virtual", 0):
        frappe.log_error(
            title="Asset Maintenance Log: duration field is virtual",
            message=(
                f"{doc.doctype} {doc.name}: field '{DURATION_FIELD}' is "
                f"marked 'Is Virtual', so it has no real DB column and any "
                f"value assigned to it will never be saved. Uncheck 'Is "
                f"Virtual' on the Custom Field / Customize Form entry for "
                f"this field, then re-save this document."
            ),
        )
        return
    # ----------------------------------------------------------------------
 
    completion_time = now_datetime()
    assignment_time = _get_first_change_timestamp(doc.doctype, doc.name, assign_field)
 
    if not assignment_time and doc.get(assign_field):
        # Edge case: the assign-to field is being set for the very first
        # time in this SAME save that also completes the task (so there's
        # no earlier Version entry, and the pre-write DB value is still
        # empty). Treat "assigned" and "completed" as happening together.
        assignment_time = completion_time
 
    if not assignment_time:
        frappe.log_error(
            title="Asset Maintenance Log: could not determine assignment time",
            message=(
                f"{doc.doctype} {doc.name}: no Activity/Version entry or "
                f"existing value found for '{assign_field}', so "
                f"{DURATION_FIELD} was not calculated."
            ),
        )
        return
 
    seconds = time_diff_in_seconds(completion_time, assignment_time)
 
    # Guard against clock skew / bad data producing a negative duration.
    if seconds < 0:
        frappe.log_error(
            title="Asset Maintenance Log: negative task duration",
            message=(
                f"{doc.doctype} {doc.name}: completion time "
                f"({completion_time}) is before assignment time "
                f"({assignment_time})."
            ),
        )
        seconds = 0
 
    # IMPORTANT: if this hook is wired to "on_update" (fires AFTER the doc's
    # own save/db-write already happened), plain attribute assignment here
    # only changes the in-memory object - it is never written to the DB row,
    # which is exactly why the value shows once and then disappears on
    # refresh. db_set() issues its own immediate UPDATE, so it persists
    # regardless of which event this runs on. If this is wired to
    # "validate" instead (runs BEFORE the save), doc.set(...) alone would
    # also work and avoid the extra query - but db_set() is safe either way.
    doc.db_set(DURATION_FIELD, seconds, update_modified=False)
 
 
# ---------------------------------------------------------------------------
# Shared helper - reads the Activity/Version log
# ---------------------------------------------------------------------------
 
def _get_first_change_timestamp(doctype, docname, fieldname, expected_value=None):
    """Scan this document's Version (Activity log) history for the earliest
    save where `fieldname` changed to a truthy value (or to
    `expected_value`, if given), and return that Version's creation
    timestamp.
 
    Falls back to the document's own `creation` timestamp if the field's
    current value already satisfies the condition but no version entry
    captured the change (e.g. it was set at the very first insert).
    """
 
    versions = frappe.get_all(
        "Version",
        filters={"ref_doctype": doctype, "docname": docname},
        fields=["name", "data", "creation"],
        order_by="creation asc",
    )
 
    for version in versions:
        try:
            data = json.loads(version.data or "{}")
        except ValueError:
            continue
 
        for changed in data.get("changed", []) or []:
            # Each entry looks like [fieldname, old_value, new_value].
            if len(changed) < 3 or changed[0] != fieldname:
                continue
 
            new_value = changed[2]
 
            if expected_value is not None:
                if new_value == expected_value:
                    return version.creation
            elif new_value:
                return version.creation
 
    # No matching version entry - check if the field already holds a
    # qualifying value, in which case treat the document's own creation
    # time as the assignment time.
    current_value = frappe.db.get_value(doctype, docname, fieldname)
 
    qualifies = (
        current_value == expected_value
        if expected_value is not None
        else bool(current_value)
    )
 
    if qualifies:
        return frappe.db.get_value(doctype, docname, "creation")
 
    return None
 
 
# ---------------------------------------------------------------------------
# One-time backfill for logs that were Completed BEFORE this hook existed
# ---------------------------------------------------------------------------
 
def backfill_completed_logs(dry_run=False):
    """Run once, from the bench console, to fill in custom_task_duration
    for Asset Maintenance Log records that are already Completed but have
    no duration recorded (because they were completed before this hook
    was installed).
 
    Unlike the live hook, this pulls BOTH the assignment time AND the
    completion time from the Version log, since "now()" is meaningless
    for a save that already happened in the past.
 
    Usage:
        bench --site <your-site> console
        >>> from your_app.asset_maintenance_log import backfill_completed_logs
        >>> backfill_completed_logs(dry_run=True)   # preview first
        >>> backfill_completed_logs()                # then actually apply
    """
 
    meta = frappe.get_meta("Asset Maintenance Log")
    field_meta = meta.get_field(DURATION_FIELD)
    if not field_meta:
        print(
            f"ABORTING: field '{DURATION_FIELD}' does not exist on "
            f"'Asset Maintenance Log'. Check for a typo or the wrong doctype."
        )
        return
    if getattr(field_meta, "is_virtual", 0):
        print(
            f"ABORTING: field '{DURATION_FIELD}' is marked 'Is Virtual' - "
            f"it has no DB column, so nothing written to it will persist. "
            f"Uncheck 'Is Virtual' first."
        )
        return
 
    logs = frappe.get_all(
        "Asset Maintenance Log",
        filters={
            "custom_employee_work_status": COMPLETED_STATUS,
            DURATION_FIELD: ["in", [None, 0, ""]],
        },
        fields=["name", "custom_asset_maintenance_type"],
    )
 
    updated, skipped = 0, []
 
    for log in logs:
        assign_field = ASSIGN_FIELD_BY_TYPE.get(log.custom_asset_maintenance_type)
        if not assign_field:
            skipped.append((log.name, "unknown/blank maintenance type"))
            continue
 
        assignment_time = _get_first_change_timestamp(
            "Asset Maintenance Log", log.name, assign_field
        )
        completion_time = _get_first_change_timestamp(
            "Asset Maintenance Log",
            log.name,
            "custom_employee_work_status",
            expected_value=COMPLETED_STATUS,
        )
 
        if not assignment_time or not completion_time:
            skipped.append((log.name, "missing assignment or completion timestamp"))
            continue
 
        seconds = time_diff_in_seconds(completion_time, assignment_time)
        if seconds < 0:
            skipped.append((log.name, "negative duration - skipped"))
            continue
 
        if dry_run:
            print(f"{log.name}: would set {DURATION_FIELD} = {seconds} sec")
        else:
            frappe.db.set_value(
                "Asset Maintenance Log", log.name, DURATION_FIELD, seconds
            )
            updated += 1
 
    if not dry_run:
        frappe.db.commit()
 
    print(f"Backfill done. Updated: {updated}. Skipped: {len(skipped)}.")
    for name, reason in skipped:
        print(f"  - {name}: {reason}")
 