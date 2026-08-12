# import json
# import frappe
# from werkzeug.wrappers import Response


# @frappe.whitelist(allow_guest=False)
# def submit_maintenance_feedback(asset_maintenance_log_id=None, star_rating=None, feedback=None):
#     """
#     Saves star rating + feedback text into an Asset Maintenance Log
#     (custom_rating, custom_feedback fields on the "Feedback" tab).

#     Business rule:
#         Before saving feedback for `asset_maintenance_log_id`, ALL earlier
#         Asset Maintenance Logs belonging to the SAME customer must already
#         have feedback + rating filled in — EXCEPT logs that are Cancelled
#         (docstatus == 2), which are skipped entirely from this check.
#         If any earlier, non-cancelled log is still missing feedback, this
#         request is blocked. The response includes the oldest pending log
#         (fix this one next) AND the full list of all pending logs.

#     Customer lookup path:
#         Asset Maintenance Log  <-  Maintenance Request (maintenance_log == AML.name)
#         Maintenance Request.customer  is the actual customer field.

#     Params (form-data / JSON body):
#         asset_maintenance_log_id (str)  - required - name of the AML to update
#         star_rating              (int)  - required - 1 to 5
#         feedback                 (str)  - required - feedback text
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

#         if star_rating in (None, ""):
#             return Response(
#                 json.dumps({"status": "error", "message": "star_rating is required."}),
#                 status=400, mimetype="application/json",
#             )

#         try:
#             star_rating = int(star_rating)
#         except (TypeError, ValueError):
#             return Response(
#                 json.dumps({"status": "error", "message": "star_rating must be a whole number between 1 and 5."}),
#                 status=400, mimetype="application/json",
#             )

#         if star_rating < 1 or star_rating > 5:
#             return Response(
#                 json.dumps({"status": "error", "message": "star_rating must be between 1 and 5."}),
#                 status=400, mimetype="application/json",
#             )

#         if not feedback or not str(feedback).strip():
#             return Response(
#                 json.dumps({"status": "error", "message": "feedback is required."}),
#                 status=400, mimetype="application/json",
#             )

#         # ── STEP 3: Fetch the target Asset Maintenance Log ──────────────
#         if not frappe.db.exists("Asset Maintenance Log", asset_maintenance_log_id):
#             return Response(
#                 json.dumps({"status": "error", "message": f"Asset Maintenance Log '{asset_maintenance_log_id}' not found."}),
#                 status=404, mimetype="application/json",
#             )

#         target_log = frappe.get_doc("Asset Maintenance Log", asset_maintenance_log_id)

#         # ── STEP 4: Resolve the customer via Maintenance Request ────────
#         target_mr = frappe.get_all(
#             "Maintenance Request",
#             filters={"maintenance_log": asset_maintenance_log_id},
#             fields=["name", "customer", "creation"],
#         )

#         if not target_mr:
#             return Response(
#                 json.dumps({"status": "error", "message": f"No Maintenance Request linked to Asset Maintenance Log '{asset_maintenance_log_id}'."}),
#                 status=404, mimetype="application/json",
#             )

#         customer = target_mr[0].get("customer")
#         target_date = target_mr[0].get("creation")

#         if not customer:
#             return Response(
#                 json.dumps({"status": "error", "message": "Could not resolve Customer for this maintenance log."}),
#                 status=400, mimetype="application/json",
#             )

#         # ── STEP 5: Check earlier logs for the SAME customer missing feedback ─
#         # Cancelled Asset Maintenance Logs (docstatus == 2) are excluded —
#         # feedback is only required for logs that are Saved (0) or Submitted (1).
#         earlier_logs = frappe.db.sql(
#             """
#             SELECT aml.name AS maintenance_log_id, mr.creation
#             FROM `tabMaintenance Request` mr
#             INNER JOIN `tabAsset Maintenance Log` aml ON aml.name = mr.maintenance_log
#             WHERE mr.customer = %(customer)s
#               AND mr.creation < %(target_date)s
#               AND aml.name != %(current_log)s
#               AND aml.docstatus != 2
#               AND (
#                     aml.custom_feedback IS NULL OR aml.custom_feedback = ''
#                     OR aml.custom_rating IS NULL OR aml.custom_rating = 0
#               )
#             ORDER BY mr.creation ASC
#             """,
#             {
#                 "customer": customer,
#                 "target_date": target_date,
#                 "current_log": asset_maintenance_log_id,
#             },
#             as_dict=True,
#         )

