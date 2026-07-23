# import json
# import frappe
# from werkzeug.wrappers import Response


# @frappe.whitelist(allow_guest=False)
# def add_reschedule_history(asset_maintenance_log_id=None, remarks=None, employee_visit_date=None, is_rescheduled=None):
#     """
#     Appends a new row into the Reschedule History child table
#     (fieldname: custom_reschedule_history_table) on an Asset Maintenance Log.

#     NOTE ON NAMING:
#         The API parameter is called `employee_visit_date` for clarity to
#         callers, but the actual child table field in Frappe is still
#         `date_time` (unchanged). This function maps the incoming
#         `employee_visit_date` value onto the real `date_time` fieldname
#         when saving — no DocType rename was done.

#     Auth:
#         Requires a valid OAuth2 Bearer token (from generate_token_secure_for_users).
#         frappe.session.user is resolved automatically from the token.

#     Params (form-data / JSON body):
#         asset_maintenance_log_id (str)      - required - AML to update
#         remarks                  (str)      - required - free text remarks
#         employee_visit_date      (str)      - required - format "YYYY-MM-DD HH:MM:SS"
#         is_rescheduled            (0/1/bool) - required - rescheduled checkbox

#     NOTE: scheduled_date is intentionally NOT accepted here.
#     """

#     try:
#         # ── STEP 1: Auth ───────────────────────────────────────────────
#         current_user = frappe.session.user
#         if not current_user or current_user == "Guest":
#             return Response(
#                 json.dumps({"status": "error", "message": "Unauthorized. Please provide a valid Bearer token."}),
#                 status=401, mimetype="application/json",
#             )

#         # ── STEP 2: Validate input ─────────────────────────────────────
#         if not asset_maintenance_log_id:
#             return Response(
#                 json.dumps({"status": "error", "message": "asset_maintenance_log_id is required."}),
#                 status=400, mimetype="application/json",
#             )

#         if not remarks or not str(remarks).strip():
#             return Response(
#                 json.dumps({"status": "error", "message": "remarks is required."}),
#                 status=400, mimetype="application/json",
#             )

#         if not employee_visit_date or not str(employee_visit_date).strip():
#             return Response(
#                 json.dumps({"status": "error", "message": "employee_visit_date is required (format: YYYY-MM-DD HH:MM:SS)."}),
#                 status=400, mimetype="application/json",
#             )

#         # Validate datetime format
#         try:
#             frappe.utils.get_datetime(employee_visit_date)
#         except Exception:
#             return Response(
#                 json.dumps({"status": "error", "message": "employee_visit_date must be in format YYYY-MM-DD HH:MM:SS."}),
#                 status=400, mimetype="application/json",
#             )

#         if is_rescheduled in (None, ""):
#             return Response(
#                 json.dumps({"status": "error", "message": "is_rescheduled is required (0 or 1)."}),
#                 status=400, mimetype="application/json",
#             )

#         # Normalize checkbox to 0/1
#         if isinstance(is_rescheduled, str):
#             is_rescheduled_val = 1 if is_rescheduled.strip().lower() in ("1", "true", "yes") else 0
#         else:
#             is_rescheduled_val = 1 if int(is_rescheduled) == 1 else 0

#         # ── STEP 3: Fetch the target Asset Maintenance Log ──────────────
#         if not frappe.db.exists("Asset Maintenance Log", asset_maintenance_log_id):
#             return Response(
#                 json.dumps({"status": "error", "message": f"Asset Maintenance Log '{asset_maintenance_log_id}' not found."}),
#                 status=404, mimetype="application/json",
#             )

#         target_log = frappe.get_doc("Asset Maintenance Log", asset_maintenance_log_id)

#         # ── STEP 4: Append the new row into the child table ─────────────
#         # NOTE: real child table fieldname is "date_time", not "employee_visit_date"
#         new_row = target_log.append("custom_reschedule_history_table", {
#             "remarks": remarks,
#             "date_time": employee_visit_date,   # mapped: API param -> actual field
#             "is_rescheduled": is_rescheduled_val,
#         })

#         target_log.save(ignore_permissions=False)
#         frappe.db.commit()

#         # ── STEP 5: Return success with the new row ─────────────────────
#         return Response(
#             json.dumps(
#                 {
#                     "success": True,
#                     "message": "Reschedule history added successfully.",
#                     "asset_maintenance_log_id": asset_maintenance_log_id,
#                     "row": {
#                         "name": new_row.name,
#                         "remarks": new_row.remarks,
#                         "employeeVisitDate": str(new_row.date_time),   # read from real field
#                         "isRescheduled": bool(new_row.is_rescheduled),
#                     },
#                 },
#                 default=str,
#             ),
#             status=200, mimetype="application/json",
#         )

#     except frappe.PermissionError:
#         return Response(
#             json.dumps({"status": "error", "message": "You do not have permission to access this resource."}),
#             status=403, mimetype="application/json",
#         )
#     except Exception as e:
#         frappe.log_error(title="add_reschedule_history error", message=frappe.get_traceback())
#         return Response(
#             json.dumps({"status": "error", "message": str(e)}),
#             status=500, mimetype="application/json",
#         )
import json
import frappe
from werkzeug.wrappers import Response


