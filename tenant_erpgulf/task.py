# import io
# import os
# import re
# import base64
# from base64 import b64encode
# import json
# import random

# import requests
# import frappe
# from frappe import _
# from frappe.utils import now_datetime
# from pyqrcode import create as qr_create
# from werkzeug.wrappers import Response


# # ════════════════════════════════════════════════════════════════════════════════
# # API — GET Employee Assigned Tasks
# # ════════════════════════════════════════════════════════════════════════════════

# @frappe.whitelist(allow_guest=False)
# def get_employee_tasks():
#     try:
#         # ── STEP 1: Identify user from Bearer token ────────────────────────────
#         current_user = frappe.session.user

#         if not current_user or current_user == "Guest":
#             return Response(
#                 json.dumps({
#                     "status": "error",
#                     "message": "Unauthorized. Please provide a valid Bearer token.",
#                 }),
#                 status=401,
#                 mimetype="application/json",
#             )

#         # ── STEP 2: Find Employee linked to this user ──────────────────────────
#         employee = frappe.db.get_value(
#             "Employee",
#             {"user_id": current_user},
#             ["name", "user_id"],
#             as_dict=True,
#         )

#         if not employee:
#             return Response(
#                 json.dumps({
#                     "status": "error",
#                     "message": f"No employee record found for user '{current_user}'.",
#                 }),
#                 status=404,
#                 mimetype="application/json",
#             )

#         # ── STEP 3: Fetch ToDo tasks assigned to this employee's email ─────────
#         todos = frappe.get_all(
#             "ToDo",
#             filters={
#                 "allocated_to":   current_user,
#                 "reference_type": "Asset Maintenance Log",
#                 "status":         ["not in", ["Cancelled"]],
#             },
#             fields=["name", "status", "priority", "date", "reference_name"],
#             order_by="date asc",
#         )

#         # ── STEP 4: Map to required response shape ─────────────────────────────
#         STATUS_MAP = {
#             "Open":        "open",
#             "In Progress": "in_progress",
#             "Blocked":     "blocked",
#             "Closed":      "completed",
#             "Cancelled":   "cancelled",
#         }

#         PRIORITY_MAP = {
#             "Low":    "low",
#             "Medium": "medium",
#             "High":   "high",
#             "Urgent": "urgent",
#         }

#         tasks = []
#         for todo in todos:
#             task_name = None

#             # ── Go to Asset Maintenance Log and get task_name field ────────────
#             aml_name = todo.get("reference_name")
#             if aml_name and frappe.db.exists("Asset Maintenance Log", aml_name):
#                 aml = frappe.db.get_value(
#                     "Asset Maintenance Log",
#                     aml_name,
#                     ["task_name", "asset_name", "name"],
#                     as_dict=True,
#                 )
#                 frappe.log_error(
#                     title="[get_employee_tasks] AML fields",
#                     message=f"aml_name={aml_name} | aml={aml}"
#                 )
#                 task_name = aml.get("task_name") if aml else None

#             # ── Fallback: use asset_name if task_name is blank ─────────────────
#             if not task_name:
#                 task_name = aml.get("asset_name") if aml else aml_name

#             tasks.append({
#                 "id":       todo["name"],
#                 "name":     task_name,
#                 "status":   STATUS_MAP.get(todo.get("status"), "open"),
#                 "priority": PRIORITY_MAP.get(todo.get("priority"), "medium"),
#                 "dueDate":  str(todo["date"]) if todo.get("date") else None,
#             })

#         return Response(
#             json.dumps({"tasks": tasks}),
#             status=200,
#             mimetype="application/json",
#         )

#     except frappe.PermissionError:
#         return Response(
#             json.dumps({
#                 "status": "error",
#                 "message": "You do not have permission to access this resource.",
#             }),
#             status=403,
#             mimetype="application/json",
#         )

#     except Exception as e:
#         frappe.log_error(
#             title="get_employee_tasks error",
#             message=frappe.get_traceback(),
#         )
#         return Response(
#             json.dumps({"status": "error", "message": str(e)}),
#             status=500,
#             mimetype="application/json",
#         )