#         if earlier_logs:
#             pending_ids = [row["maintenance_log_id"] for row in earlier_logs]
#             oldest_pending = pending_ids[0]
#             return Response(
#                 json.dumps(
#                     {
#                         "status": "error",
#                         "message": f"Please give the feedback of previous maintenance log '{oldest_pending}' before proceeding.",
#                         "pendingMaintenanceLogId": oldest_pending,
#                         "allPendingMaintenanceLogIds": pending_ids,
#                     }
#                 ),
#                 status=400, mimetype="application/json",
#             )

#         # ── STEP 6: Save rating + feedback on the target log ─────────────
#         target_log.custom_rating = star_rating / 5   # Rating fieldtype stores 0-1
#         target_log.custom_feedback = feedback
#         target_log.save(ignore_permissions=False)
#         frappe.db.commit()

#         return Response(
#             json.dumps(
#                 {
#                     "success": True,
#                     "message": "Feedback saved successfully.",
#                     "asset_maintenance_log_id": asset_maintenance_log_id,
#                     "starRating": star_rating,
#                     "feedback": feedback,
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
#         frappe.log_error(title="submit_maintenance_feedback error", message=frappe.get_traceback())
#         return Response(
#             json.dumps({"status": "error", "message": str(e)}),
#             status=500, mimetype="application/json",
#         )
import json
import frappe
from werkzeug.wrappers import Response


