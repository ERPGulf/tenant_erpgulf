
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

        # ── STEP 3: Fetch ToDo tasks assigned to this employee ──────────────────
        # reference_type can be either:
        #   - "Asset Maintenance"      → planned/preventive (needs two-hop lookup)
        #   - "Asset Maintenance Log"  → reactive/breakdown (fields already on it)
        todos = frappe.get_all(
            "ToDo",
            filters={
                "allocated_to":   current_user,
                "reference_type": ["in", ["Asset Maintenance", "Asset Maintenance Log"]],
                "status":         ["not in", ["Cancelled"]],
            },
            fields=["name", "status", "priority", "date", "reference_name", "reference_type"],
            order_by="date asc",
        )

        # ── STEP 4: Map to required response shape ─────────────────────────────
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
            maintenance_type = None

            ref_name = todo.get("reference_name")
            ref_type = todo.get("reference_type")

            if ref_type == "Asset Maintenance Log":
                # ── Reactive: read the log directly, no parent hop needed ──────
                if ref_name and frappe.db.exists("Asset Maintenance Log", ref_name):
                    log = frappe.db.get_value(
                        "Asset Maintenance Log",
                        ref_name,
                        [
                            "name",
                            "asset_name",
                            "custom_employee_work_status",
                            "custom_asset_maintenance_type",
                        ],
                        as_dict=True,
                    )
                    if log:
                        work_status      = log.get("custom_employee_work_status")
                        maintenance_type = log.get("custom_asset_maintenance_type")
                        task_name        = log.get("asset_name")

            elif ref_type == "Asset Maintenance":
                # ── Planned/preventive: parent + child task + linked log ───────
                if ref_name and frappe.db.exists("Asset Maintenance", ref_name):
                    asset_maintenance = frappe.db.get_value(
                        "Asset Maintenance",
                        ref_name,
                        ["name", "asset_name", "item_name"],
                        as_dict=True,
                    )

                    task_row = frappe.get_all(
                        "Asset Maintenance Task",
                        filters={"parent": ref_name, "assign_to": current_user},
                        fields=["maintenance_task", "maintenance_type"],
                        limit_page_length=1,
                    )
                    if not task_row:
                        task_row = frappe.get_all(
                            "Asset Maintenance Task",
                            filters={"parent": ref_name},
                            fields=["maintenance_task", "maintenance_type"],
                            order_by="idx asc",
                            limit_page_length=1,
                        )

                    if task_row:
                        task_name = task_row[0].get("maintenance_task")

                    if not task_name and asset_maintenance:
                        task_name = (
                            asset_maintenance.get("asset_name")
                            or asset_maintenance.get("item_name")
                        )

                    log = frappe.get_all(
                        "Asset Maintenance Log",
                        filters={"asset_maintenance": ref_name},
                        fields=["name", "custom_employee_work_status", "custom_asset_maintenance_type"],
                        order_by="creation desc",
                        limit_page_length=1,
                    )
                    if log:
                        work_status      = log[0].get("custom_employee_work_status")
                        maintenance_type = log[0].get("custom_asset_maintenance_type")

            if not task_name:
                task_name = ref_name

            tasks.append({
                "id":              todo["name"],
                "name":            task_name,
                # send exactly what's in custom_employee_work_status — no mapping,
                # only default to "New" when the field itself is empty
                "status":          work_status or "New",
                "priority":        PRIORITY_MAP.get(todo.get("priority"), "medium"),
                "dueDate":         str(todo["date"]) if todo.get("date") else None,
                "maintenanceType": maintenance_type,
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

        # ── STEP 4: Resolve the Asset Maintenance Log ───────────────────────────
        # reference_type on the ToDo can be either:
        #   - "Asset Maintenance Log"  → reference_name IS the log, use directly
        #   - "Asset Maintenance"      → reference_name is the parent; find the
        #                                log linked to it via `asset_maintenance`
        ref_name = todo.get("reference_name")
        ref_type = todo.get("reference_type")

        aml_name = None

        if ref_type == "Asset Maintenance Log":
            if ref_name and frappe.db.exists("Asset Maintenance Log", ref_name):
                aml_name = ref_name

        elif ref_type == "Asset Maintenance":
            if ref_name and frappe.db.exists("Asset Maintenance", ref_name):
                matching_logs = frappe.get_all(
                    "Asset Maintenance Log",
                    filters={"asset_maintenance": ref_name, "custom_assign_to": current_user},
                    fields=["name"],
                    order_by="creation desc",
                    limit_page_length=1,
                )
                if not matching_logs:
                    matching_logs = frappe.get_all(
                        "Asset Maintenance Log",
                        filters={"asset_maintenance": ref_name},
                        fields=["name"],
                        order_by="creation desc",
                        limit_page_length=1,
                    )
                if matching_logs:
                    aml_name = matching_logs[0]["name"]

        if not aml_name:
            return Response(
                json.dumps({"status": "error", "message": f"Asset Maintenance Log for reference '{ref_name}' not found"}),
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

        # ── STEP 5: Resolve Asset → location + room + name/code ────────────────
        # custom_asset_maintenance_type decides which AML field holds the Asset ID:
        #   Reactive  -> custom_asset
        #   Planned   -> asset_name (this AML field is actually a Link to Asset)
        # Whichever branch we're in, asset_id ends up normalized, so everything
        # fetched from the Asset doc below (and the response keys built from it)
        # is identical in shape for both Reactive and Planned tasks.
        is_reactive   = aml.get("custom_asset_maintenance_type") == "Reactive"
        asset_id      = aml.get("custom_asset") if is_reactive else aml.get("asset_name")

        location_name   = None
        room            = None
        asset_name_val  = None
        asset_item_code = None
        asset_item_name = None

        if asset_id and frappe.db.exists("Asset", asset_id):
            asset_doc = frappe.db.get_value(
                "Asset",
                asset_id,
                ["location", "custom_room_name", "asset_name", "item_code", "item_name"],
                as_dict=True,
            )
            location_name   = asset_doc.get("location")
            room            = asset_doc.get("custom_room_name") or None
            asset_name_val  = asset_doc.get("asset_name")
            asset_item_code = asset_doc.get("item_code")
            asset_item_name = asset_doc.get("item_name")

        # ── STEP 6: Resolve Location → Floor → Building (tower) ───────────────
        tower        = None
        floor        = None
        customer_id  = None
        building     = None
        compound     = None
        flat_number  = None

        if location_name and frappe.db.exists("Location", location_name):
            location = frappe.db.get_value(
                "Location",
                location_name,
                ["custom_floor", "custom_customer", "custom_flat_number", "custom_building", "custom_compound"],
                as_dict=True,
            )

            customer_id = location.get("custom_customer")
            building    = location.get("custom_building")
            compound    = location.get("custom_compound")
            flat_number = location.get("custom_flat_number")

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

        # ── STEP 9a: Resolve maintenance team based on maintenance type ────────
        # Reactive  → custom_maintenance_team field directly on the AML
        # Planned   → AML.asset_maintenance (link) → Asset Maintenance doc → maintenance_team field
        maintenance_team = None
        asset_maintenance_name = aml.get("asset_maintenance")

        if is_reactive:
            maintenance_team = aml.get("custom_maintenance_team") or None
        else:
            if asset_maintenance_name and frappe.db.exists("Asset Maintenance", asset_maintenance_name):
                maintenance_team = frappe.db.get_value(
                    "Asset Maintenance",
                    asset_maintenance_name,
                    "maintenance_team",
                ) or None

        # ── STEP 9b: Resolve assignedTo ─────────────────────────────────────────
        # Reactive  → custom_assign_to (User) directly on the AML
        # Planned   → assign_to / assign_to_name live on the Asset Maintenance Task
        #             child row, not on the AML — go fetch that row instead.
        assigned_to = {"id": None, "name": None, "team": None}

        if is_reactive:
            assign_user = aml.get("custom_assign_to")
            if assign_user and frappe.db.exists("User", assign_user):
                user_data = frappe.db.get_value(
                    "User",
                    assign_user,
                    ["name", "full_name"],
                    as_dict=True,
                )
                assigned_to = {
                    "id":   assign_user,
                    "name": user_data.get("full_name") or assign_user,
                    "team": maintenance_team,
                }
        else:
            if asset_maintenance_name and frappe.db.exists("Asset Maintenance", asset_maintenance_name):
                # Prefer the row matching this AML's task_name (in case a parent
                # Asset Maintenance has multiple task rows for different employees).
                task_rows = frappe.get_all(
                    "Asset Maintenance Task",
                    filters={"parent": asset_maintenance_name, "maintenance_task": aml.get("task_name")},
                    fields=["assign_to", "assign_to_name"],
                    limit_page_length=1,
                )
                if not task_rows:
                    task_rows = frappe.get_all(
                        "Asset Maintenance Task",
                        filters={"parent": asset_maintenance_name},
                        fields=["assign_to", "assign_to_name"],
                        order_by="idx asc",
                        limit_page_length=1,
                    )
                if task_rows:
                    assigned_to = {
                        "id":   task_rows[0].get("assign_to"),
                        "name": task_rows[0].get("assign_to_name") or task_rows[0].get("assign_to"),
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
                "tower":      tower,
                "floor":      floor,
                "room":       room,
                "building":   building,
                "compound":   compound,
                "flatNumber": flat_number,
            },
            # Same shape/keys regardless of Reactive vs Planned, since asset_id
            # was already normalized in STEP 5.
            "asset": {
                "id":        asset_id,
                "assetName": asset_name_val,
                "itemCode":  asset_item_code,
                "itemName":  asset_item_name,
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


@frappe.whitelist(allow_guest=False)
def update_employee_task_status(task_id, status, date=None, reason=None):
    """
    Update the Employee Work Status on the Asset Maintenance Log linked to a ToDo.

    Args:
        task_id : ToDo document name (e.g. "dhb3c0s6dn")
        status  : One of "in_progress" | "on_hold" | "completed"
        date    : Optional date string (YYYY-MM-DD). Only applied to completion_date
                  when status == "completed". Ignored for all other statuses.
        reason  : Required when status == "on_hold" (reason for the hold).
                  Ignored for all other statuses.
    """
    try:
        # ── STEP 1: Auth ───────────────────────────────────────────────────────
        current_user = frappe.session.user
        if not current_user or current_user == "Guest":
            return Response(
                json.dumps({"status": "error", "message": "Unauthorized. Please provide a valid Bearer token."}),
                status=401, mimetype="application/json",
            )

        # ── STEP 2: Validate + map incoming status ─────────────────────────────
        # API accepts: in_progress | on_hold | completed
        # Stored in doctype as: In Progress | On Hold | Completed
        STATUS_MAP = {
            "in_progress": "In Progress",
            "on_hold":     "On Hold",
            "completed":   "Completed",
        }

        status_key = (status or "").strip().lower()
        if status_key not in STATUS_MAP:
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": f"Invalid status '{status}'. Allowed values: {list(STATUS_MAP.keys())}",
                }),
                status=400, mimetype="application/json",
            )

        db_status = STATUS_MAP[status_key]

        # ── STEP 2b: Reason is required for on_hold, ignored otherwise ─────────
        reason = (reason or "").strip() if reason else ""
        if status_key == "on_hold" and not reason:
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "Reason is required when status is 'on_hold'.",
                }),
                status=400, mimetype="application/json",
            )

        # ── STEP 3: Fetch the ToDo ─────────────────────────────────────────────
        if not frappe.db.exists("ToDo", task_id):
            return Response(
                json.dumps({"status": "error", "message": f"Task '{task_id}' not found"}),
                status=404, mimetype="application/json",
            )

        todo = frappe.db.get_value(
            "ToDo",
            task_id,
            ["name", "reference_name", "reference_type", "allocated_to"],
            as_dict=True,
        )

        # ── STEP 4: Verify task belongs to this user ───────────────────────────
        if todo.get("allocated_to") != current_user:
            return Response(
                json.dumps({"status": "error", "message": "You do not have access to this task."}),
                status=403, mimetype="application/json",
            )

        # ── STEP 5: Resolve the Asset Maintenance Log ───────────────────────────
        # reference_type on the ToDo can be either:
        #   - "Asset Maintenance Log"  → reference_name IS the log, use directly
        #   - "Asset Maintenance"      → reference_name is the parent; find the
        #                                log linked to it via `asset_maintenance`
        ref_name = todo.get("reference_name")
        ref_type = todo.get("reference_type")

        if ref_type not in ("Asset Maintenance Log", "Asset Maintenance"):
            return Response(
                json.dumps({"status": "error", "message": "This task is not linked to an Asset Maintenance Log."}),
                status=400, mimetype="application/json",
            )

        aml_name = None

        if ref_type == "Asset Maintenance Log":
            if ref_name and frappe.db.exists("Asset Maintenance Log", ref_name):
                aml_name = ref_name

        elif ref_type == "Asset Maintenance":
            if ref_name and frappe.db.exists("Asset Maintenance", ref_name):
                matching_logs = frappe.get_all(
                    "Asset Maintenance Log",
                    filters={"asset_maintenance": ref_name, "custom_assign_to": current_user},
                    fields=["name"],
                    order_by="creation desc",
                    limit_page_length=1,
                )
                if not matching_logs:
                    matching_logs = frappe.get_all(
                        "Asset Maintenance Log",
                        filters={"asset_maintenance": ref_name},
                        fields=["name"],
                        order_by="creation desc",
                        limit_page_length=1,
                    )
                if matching_logs:
                    aml_name = matching_logs[0]["name"]

        # ── STEP 6: Fetch the Asset Maintenance Log ────────────────────────────
        if not aml_name or not frappe.db.exists("Asset Maintenance Log", aml_name):
            return Response(
                json.dumps({"status": "error", "message": f"Asset Maintenance Log for reference '{ref_name}' not found"}),
                status=404, mimetype="application/json",
            )

        aml = frappe.get_doc("Asset Maintenance Log", aml_name)

        # ── STEP 7: Update custom_employee_work_status ─────────────────────────
        aml.custom_employee_work_status = db_status

        # ── STEP 7b: On hold → store the reason. Clear it once status moves on.
        if status_key == "on_hold":
            aml.custom_hold_reason = reason
        else:
            aml.custom_hold_reason = None

        # ── STEP 8: If Completed → also update maintenance_status + completion_date
        if status_key == "completed":
            aml.maintenance_status = "Completed"
            if date:
                aml.completion_date = date
            else:
                # fallback to today if no date provided
                aml.completion_date = frappe.utils.nowdate()

        # ── STEP 9: Save (no submit, no validation bypass) ────────────────────
        aml.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.log_error(
            title="[update_employee_task_status] SUCCESS",
            message=f"task_id={task_id} | aml={aml_name} | status={db_status} | date={date} | reason={reason}"
        )

        # ── STEP 10: Build response ────────────────────────────────────────────
        response_data = {
            "status":  "success",
            "message": f"Task status updated to '{db_status}' successfully.",
            "data": {
                "taskId":               task_id,
                "maintenanceLogId":     aml_name,
                "employeeWorkStatus":   db_status,
                "maintenanceStatus":    aml.maintenance_status,
                "completionDate":       str(aml.completion_date) if aml.completion_date else None,
                "holdReason":           aml.custom_hold_reason,
            }
        }

        return Response(
            json.dumps(response_data, default=str),
            status=200,
            mimetype="application/json",
        )

    except frappe.ValidationError as e:
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=400, mimetype="application/json",
        )

    except frappe.PermissionError:
        return Response(
            json.dumps({"status": "error", "message": "You do not have permission to perform this action."}),
            status=403, mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(
            title="update_employee_task_status error",
            message=frappe.get_traceback()
        )
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500, mimetype="application/json",
        )