# @frappe.whitelist(allow_guest=False)
# def get_employee_task_detail(task_id):
#     try:
#         # ── STEP 1: Auth ───────────────────────────────────────────────────────
#         current_user = frappe.session.user
#         if not current_user or current_user == "Guest":
#             return Response(
#                 json.dumps({"status": "error", "message": "Unauthorized. Please provide a valid Bearer token."}),
#                 status=401, mimetype="application/json",
#             )

#         # ── STEP 2: Fetch the ToDo ─────────────────────────────────────────────
#         if not frappe.db.exists("ToDo", task_id):
#             return Response(
#                 json.dumps({"status": "error", "message": f"Task '{task_id}' not found"}),
#                 status=404, mimetype="application/json",
#             )

#         todo = frappe.db.get_value(
#             "ToDo",
#             task_id,
#             ["name", "status", "priority", "date", "reference_name", "reference_type", "allocated_to"],
#             as_dict=True,
#         )

#         # ── STEP 3: Verify it belongs to this employee ─────────────────────────
#         if todo.get("allocated_to") != current_user:
#             return Response(
#                 json.dumps({"status": "error", "message": "You do not have access to this task."}),
#                 status=403, mimetype="application/json",
#             )

#         # ── STEP 4: Fetch Asset Maintenance Log ────────────────────────────────
#         aml_name = todo.get("reference_name")
#         if not aml_name or not frappe.db.exists("Asset Maintenance Log", aml_name):
#             return Response(
#                 json.dumps({"status": "error", "message": f"Asset Maintenance Log '{aml_name}' not found"}),
#                 status=404, mimetype="application/json",
#             )

#         aml = frappe.db.get_value(
#             "Asset Maintenance Log",
#             aml_name,
#             [
#                 "name",
#                 "task_name",
#                 "custom_asset_maintenance_type",
#                 "custom_asset",
#                 "asset_name",
#                 "custom_maintenance_types",
#                 "maintenance_status",
#                 "custom_assign_to",
#                 "custom_maintenance_team",
#                 "asset_maintenance",
#                 "custom_employee_work_status",
#             ],
#             as_dict=True,
#         )

#         # ── STEP 5: Resolve Asset → location + room ────────────────────────────
#         is_reactive   = aml.get("custom_asset_maintenance_type") == "Reactive"
#         asset_id      = aml.get("custom_asset") if is_reactive else aml.get("asset_name")

#         location_name = None
#         room          = None

#         if asset_id and frappe.db.exists("Asset", asset_id):
#             asset_doc = frappe.db.get_value(
#                 "Asset",
#                 asset_id,
#                 ["location", "custom_room_name"],
#                 as_dict=True,
#             )
#             location_name = asset_doc.get("location")
#             room          = asset_doc.get("custom_room_name") or None

#         # ── STEP 6: Resolve Location → Floor → Building (tower) ───────────────
#         tower       = None
#         floor       = None
#         customer_id = None

#         if location_name and frappe.db.exists("Location", location_name):
#             location = frappe.db.get_value(
#                 "Location",
#                 location_name,
#                 ["custom_floor", "custom_customer", "custom_flat_number"],
#                 as_dict=True,
#             )

#             customer_id = location.get("custom_customer")

#             # room fallback: use custom_flat_number from Location if Asset has none
#             if not room and location.get("custom_flat_number"):
#                 room = location.get("custom_flat_number")

#             # floor → building → tower
#             if location.get("custom_floor"):
#                 floor_doc = frappe.db.get_value(
#                     "Floor",
#                     location["custom_floor"],
#                     ["name", "building"],
#                     as_dict=True,
#                 )
#                 if floor_doc:
#                     floor = floor_doc.get("name")
#                     if floor_doc.get("building"):
#                         tower = frappe.db.get_value(
#                             "Building",
#                             floor_doc["building"],
#                             "building_name",
#                         )

#         # ── STEP 7: Resolve Customer → reportedBy ─────────────────────────────
#         reported_by = {"id": None, "name": None}

#         if customer_id and frappe.db.exists("Customer", customer_id):
#             customer_name = frappe.db.get_value("Customer", customer_id, "customer_name")
#             reported_by = {
#                 "id":   customer_id,
#                 "name": customer_name or customer_id,
#             }

#         # ── STEP 8: Find Maintenance Request where maintenance_log = aml_name ──
#         reported_on = None
#         description = None
#         attachments = []