@frappe.whitelist(allow_guest=False)
def submit_maintenance_feedback(asset_maintenance_log_id=None, star_rating=None, feedback=None, completed=None):
    """
    Saves star rating + feedback text + completed checkbox into an Asset
    Maintenance Log (custom_rating, custom_feedback, custom_completed
    fields on the "Feedback" tab).

    Business rule:
        Before saving feedback for `asset_maintenance_log_id`, ALL earlier
        Asset Maintenance Logs belonging to the SAME customer must already
        have feedback + rating filled in — EXCEPT logs that are Cancelled
        (docstatus == 2), which are skipped entirely from this check.
        If any earlier, non-cancelled log is still missing feedback, this
        request is blocked. The response includes the oldest pending log
        (fix this one next) AND the full list of all pending logs.

    Customer lookup path:
        Asset Maintenance Log  <-  Maintenance Request (maintenance_log == AML.name)
        Maintenance Request.customer  is the actual customer field.

    Params (form-data / JSON body):
        asset_maintenance_log_id (str)  - required - name of the AML to update
        star_rating              (int)  - required - 1 to 5
        feedback                 (str)  - required - feedback text
        completed                (bool) - optional - 1/0, true/false, yes/no
                                            (defaults to 0 / not completed if omitted)
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

        if star_rating in (None, ""):
            return Response(
                json.dumps({"status": "error", "message": "star_rating is required."}),
                status=400, mimetype="application/json",
            )

        try:
            star_rating = int(star_rating)
        except (TypeError, ValueError):
            return Response(
                json.dumps({"status": "error", "message": "star_rating must be a whole number between 1 and 5."}),
                status=400, mimetype="application/json",
            )

        if star_rating < 1 or star_rating > 5:
            return Response(
                json.dumps({"status": "error", "message": "star_rating must be between 1 and 5."}),
                status=400, mimetype="application/json",
            )

        if not feedback or not str(feedback).strip():
            return Response(
                json.dumps({"status": "error", "message": "feedback is required."}),
                status=400, mimetype="application/json",
            )

        # ── STEP 2b: Validate "completed" checkbox parameter (NEW) ──────
        if completed in (None, ""):
            completed = 0
        else:
            completed_str = str(completed).strip().lower()
            if completed_str in ("1", "true", "yes"):
                completed = 1
            elif completed_str in ("0", "false", "no"):
                completed = 0
            else:
                return Response(
                    json.dumps({"status": "error", "message": "completed must be a boolean value (0/1, true/false, yes/no)."}),
                    status=400, mimetype="application/json",
                )

        # ── STEP 3: Fetch the target Asset Maintenance Log ──────────────
        if not frappe.db.exists("Asset Maintenance Log", asset_maintenance_log_id):
            return Response(
                json.dumps({"status": "error", "message": f"Asset Maintenance Log '{asset_maintenance_log_id}' not found."}),
                status=404, mimetype="application/json",
            )

        target_log = frappe.get_doc("Asset Maintenance Log", asset_maintenance_log_id)

        # ── STEP 4: Resolve the customer via Maintenance Request ────────
        target_mr = frappe.get_all(
            "Maintenance Request",
            filters={"maintenance_log": asset_maintenance_log_id},
            fields=["name", "customer", "creation"],
        )

        if not target_mr:
            return Response(
                json.dumps({"status": "error", "message": f"No Maintenance Request linked to Asset Maintenance Log '{asset_maintenance_log_id}'."}),
                status=404, mimetype="application/json",
            )

        customer = target_mr[0].get("customer")
        target_date = target_mr[0].get("creation")

        if not customer:
            return Response(
                json.dumps({"status": "error", "message": "Could not resolve Customer for this maintenance log."}),
                status=400, mimetype="application/json",
            )

        # ── STEP 5: Check earlier logs for the SAME customer missing feedback ─
        # Cancelled Asset Maintenance Logs (docstatus == 2) are excluded —
        # feedback is only required for logs that are Saved (0) or Submitted (1).
        earlier_logs = frappe.db.sql(
            """
            SELECT aml.name AS maintenance_log_id, mr.creation
            FROM `tabMaintenance Request` mr
            INNER JOIN `tabAsset Maintenance Log` aml ON aml.name = mr.maintenance_log
            WHERE mr.customer = %(customer)s
              AND mr.creation < %(target_date)s
              AND aml.name != %(current_log)s
              AND aml.docstatus != 2
              AND (
                    aml.custom_feedback IS NULL OR aml.custom_feedback = ''
                    OR aml.custom_rating IS NULL OR aml.custom_rating = 0
              )
            ORDER BY mr.creation ASC
            """,
            {
                "customer": customer,
                "target_date": target_date,
                "current_log": asset_maintenance_log_id,
            },
            as_dict=True,
        )

        if earlier_logs:
            pending_ids = [row["maintenance_log_id"] for row in earlier_logs]
            oldest_pending = pending_ids[0]
            return Response(
                json.dumps(
                    {
                        "status": "error",
                        "message": f"Please give the feedback of previous maintenance log '{oldest_pending}' before proceeding.",
                        "pendingMaintenanceLogId": oldest_pending,
                        "allPendingMaintenanceLogIds": pending_ids,
                    }
                ),
                status=400, mimetype="application/json",
            )

        # ── STEP 6: Save rating + feedback + completed on the target log (NEW field added) ─
        target_log.custom_rating = star_rating / 5   # Rating fieldtype stores 0-1
        target_log.custom_feedback = feedback
        target_log.custom_completed = completed       # NEW: Check field (0/1)
        target_log.save(ignore_permissions=False)
        frappe.db.commit()

        return Response(
            json.dumps(
                {
                    "success": True,
                    "message": "Feedback saved successfully.",
                    "asset_maintenance_log_id": asset_maintenance_log_id,
                    "starRating": star_rating,
                    "feedback": feedback,
                    "completed": completed,
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
        frappe.log_error(title="submit_maintenance_feedback error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500, mimetype="application/json",
        )