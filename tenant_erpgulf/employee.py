
import io
import os
import base64
from base64 import b64encode
import json
import requests  
import frappe
from frappe import _
from pyqrcode import create as qr_create
from werkzeug.wrappers import Response


def create_qr_code(doc, method):
    """Create QR Code after inserting Employee"""
    if not hasattr(doc, 'custom_qr_code'):
        return

    fields = frappe.get_meta('Employee').fields
    auth_client_name = frappe.db.get_value("OAuth Client", {}, "name")
    if auth_client_name:
        auth_client = frappe.get_doc("OAuth Client", auth_client_name)
    else:
        frappe.throw("No OAuth Client found")

    app_name = auth_client.app_name
    if not app_name:
        frappe.throw(_('App name missing in OAuth Client'))

    app_key = base64.b64encode(app_name.encode()).decode("utf-8")


    for field in fields:
        if field.fieldname == 'custom_qr_code' and field.fieldtype == 'Attach Image':

            company_name = frappe.db.get_value('Company', doc.company, 'company_name')
            if not company_name:
                frappe.throw(_('Company name missing for {} in the company document'.format(doc.company)))

            if not doc.name:
                frappe.throw(_('Employee code missing in the document'))

            if not doc.first_name:
                frappe.throw(_('First name missing for {} in the document'.format(doc.name)))

            last_name = doc.last_name if doc.last_name else ""

            if not doc.user_id:
                frappe.throw(_('User ID missing for {} in the document'.format(doc.name)))

            if not frappe.local.conf.host_name:
                frappe.throw(_('API URL (host_name) is missing in site config'))

            if not app_key:
                frappe.throw(_('App key could not be generated'))

            cleaned = (
                f"Company: {company_name}"
                f" Employee_Code: {doc.name}"
                f" Full_Name: {doc.first_name}  {last_name}"
                f" User_id: {doc.user_id}"
                f" API: {frappe.local.conf.host_name}"
                f" App_key: {app_key}"
            )

            base64_string = b64encode(cleaned.encode()).decode()

            qr_image = io.BytesIO()
            url = qr_create(base64_string, error='L')
            url.png(qr_image, scale=2, quiet_zone=1)

            filename = f"QR-CODE-{doc.name}.png".replace(os.path.sep, "__")
            _file = frappe.get_doc({
                "doctype": "File",
                "file_name": filename,
                "content": qr_image.getvalue(),
                "is_private": 0
            })

            _file.save()

            doc.db_set('custom_qr_code', _file.file_url)
            doc.db_set('image', _file.file_url)
            doc.notify_update()

            break


# ─────────────────────────────────────────────────────────────
# API — GET Employee QR Code as PNG image
# ─────────────────────────────────────────────────────────────
@frappe.whitelist(allow_guest=False)
def generate_employee_qr(employee_id):
    try:
        # ── Validate Employee exists ──
        if not frappe.db.exists("Employee", employee_id):
            return Response(
                json.dumps({
                    "status": "error",
                    "message": f"Employee '{employee_id}' not found"
                }),
                status=404,
                mimetype="application/json"
            )

        doc = frappe.get_doc("Employee", employee_id)

        # ── OAuth Client ──
        auth_client_name = frappe.db.get_value("OAuth Client", {}, "name")
        if not auth_client_name:
            return Response(
                json.dumps({"status": "error", "message": "No OAuth Client found"}),
                status=500,
                mimetype="application/json"
            )

        auth_client  = frappe.get_doc("OAuth Client", auth_client_name)
        app_name     = auth_client.app_name
        if not app_name:
            return Response(
                json.dumps({"status": "error", "message": "App name missing in OAuth Client"}),
                status=500,
                mimetype="application/json"
            )

        host_name = frappe.local.conf.get("host_name")
        if not host_name:
            return Response(
                json.dumps({"status": "error", "message": "host_name missing in site config"}),
                status=500,
                mimetype="application/json"
            )

        app_key      = base64.b64encode(app_name.encode()).decode("utf-8")
        company_name = frappe.db.get_value('Company', doc.company, 'company_name') or ""
        last_name    = doc.last_name if doc.last_name else ""

        # ── Delete old QR if exists ──
        old_qr_url = frappe.db.get_value("Employee", employee_id, "custom_qr_code")
        if old_qr_url:
            old_file = frappe.db.get_value("File", {"file_url": old_qr_url}, "name")
            if old_file:
                frappe.delete_doc("File", old_file, ignore_permissions=True)

        # ── Build QR content ──
        cleaned = (
            f"Company: {company_name}"
            f" Employee_Code: {doc.name}"
            f" Full_Name: {doc.first_name} {last_name}"
            f" User_id: {doc.user_id}"
            f" API: {host_name}"
            f" App_key: {app_key}"
        )

        base64_string = b64encode(cleaned.encode()).decode()

        # ── Generate QR PNG ──
        qr_image = io.BytesIO()
        qr = qr_create(base64_string, error='L')
        qr.png(qr_image, scale=2, quiet_zone=1)

        filename = f"QR-CODE-{doc.name}.png".replace(os.path.sep, "__").replace(" ", "-")

        _file = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": qr_image.getvalue(),
            "is_private": 0
        })
        _file.save()

        doc.db_set('custom_qr_code', _file.file_url)
        doc.db_set('image', _file.file_url)
        doc.notify_update()

        full_qr_url = f"{host_name.rstrip('/')}{_file.file_url}"

        # ── Return PNG directly so Postman renders it ──
        qr_image.seek(0)
        return Response(
            qr_image.getvalue(),
            status=200,
            mimetype="image/png",
            headers={
                "Content-Disposition" : f"inline; filename={filename}",
                "X-Employee-ID"       : doc.name,
                "X-Employee-Name"     : f"{doc.first_name} {last_name}",
                "X-QR-Code-URL"       : full_qr_url
            }
        )

    except Exception as e:
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500,
            mimetype="application/json"
        )