#         mr_name = frappe.db.get_value(
#             "Maintenance Request",
#             {"maintenance_log": aml_name},
#             "name",
#         )

#         frappe.log_error(
#             title="[get_employee_task_detail] MR lookup",
#             message=f"aml_name={aml_name} | mr_name={mr_name}"
#         )

#         if mr_name:
#             mr = frappe.db.get_value(
#                 "Maintenance Request",
#                 mr_name,
#                 ["date_of_submit", "description"],
#                 as_dict=True,
#             )
#             if mr:
#                 reported_on = str(mr.get("date_of_submit")) if mr.get("date_of_submit") else None
#                 description = mr.get("description") or None

#             # ── STEP 8a: Fetch attachments from the Maintenance Request ────────
#             site_url = frappe.utils.get_url()
#             raw_files = frappe.db.get_all(
#                 "File",
#                 filters={
#                     "attached_to_doctype": "Maintenance Request",
#                     "attached_to_name": mr_name,
#                 },
#                 fields=["name", "file_name", "file_url", "file_size", "is_private", "creation"],
#             )
#             for f in raw_files:
#                 file_url = f.get("file_url") or ""
#                 attachments.append({
#                     "id":         f.get("name"),
#                     "fileName":   f.get("file_name"),
#                     "fileUrl":    file_url,
#                     "fullUrl":    site_url.rstrip("/") + "/" + file_url.lstrip("/"),
#                     "fileSize":   f.get("file_size") or 0,
#                     "isPrivate":  bool(f.get("is_private")),
#                     "uploadedAt": str(f.get("creation")) if f.get("creation") else None,
#                 })

#         # ── STEP 9: Resolve assignedTo ─────────────────────────────────────────
#         assigned_to = {"id": None, "name": None, "team": None}
#         assign_user = aml.get("custom_assign_to")

#         # ── STEP 9a: Resolve maintenance team based on maintenance type ────────
#         # Reactive  → custom_maintenance_team field directly on the AML
#         # Planned   → AML.asset_maintenance (link) → Asset Maintenance doc → maintenance_team field
#         maintenance_team = None

#         if is_reactive:
#             maintenance_team = aml.get("custom_maintenance_team") or None
#         else:
#             asset_maintenance_name = aml.get("asset_maintenance")
#             if asset_maintenance_name and frappe.db.exists("Asset Maintenance", asset_maintenance_name):
#                 maintenance_team = frappe.db.get_value(
#                     "Asset Maintenance",
#                     asset_maintenance_name,
#                     "maintenance_team",
#                 ) or None

#         if assign_user and frappe.db.exists("User", assign_user):
#             user_data = frappe.db.get_value(
#                 "User",
#                 assign_user,
#                 ["name", "full_name"],
#                 as_dict=True,
#             )
#             emp = frappe.db.get_value(
#                 "Employee",
#                 {"user_id": assign_user},
#                 ["employee_name", "department"],
#                 as_dict=True,
#             )
#             assigned_to = {
#                 "id":   assign_user,
#                 "name": user_data.get("full_name") or assign_user,
#                 "team": maintenance_team,
#             }

#         # ── STEP 10: Status + priority maps ───────────────────────────────────
#         STATUS_MAP = {
#             "In Progress": "in_progress",
#             "On Hold":     "on_hold",
#             "Completed":   "completed",
#         }

#         PRIORITY_MAP = {
#             "Low":    "low",
#             "Medium": "medium",
#             "High":   "high",
#             "Urgent": "urgent",
#         }

#         # ── STEP 11: Build response ────────────────────────────────────────────
#         result = {
#             "id":       todo["name"],
#             "name":     aml.get("task_name") or aml_name,
#             "status":   STATUS_MAP.get(aml.get("custom_employee_work_status"), "in_progress"),
#             "priority": PRIORITY_MAP.get(todo.get("priority"), "medium"),
#             "category": aml.get("custom_maintenance_types") or None,
#             "type":     aml.get("custom_asset_maintenance_type"),
#             "location": {
#                 "tower": tower,
#                 "floor": floor,
#                 "room":  room,
#             },
#             "reportedBy":      reported_by,
#             "reportedOn":      reported_on,
#             "progress":        0,
#             "assignedTo":      assigned_to,
#             "dueDate":         str(todo["date"]) if todo.get("date") else None,
#             "description":     description,
#             "attachmentCount": len(attachments),
#             "attachments":     attachments,
#         }