@frappe.whitelist(allow_guest=False)
def add_reschedule_history(asset_maintenance_log_id=None, remarks=None, employee_visit_date=None, is_rescheduled=None, scheduled_date=None):
    """
    Appends a new row into the Reschedule History child table
    (fieldname: custom_reschedule_history_table) on an Asset Maintenance Log.

    NOTE ON NAMING:
        The API parameter is called `employee_visit_date` for clarity to
        callers, but the actual child table field in Frappe is still
        `date_time` (unchanged). This function maps the incoming
        `employee_visit_date` value onto the real `date_time` fieldname
        when saving — no DocType rename was done.

    Auth:
        Requires a valid OAuth2 Bearer token (from generate_token_secure_for_users).
        frappe.session.user is resolved automatically from the token.

    Params (form-data / JSON body):
        asset_maintenance_log_id (str)      - required - AML to update
        remarks                  (str)      - required - free text remarks
        employee_visit_date      (str)      - required - format "YYYY-MM-DD HH:MM:SS"
        is_rescheduled            (0/1/bool) - required - rescheduled checkbox
        scheduled_date            (str)      - optional - format "YYYY-MM-DD HH:MM:SS"
    """

    try:
        # ── STEP 1: Auth ───────────────────────────────────────────────
        current_user = frappe.session.user
        if not current_user or current_user == "Guest":
            return Response(
                json.dumps({"status": "error", "message": "Unauthorized. Please provide a valid Bearer token."}),
                status=401, mimetype="application/json",
            )

        # ── STEP 2: Validate input ─────────────────────────────────────
        if not asset_maintenance_log_id:
            return Response(
                json.dumps({"status": "error", "message": "asset_maintenance_log_id is required."}),
                status=400, mimetype="application/json",
            )

        if not remarks or not str(remarks).strip():
            return Response(
                json.dumps({"status": "error", "message": "remarks is required."}),
                status=400, mimetype="application/json",
            )

        if not employee_visit_date or not str(employee_visit_date).strip():
            return Response(
                json.dumps({"status": "error", "message": "employee_visit_date is required (format: YYYY-MM-DD HH:MM:SS)."}),
                status=400, mimetype="application/json",
            )

        # Validate datetime format
        try:
            frappe.utils.get_datetime(employee_visit_date)
        except Exception:
            return Response(
                json.dumps({"status": "error", "message": "employee_visit_date must be in format YYYY-MM-DD HH:MM:SS."}),
                status=400, mimetype="application/json",
            )

        if is_rescheduled in (None, ""):
            return Response(
                json.dumps({"status": "error", "message": "is_rescheduled is required (0 or 1)."}),
                status=400, mimetype="application/json",
            )

        # Normalize checkbox to 0/1
        if isinstance(is_rescheduled, str):
            is_rescheduled_val = 1 if is_rescheduled.strip().lower() in ("1", "true", "yes") else 0
        else:
            is_rescheduled_val = 1 if int(is_rescheduled) == 1 else 0

        # scheduled_date is optional — only validate format if it was actually provided
        if scheduled_date and str(scheduled_date).strip():
            try:
                frappe.utils.get_datetime(scheduled_date)
            except Exception:
                return Response(
                    json.dumps({"status": "error", "message": "scheduled_date must be in format YYYY-MM-DD HH:MM:SS."}),
                    status=400, mimetype="application/json",
                )
        else:
            scheduled_date = None

        # ── STEP 3: Fetch the target Asset Maintenance Log ──────────────
        if not frappe.db.exists("Asset Maintenance Log", asset_maintenance_log_id):
            return Response(
                json.dumps({"status": "error", "message": f"Asset Maintenance Log '{asset_maintenance_log_id}' not found."}),
                status=404, mimetype="application/json",
            )

        target_log = frappe.get_doc("Asset Maintenance Log", asset_maintenance_log_id)

        # ── STEP 4: Append the new row into the child table ─────────────
        # NOTE: real child table fieldname is "date_time", not "employee_visit_date"
        row_values = {
            "remarks": remarks,
            "date_time": employee_visit_date,   # mapped: API param -> actual field
            "is_rescheduled": is_rescheduled_val,
        }
        if scheduled_date:
            row_values["scheduled_date"] = scheduled_date

        new_row = target_log.append("custom_reschedule_history_table", row_values)

        target_log.save(ignore_permissions=False)
        frappe.db.commit()

        # ── STEP 5: Return success with the new row ─────────────────────
        return Response(
            json.dumps(
                {
                    "success": True,
                    "message": "Reschedule history added successfully.",
                    "asset_maintenance_log_id": asset_maintenance_log_id,
                    "row": {
                        "name": new_row.name,
                        "remarks": new_row.remarks,
                        "employeeVisitDate": str(new_row.date_time),   # read from real field
                        "isRescheduled": bool(new_row.is_rescheduled),
                        "scheduledDate": str(new_row.scheduled_date) if new_row.get("scheduled_date") else None,
                    },
                },
                default=str,
            ),
            status=200, mimetype="application/json",
        )

    except frappe.PermissionError:
        return Response(
            json.dumps({"status": "error", "message": "You do not have permission to access this resource."}),
            status=403, mimetype="application/json",
        )
    except Exception as e:
        frappe.log_error(title="add_reschedule_history error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500, mimetype="application/json",
        )