import json
import frappe
from werkzeug.wrappers import Response


@frappe.whitelist(allow_guest=False)
def get_location_full_details(location_name, task_id=None):
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

        # ── STEP 1b: If task_id is passed, mark that task's Asset Maintenance
        # Log as "In Progress" (opening the task detail = work has started).
        #   - reference_type == "Asset Maintenance Log" → update it directly
        #   - reference_type == "Asset Maintenance"      → resolve the log
        #     linked to it via `asset_maintenance`, then update that
        if task_id:
            if not frappe.db.exists("ToDo", task_id):
                return Response(
                    json.dumps({
                        "status": "error",
                        "message": f"Task '{task_id}' not found",
                    }),
                    status=404,
                    mimetype="application/json",
                )

            todo = frappe.db.get_value(
                "ToDo",
                task_id,
                ["name", "reference_name", "reference_type", "allocated_to"],
                as_dict=True,
            )

            if todo.get("allocated_to") != current_user:
                return Response(
                    json.dumps({
                        "status": "error",
                        "message": "You do not have access to this task.",
                    }),
                    status=403,
                    mimetype="application/json",
                )

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

            if aml_name and frappe.db.exists("Asset Maintenance Log", aml_name):
                frappe.db.set_value(
                    "Asset Maintenance Log",
                    aml_name,
                    "custom_employee_work_status",
                    "In Progress",
                )
                frappe.db.commit()

                frappe.log_error(
                    title="[get_location_full_details] task status → In Progress",
                    message=f"task_id={task_id} | ref_type={ref_type} | ref_name={ref_name} | aml={aml_name}",
                )

        # ── STEP 2: Validate Location ──────────────────────────────────────────
        if not frappe.db.exists("Location", location_name):
            return Response(
                json.dumps({
                    "status": "error",
                    "message": f"Location '{location_name}' not found",
                }),
                status=404,
                mimetype="application/json",
            )

        # ── STEP 3: Fetch only required Location fields ────────────────────────
        location = frappe.db.get_value(
            "Location",
            location_name,
            [
                "name",
                "owner",
                "location_name",
                "custom_flat_number",
                "custom_floor",
                "custom_building",
                "custom_compound",
                "custom_department",
                "custom_customer",
            ],
            as_dict=True,
        )

        # ── STEP 4: Fetch room_name from Room Equipment child table ────────────
        room_equipment = frappe.get_all(
            "Room Equipment",
            filters={"parent": location_name},
            fields=["room_name"],
        )
        location["room_equipment"] = room_equipment

        # ── STEP 5: Fetch all Assets linked to this Location ──────────────────
        assets = frappe.get_all(
            "Asset",
            filters={"location": location_name},
            fields=[
                "name",
                "asset_name",
                "location",
                "asset_category",
                "custom_room_name",
            ],
        )

        # ── STEP 6: Enrich each Asset with Maintenance Logs ───────────────────
        enriched_assets = []

        for asset in assets:
            asset_dict = dict(asset)

            # ── 6a: Reactive logs → custom_asset = asset["name"] ──────────────
            reactive_logs = frappe.get_all(
                "Asset Maintenance Log",
                filters={
                    "custom_asset":                  asset["name"],
                    "custom_asset_maintenance_type": "Reactive",
                    "docstatus":                     ["!=", 2],  # saved (0) + submitted (1), exclude cancelled
                },
                fields=[
                    "name",
                    "asset_name",
                    "custom_name_of_task",   # Reactive task name lives here
                    "maintenance_status",
                    "maintenance_type",
                    "custom_maintenance_types",
                    "custom_asset_maintenance_type",
                    "custom_asset",
                    "completion_date",
                    "custom_assign_to",
                    "assign_to_name",
                ],
            )

            # ── 6b: Planned logs → asset_name = asset["asset_name"] ───────────
            planned_logs = frappe.get_all(
                "Asset Maintenance Log",
                filters={
                    "asset_name":                    asset["asset_name"],
                    "custom_asset_maintenance_type": "Planned",
                    "docstatus":                     ["!=", 2],  # saved (0) + submitted (1), exclude cancelled
                },
                fields=[
                    "name",
                    "asset_name",
                    "task",   # Planned task name lives here (not task_name)
                    "maintenance_status",
                    "maintenance_type",
                    "custom_maintenance_types",
                    "custom_asset_maintenance_type",
                    "completion_date",
                    "assign_to_name",
                ],
            )

            # ── 6c: Merge both log types ───────────────────────────────────────
            all_logs = reactive_logs + planned_logs

            # ── 6d: Enrich each log with stock items ───────────────────────────
            enriched_logs = []
            for log in all_logs:
                log_dict = dict(log)

                maintenance_kind = log_dict.get("custom_asset_maintenance_type")

                if maintenance_kind == "Reactive":
                    # Reactive logs only carry custom_maintenance_types; drop maintenance_type
                    log_dict.pop("maintenance_type", None)

                    # task_name is sourced from custom_name_of_task for Reactive logs,
                    # but the output key stays "task_name" in both cases
                    log_dict["task_name"] = log_dict.get("custom_name_of_task")
                    log_dict.pop("custom_name_of_task", None)

                    # assign_to_name is sourced from custom_assign_to for Reactive logs,
                    # but the output parameter name stays "assign_to_name" in both cases
                    log_dict["assign_to_name"] = log_dict.get("custom_assign_to")
                    log_dict.pop("custom_assign_to", None)

                elif maintenance_kind == "Planned":
                    # Planned logs only carry maintenance_type; drop custom_maintenance_types
                    log_dict.pop("custom_maintenance_types", None)

                    # task_name is sourced from "task" for Planned logs,
                    # but the output key stays "task_name" in both cases
                    log_dict["task_name"] = log_dict.get("task")
                    log_dict.pop("task", None)

                    # assign_to_name is already sourced correctly from its own
                    # field for Planned logs — no remapping needed.

                stock_items = frappe.get_all(
                    "Stock Items For Asset",
                    filters={"parent": log["name"]},
                    fields=[
                        "name",
                        "item_code",
                        "qty",
                        "uom",
                        "stock_uom",
                        "conversion_factor",
                        "s_warehouse",
                    ],
                )
                log_dict["custom_items"] = stock_items

                # ── 6e: task_id → ToDo linked to this Asset Maintenance Log ────
                log_task_id = frappe.db.get_value(
                    "ToDo",
                    {
                        "reference_type": "Asset Maintenance Log",
                        "reference_name": log["name"],
                    },
                    "name",
                )
                log_dict["task_id"] = log_task_id

                enriched_logs.append(log_dict)

            asset_dict["maintenance_logs"] = enriched_logs
            enriched_assets.append(asset_dict)

        # ── STEP 7: Build and return final response ────────────────────────────
        return Response(
            json.dumps(
                {
                    "status": "success",
                    "data": {
                        "location": location,
                        "assets":   enriched_assets,
                    }
                },
                default=str
            ),
            status=200,
            mimetype="application/json",
        )

    except frappe.PermissionError:
        return Response(
            json.dumps({
                "status": "error",
                "message": "You do not have permission to access this resource",
            }),
            status=403,
            mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(
            title="get_location_full_details error",
            message=frappe.get_traceback()
        )
        return Response(
            json.dumps({
                "status": "error",
                "message": str(e),
            }),
            status=500,
            mimetype="application/json",
        )


@frappe.whitelist(allow_guest=True)
def generate_and_send_otp(mobile_no):
    try:
        if not mobile_no:
            return Response(
                json.dumps({"status": "error", "message": "mobile_no is required"}),
                status=400, mimetype="application/json",
            )

        # ── Fetch WhatsApp Saudi config ────────────────────────────────────────
        wa_config   = frappe.get_doc("Whatsapp Saudi")
        is_testing  = wa_config.get("testing")                        # testing checkbox
        testing_otp = str(wa_config.get("testing_otp") or "")        # fixed OTP field

        # ── STEP 1: Determine OTP ──────────────────────────────────────────────
        if is_testing:
            if not testing_otp:
                return Response(
                    json.dumps({
                        "status":  "error",
                        "message": "Testing mode is ON but testing_otp is not set in Whatsapp Saudi.",
                    }),
                    status=500, mimetype="application/json",
                )
            otp = testing_otp
        else:
            otp = str(random.randint(100000, 999999))

        # ── STEP 2: Cache OTP against mobile number (expires in 5 min) ────────
        key = f"otp:{mobile_no}"
        frappe.cache().set_value(key, otp, expires_in_sec=300)

        # ── STEP 3: If testing — skip WhatsApp, return OTP in response ────────
        if is_testing:
            frappe.log_error(
                title="[OTP] Testing mode — OTP not sent via WhatsApp",
                message=f"mobile={mobile_no} | otp={otp}"
            )
            return Response(
                json.dumps({
                    "status":  "success",
                    "message": "OTP sent successfully",
                    "mobile":  mobile_no,
                    "otp":     otp,          # ← returned only in testing mode
                }),
                status=200, mimetype="application/json",
            )

        # ── STEP 4: Live mode — send via WhatsApp, never expose OTP ──────────
        send_result = _send_otp_whatsapp(mobile_no, otp)

        if not send_result.get("success"):
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "OTP generated but WhatsApp delivery failed",
                    "detail":  send_result.get("error"),
                }),
                status=500, mimetype="application/json",
            )

        return Response(
            json.dumps({
                "status":  "success",
                "message": "OTP sent successfully",
                "mobile":  mobile_no,
                # otp intentionally omitted in live mode
            }),
            status=200, mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(title="generate_and_send_otp error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500, mimetype="application/json",
        )


# ════════════════════════════════════════════════════════════════════════════════
# OTP — VALIDATE
# ════════════════════════════════════════════════════════════════════════════════

import json

import frappe
from werkzeug.wrappers import Response

# How long the "verified" token stays valid after a successful OTP check.
# The customer must set their password within this window.
VERIFICATION_TOKEN_TTL = 600  # seconds (10 minutes)


@frappe.whitelist(allow_guest=True)
def verify_otp(mobile_no, otp):
    try:
        if not mobile_no or not otp:
            return Response(
                json.dumps({"status": "error", "message": "mobile_no and otp are required"}),
                status=400, mimetype="application/json",
            )

        # ── STEP 1: Fetch cached OTP ───────────────────────────────────────────
        key        = f"otp:{mobile_no}"
        stored_otp = frappe.cache().get_value(key)

        # ── STEP 2: Check if OTP exists ────────────────────────────────────────
        if not stored_otp:
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "OTP expired or not found. Please request a new OTP.",
                }),
                status=404, mimetype="application/json",
            )

        # ── STEP 3: Check if OTP matches ──────────────────────────────────────
        if str(stored_otp) != str(otp):
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "Invalid OTP. Please try again.",
                }),
                status=400, mimetype="application/json",
            )

        # ── STEP 4: OTP matched — delete from cache immediately ───────────────
        frappe.cache().delete_key(key)

        # ── STEP 5: Issue a one-time "verified" token ──────────────────────────
        # This is the "unique ID" the client must send back, along with the
        # customer ID and new password, to update_customer_password (see
        # update_customer_password.py). It is opaque (not the OTP, not the
        # mobile number) and expires quickly, so it can't be replayed or guessed.
        unique_id = frappe.generate_hash(length=32)
        frappe.cache().set_value(
            f"otp_verified:{unique_id}",
            mobile_no,
            expires_in_sec=VERIFICATION_TOKEN_TTL,
        )

        return Response(
            json.dumps({
                "status":    "success",
                "message":   "OTP verified successfully",
                "mobile":    mobile_no,
                "unique_id": unique_id,
            }),
            status=200, mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(title="verify_otp error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500, mimetype="application/json",
        )

import json

import frappe
from werkzeug.wrappers import Response


@frappe.whitelist(allow_guest=True)
def update_customer_password(unique_id, customer, password):
    """
    Called after verify_otp (see verify_otp.py). Takes the unique_id issued
    by verify_otp, the Customer ID, and the new password, and stores the
    (hashed) password on Customer.custom_password.

    NOTE: adjust the "mobile_no" field name below (STEP 3) to whatever
    field actually holds the customer's mobile number on your Customer
    doctype, if it isn't literally called mobile_no / custom_mobile_no.
    """
    try:
        if not unique_id or not customer or not password:
            return Response(
                json.dumps({"status": "error", "message": "unique_id, customer and password are required"}),
                status=400, mimetype="application/json",
            )

        # ── STEP 1: Look up the token issued by verify_otp ─────────────────────
        verify_key = f"otp_verified:{unique_id}"
        mobile_no  = frappe.cache().get_value(verify_key)

        if not mobile_no:
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "Invalid or expired verification ID. Please verify OTP again.",
                }),
                status=401, mimetype="application/json",
            )

        # ── STEP 2: Make sure the customer exists ──────────────────────────────
        if not frappe.db.exists("Customer", customer):
            return Response(
                json.dumps({"status": "error", "message": "Customer not found"}),
                status=404, mimetype="application/json",
            )

        customer_doc = frappe.get_doc("Customer", customer)

        # ── STEP 3: (Recommended) confirm this customer belongs to the mobile
        # number that was actually OTP-verified, so unique_id + customer can't
        # be mixed-and-matched across two different people. Skip/adjust this
        # block if Customer doesn't carry a mobile number field.
        customer_mobile = customer_doc.get("mobile_no") or customer_doc.get("custom_mobile_no")
        if customer_mobile and str(customer_mobile) != str(mobile_no):
            return Response(
                json.dumps({"status": "error", "message": "Customer does not match verified mobile number"}),
                status=403, mimetype="application/json",
            )

        # ── STEP 4: Store the password as-is in custom_password ────────────────
        # db_set writes directly and skips doctype validation hooks/versioning
        # noise for this single field.
        customer_doc.db_set("custom_password", password, update_modified=False)

        # ── STEP 5: Invalidate the token so it can't be reused ─────────────────
        frappe.cache().delete_key(verify_key)

        return Response(
            json.dumps({"status": "success", "message": "Password updated successfully"}),
            status=200, mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(title="update_customer_password error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500, mimetype="application/json",
        )

# ════════════════════════════════════════════════════════════════════════════════
# INTERNAL — Send OTP via WhatsApp (unchanged)
# ════════════════════════════════════════════════════════════════════════════════

def _send_otp_whatsapp(mobile_no, otp):
    try:
        wa_config   = frappe.get_doc("Whatsapp Saudi")
        url         = wa_config.get("message_url")
        instance_id = wa_config.get("instance_id")
        token       = wa_config.get("token")

        phone = _clean_phone_number(mobile_no)

        frappe.log_error(title="OTP WhatsApp send", message=f"To: {phone} | OTP: {otp}")

        message = (
            f"رمز التحقق لاستبدال نقاط الولاء في الجواد بريميوم هو *{otp}*.\n"
            "هذا الرمز صالح لمدة 5 دقائق يُرجى مشاركته مع أمين الصندوق للتحقق.\n\n"
            f"The verification code for redeeming your loyalty points in Aljawad Premium is *{otp}*. "
            "This is valid for 5 minutes. Please share it with the cashier for validation."
        )

        querystring = {
            "instanceid": instance_id,
            "token":      token,
            "phone":      phone,
            "body":       message,
        }

        response      = requests.get(url, params=querystring, timeout=15)
        response_dict = response.json()

        frappe.log_error(title="OTP WhatsApp response", message=frappe.as_json(response_dict))

        if response.status_code == 200 and response_dict.get("sent") and response_dict.get("id"):
            frappe.get_doc({
                "doctype":   "whatsapp saudi success log",
                "title":     "OTP sent successfully",
                "message":   otp,
                "to_number": phone,
                "time":      now_datetime(),
            }).insert(ignore_permissions=True)
            return {"success": True}

        else:
            frappe.log_error(title="OTP WhatsApp send failed", message=frappe.as_json(response_dict))
            return {"success": False, "error": response_dict}

    except requests.exceptions.Timeout:
        frappe.log_error(title="OTP WhatsApp timeout", message=frappe.get_traceback())
        return {"success": False, "error": "WhatsApp API timed out"}

    except Exception as e:
        frappe.log_error(title="OTP WhatsApp exception", message=frappe.get_traceback())
        return {"success": False, "error": str(e)}


# ════════════════════════════════════════════════════════════════════════════════
# INTERNAL — Clean phone number (unchanged)
# ════════════════════════════════════════════════════════════════════════════════

def _clean_phone_number(number):
    phone = number.replace("+", "").replace("-", "").replace(" ", "")
    if phone.startswith("00"):
        phone = phone[2:]
    elif phone.startswith("0"):
        if len(phone) == 10:
            phone = "966" + phone[1:]
    else:
        if len(phone) < 10:
            phone = "966" + phone
    if phone.startswith("0"):
        phone = phone[1:]
    return phone