#         return Response(
#             json.dumps(result, default=str),
#             status=200,
#             mimetype="application/json",
#         )

#     except frappe.PermissionError:
#         return Response(
#             json.dumps({"status": "error", "message": "You do not have permission to access this resource."}),
#             status=403, mimetype="application/json",
#         )

#     except Exception as e:
#         frappe.log_error(title="get_employee_task_detail error", message=frappe.get_traceback())
#         return Response(
#             json.dumps({"status": "error", "message": str(e)}),
#             status=500, mimetype="application/json",
#         )
import io
import os
import re
import base64
from base64 import b64encode
import json
import random

import requests
import frappe
from frappe import _
from frappe.utils import now_datetime
from pyqrcode import create as qr_create
from werkzeug.wrappers import Response


# ════════════════════════════════════════════════════════════════════════════════
# API — GET Employee Assigned Tasks
# ════════════════════════════════════════════════════════════════════════════════

@frappe.whitelist(allow_guest=False)
def get_employee_tasks():
    try:
        # ── STEP 1: Identify user from Bearer token ────────────────────────────
        current_user = frappe.session.user

        if not current_user or current_user == "Guest":
            return Response(
                json.dumps({
                    "status": "error",
                    "message": "Unauthorized. Please provide a valid Bearer token.",
                }),
                status=401,
                mimetype="application/json",
            )

        # ── STEP 2: Find Employee linked to this user ──────────────────────────
        employee = frappe.db.get_value(
            "Employee",
            {"user_id": current_user},
            ["name", "user_id"],
            as_dict=True,
        )

        if not employee:
            return Response(
                json.dumps({
                    "status": "error",
                    "message": f"No employee record found for user '{current_user}'.",
                }),
                status=404,
                mimetype="application/json",
            )

        # ── STEP 3: Fetch ToDo tasks assigned to this employee's email ─────────
        todos = frappe.get_all(
            "ToDo",
            filters={
                "allocated_to":   current_user,
                "reference_type": "Asset Maintenance Log",
                "status":         ["not in", ["Cancelled"]],
            },
            fields=["name", "status", "priority", "date", "reference_name"],
            order_by="date asc",
        )

        # ── STEP 4: Map to required response shape ─────────────────────────────
        STATUS_MAP = {
            "In Progress": "in_progress",
            "On Hold":     "on_hold",
            "Completed":   "completed",
        }

        PRIORITY_MAP = {
            "Low":    "low",
            "Medium": "medium",
            "High":   "high",
            "Urgent": "urgent",
        }

        tasks = []
        for todo in todos:
            task_name = None
            work_status = None

            # ── Go to Asset Maintenance Log and get task_name + work status ────
            aml_name = todo.get("reference_name")
            if aml_name and frappe.db.exists("Asset Maintenance Log", aml_name):
                aml = frappe.db.get_value(
                    "Asset Maintenance Log",
                    aml_name,
                    ["task_name", "asset_name", "name", "custom_employee_work_status"],
                    as_dict=True,
                )
                frappe.log_error(
                    title="[get_employee_tasks] AML fields",
                    message=f"aml_name={aml_name} | aml={aml}"
                )
                task_name   = aml.get("task_name") if aml else None
                work_status = aml.get("custom_employee_work_status") if aml else None

            # ── Fallback: use asset_name if task_name is blank ─────────────────
            if not task_name:
                task_name = aml.get("asset_name") if aml else aml_name

            tasks.append({
                "id":       todo["name"],
                "name":     task_name,
                "status":   STATUS_MAP.get(work_status, "in_progress"),
                "priority": PRIORITY_MAP.get(todo.get("priority"), "medium"),
                "dueDate":  str(todo["date"]) if todo.get("date") else None,
            })

        return Response(
            json.dumps({"tasks": tasks}),
            status=200,
            mimetype="application/json",
        )

    except frappe.PermissionError:
        return Response(
            json.dumps({
                "status": "error",
                "message": "You do not have permission to access this resource.",
            }),
            status=403,
            mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(
            title="get_employee_tasks error",
            message=frappe.get_traceback(),
        )
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500,
            mimetype="application/json",
        )




@frappe.whitelist(allow_guest=False)
def get_employee_task_detail(task_id):
    try:
        # ── STEP 1: Auth ───────────────────────────────────────────────────────
        current_user = frappe.session.user
        if not current_user or current_user == "Guest":
            return Response(
                json.dumps({"status": "error", "message": "Unauthorized. Please provide a valid Bearer token."}),
                status=401, mimetype="application/json",
            )

        # ── STEP 2: Fetch the ToDo ─────────────────────────────────────────────
        if not frappe.db.exists("ToDo", task_id):
            return Response(
                json.dumps({"status": "error", "message": f"Task '{task_id}' not found"}),
                status=404, mimetype="application/json",
            )

        todo = frappe.db.get_value(
            "ToDo",
            task_id,
            ["name", "status", "priority", "date", "reference_name", "reference_type", "allocated_to"],
            as_dict=True,
        )

        # ── STEP 3: Verify it belongs to this employee ─────────────────────────
        if todo.get("allocated_to") != current_user:
            return Response(
                json.dumps({"status": "error", "message": "You do not have access to this task."}),
                status=403, mimetype="application/json",
            )

        # ── STEP 4: Fetch Asset Maintenance Log ────────────────────────────────
        aml_name = todo.get("reference_name")
        if not aml_name or not frappe.db.exists("Asset Maintenance Log", aml_name):
            return Response(
                json.dumps({"status": "error", "message": f"Asset Maintenance Log '{aml_name}' not found"}),
                status=404, mimetype="application/json",
            )

        aml = frappe.db.get_value(
            "Asset Maintenance Log",
            aml_name,
            [
                "name",
                "task_name",
                "custom_asset_maintenance_type",
                "custom_asset",
                "asset_name",
                "custom_maintenance_types",
                "maintenance_status",
                "custom_assign_to",
                "custom_maintenance_team",
                "asset_maintenance",
                "custom_employee_work_status",
            ],
            as_dict=True,
        )

        # ── STEP 5: Resolve Asset → location + room ────────────────────────────
        is_reactive   = aml.get("custom_asset_maintenance_type") == "Reactive"
        asset_id      = aml.get("custom_asset") if is_reactive else aml.get("asset_name")

        location_name = None
        room          = None

        if asset_id and frappe.db.exists("Asset", asset_id):
            asset_doc = frappe.db.get_value(
                "Asset",
                asset_id,
                ["location", "custom_room_name"],
                as_dict=True,
            )
            location_name = asset_doc.get("location")
            room          = asset_doc.get("custom_room_name") or None

        # ── STEP 6: Resolve Location → Floor → Building (tower) ───────────────
        tower       = None
        floor       = None
        customer_id = None

        if location_name and frappe.db.exists("Location", location_name):
            location = frappe.db.get_value(
                "Location",
                location_name,
                ["custom_floor", "custom_customer", "custom_flat_number"],
                as_dict=True,
            )

            customer_id = location.get("custom_customer")

            # room fallback: use custom_flat_number from Location if Asset has none
            if not room and location.get("custom_flat_number"):
                room = location.get("custom_flat_number")

            # floor → building → tower
            if location.get("custom_floor"):
                floor_doc = frappe.db.get_value(
                    "Floor",
                    location["custom_floor"],
                    ["name", "building"],
                    as_dict=True,
                )
                if floor_doc:
                    floor = floor_doc.get("name")
                    if floor_doc.get("building"):
                        tower = frappe.db.get_value(
                            "Building",
                            floor_doc["building"],
                            "building_name",
                        )

        # ── STEP 7: Resolve Customer → reportedBy ─────────────────────────────
        reported_by = {"id": None, "name": None}

        if customer_id and frappe.db.exists("Customer", customer_id):
            customer_name = frappe.db.get_value("Customer", customer_id, "customer_name")
            reported_by = {
                "id":   customer_id,
                "name": customer_name or customer_id,
            }

        # ── STEP 8: Find Maintenance Request where maintenance_log = aml_name ──
        reported_on = None
        description = None
        attachments = []

        mr_name = frappe.db.get_value(
            "Maintenance Request",
            {"maintenance_log": aml_name},
            "name",
        )

        frappe.log_error(
            title="[get_employee_task_detail] MR lookup",
            message=f"aml_name={aml_name} | mr_name={mr_name}"
        )

        if mr_name:
            mr = frappe.db.get_value(
                "Maintenance Request",
                mr_name,
                ["date_of_submit", "description"],
                as_dict=True,
            )
            if mr:
                reported_on = str(mr.get("date_of_submit")) if mr.get("date_of_submit") else None
                description = mr.get("description") or None

            # ── STEP 8a: Fetch attachments from the Maintenance Request ────────
            site_url = frappe.utils.get_url()
            raw_files = frappe.db.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Maintenance Request",
                    "attached_to_name": mr_name,
                },
                fields=["name", "file_name", "file_url", "file_size", "is_private", "creation"],
            )
            for f in raw_files:
                file_url = f.get("file_url") or ""
                attachments.append({
                    "id":         f.get("name"),
                    "fileName":   f.get("file_name"),
                    "fileUrl":    file_url,
                    "fullUrl":    site_url.rstrip("/") + "/" + file_url.lstrip("/"),
                    "fileSize":   f.get("file_size") or 0,
                    "isPrivate":  bool(f.get("is_private")),
                    "uploadedAt": str(f.get("creation")) if f.get("creation") else None,
                })

        # ── STEP 9: Resolve assignedTo ─────────────────────────────────────────
        assigned_to = {"id": None, "name": None, "team": None}
        assign_user = aml.get("custom_assign_to")

        # ── STEP 9a: Resolve maintenance team based on maintenance type ────────
        # Reactive  → custom_maintenance_team field directly on the AML
        # Planned   → AML.asset_maintenance (link) → Asset Maintenance doc → maintenance_team field
        maintenance_team = None

        if is_reactive:
            maintenance_team = aml.get("custom_maintenance_team") or None
        else:
            asset_maintenance_name = aml.get("asset_maintenance")
            if asset_maintenance_name and frappe.db.exists("Asset Maintenance", asset_maintenance_name):
                maintenance_team = frappe.db.get_value(
                    "Asset Maintenance",
                    asset_maintenance_name,
                    "maintenance_team",
                ) or None

        if assign_user and frappe.db.exists("User", assign_user):
            user_data = frappe.db.get_value(
                "User",
                assign_user,
                ["name", "full_name"],
                as_dict=True,
            )
            emp = frappe.db.get_value(
                "Employee",
                {"user_id": assign_user},
                ["employee_name", "department"],
                as_dict=True,
            )
            assigned_to = {
                "id":   assign_user,
                "name": user_data.get("full_name") or assign_user,
                "team": maintenance_team,
            }

        # ── STEP 10: Status + priority maps ───────────────────────────────────
        STATUS_MAP = {
            "In Progress": "in_progress",
            "On Hold":     "on_hold",
            "Completed":   "completed",
        }

        PRIORITY_MAP = {
            "Low":    "low",
            "Medium": "medium",
            "High":   "high",
            "Urgent": "urgent",
        }

        # ── STEP 11: Build response ────────────────────────────────────────────
        result = {
            "id":       todo["name"],
            "name":     aml.get("task_name") or aml_name,
            "status":   STATUS_MAP.get(aml.get("custom_employee_work_status"), "in_progress"),
            "priority": PRIORITY_MAP.get(todo.get("priority"), "medium"),
            "category": aml.get("custom_maintenance_types") or None,
            "type":     aml.get("custom_asset_maintenance_type"),
            "location": {
                "tower": tower,
                "floor": floor,
                "room":  room,
            },
            "reportedBy":      reported_by,
            "reportedOn":      reported_on,
            "assignedTo":      assigned_to,
            "dueDate":         str(todo["date"]) if todo.get("date") else None,
            "description":     description,
            "attachmentCount": len(attachments),
            "attachments":     attachments,
        }

        return Response(
            json.dumps(result, default=str),
            status=200,
            mimetype="application/json",
        )

    except frappe.PermissionError:
        return Response(
            json.dumps({"status": "error", "message": "You do not have permission to access this resource."}),
            status=403, mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(title="get_employee_task_detail error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500, mimetype="application/json",
        )