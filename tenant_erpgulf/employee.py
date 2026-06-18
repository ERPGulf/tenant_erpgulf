
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



@frappe.whitelist(allow_guest=True)
def get_location_full_details(location_name):
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

        # ── STEP 2: Resolve Employee from session user ─────────────────────────
        employee_data = None

        emp = frappe.db.get_value(
            "Employee",
            {"user_id": current_user},
            ["name", "employee_name", "user_id"],
            as_dict=True,
        )

        if emp:
            employee_data = emp
        else:
            employee_data = {
                "user_id": current_user,
                "warning": f"No Employee record linked to user '{current_user}'"
            }

        # ── STEP 3: Validate Location ──────────────────────────────────────────
        if not frappe.db.exists("Location", location_name):
            return Response(
                json.dumps({
                    "status": "error",
                    "message": f"Location '{location_name}' not found",
                    "employee": employee_data,
                }),
                status=404,
                mimetype="application/json",
            )

        # ── STEP 4: Fetch only required Location fields ────────────────────────
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

        # ── STEP 5: Fetch room_name from Room Equipment child table ────────────
        room_equipment = frappe.get_all(
            "Room Equipment",
            filters={"parent": location_name},
            fields=["room_name"],
        )
        location["room_equipment"] = room_equipment

        # ── STEP 6: Fetch all Assets linked to this Location ──────────────────
        assets = frappe.get_all(
            "Asset",
            filters={"location": location_name},
            fields=[
                "name",
                "asset_name",
                "item_code",
                "item_name",
                "location",
                "asset_category",
            ],
        )

        # ── STEP 7: Enrich each Asset with Maintenance Logs ───────────────────
        enriched_assets = []

        for asset in assets:
            asset_dict = dict(asset)

            # ── 7a: Reactive logs → custom_asset = asset["name"] ──────────────
            reactive_logs = frappe.get_all(
                "Asset Maintenance Log",
                filters={
                    "custom_asset":                  asset["name"],       # unique asset ID
                    "custom_asset_maintenance_type": "Reactive",
                },
                fields=[
                    "name",
                    "asset_name",
                    "item_code",
                    "item_name",
                    "task_name",
                    "maintenance_status",
                    "maintenance_type",
                    "custom_maintenance_types",
                    "custom_asset_maintenance_type",
                    "custom_asset",
                    "periodicity",
                    "completion_date",
                    "description",
                    "custom_assign_to",
                    "assign_to_name",
                    "custom_default_warehouse",
                ],
            )

            # ── 7b: Planned logs → asset_name = asset["asset_name"] ───────────
            planned_logs = frappe.get_all(
                "Asset Maintenance Log",
                filters={
                    "asset_name":                    asset["asset_name"], # display name
                    "custom_asset_maintenance_type": "Planned",
                },
                fields=[
                    "name",
                    "asset_name",
                    "item_code",
                    "item_name",
                    "task_name",
                    "maintenance_status",
                    "maintenance_type",
                    "custom_maintenance_types",
                    "custom_asset_maintenance_type",
                    "custom_asset",
                    "periodicity",
                    "completion_date",
                    "description",
                    "custom_assign_to",
                    "assign_to_name",
                    "custom_default_warehouse",
                ],
            )

            # ── 7c: Merge both log types ───────────────────────────────────────
            all_logs = reactive_logs + planned_logs

            # ── 7d: Enrich each log with stock items ───────────────────────────
            enriched_logs = []
            for log in all_logs:
                log_dict = dict(log)

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
                enriched_logs.append(log_dict)

            asset_dict["maintenance_logs"] = enriched_logs
            enriched_assets.append(asset_dict)

        # ── STEP 8: Build and return final response ────────────────────────────
        return Response(
            json.dumps(
                {
                    "status": "success",
                    "data": {
                        "employee": employee_data,
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


# import random

# # ════════════════════════════════════════════════════════════════════════════════
# # OTP — GENERATE & SEND via WhatsApp
# # ════════════════════════════════════════════════════════════════════════════════

# @frappe.whitelist(allow_guest=True)
# def generate_and_send_otp(mobile_no):
#     """
#     Generate a 6-digit OTP, cache it for 5 minutes, and send via WhatsApp.

#     Params:
#         mobile_no : Customer mobile number (any format)
#     """
#     try:
#         if not mobile_no:
#             return Response(
#                 json.dumps({
#                     "status": "error",
#                     "message": "mobile_no is required",
#                 }),
#                 status=400,
#                 mimetype="application/json",
#             )

#         # ── STEP 1: Generate OTP ───────────────────────────────────────────────
#         otp = str(random.randint(100000, 999999))

#         # ── STEP 2: Cache OTP against mobile number (expires in 5 min) ────────
#         key = f"otp:{mobile_no}"
#         frappe.cache().set_value(key, otp, expires_in_sec=300)

#         # ── STEP 3: Send OTP via WhatsApp ──────────────────────────────────────
#         send_result = _send_otp_whatsapp(mobile_no, otp)

#         if not send_result.get("success"):
#             return Response(
#                 json.dumps({
#                     "status": "error",
#                     "message": "OTP generated but WhatsApp delivery failed",
#                     "detail": send_result.get("error"),
#                 }),
#                 status=500,
#                 mimetype="application/json",
#             )

#         return Response(
#             json.dumps({
#                 "status":  "success",
#                 "message": "OTP sent successfully",
#                 "mobile":  mobile_no,
#             }),
#             status=200,
#             mimetype="application/json",
#         )

#     except Exception as e:
#         frappe.log_error(
#             title="generate_and_send_otp error",
#             message=frappe.get_traceback()
#         )
#         return Response(
#             json.dumps({
#                 "status":  "error",
#                 "message": str(e),
#             }),
#             status=500,
#             mimetype="application/json",
#         )


# # ════════════════════════════════════════════════════════════════════════════════
# # OTP — VALIDATE
# # ════════════════════════════════════════════════════════════════════════════════

# @frappe.whitelist(allow_guest=True)
# def verify_otp(mobile_no, otp):
#     """
#     Validate the OTP sent to a mobile number.
#     OTP is deleted from cache after successful verification.

#     Params:
#         mobile_no : Same number used in generate_and_send_otp
#         otp       : 6-digit OTP entered by user
#     """
#     try:
#         if not mobile_no or not otp:
#             return Response(
#                 json.dumps({
#                     "status":  "error",
#                     "message": "mobile_no and otp are required",
#                 }),
#                 status=400,
#                 mimetype="application/json",
#             )

#         # ── STEP 1: Fetch cached OTP ───────────────────────────────────────────
#         key        = f"otp:{mobile_no}"
#         stored_otp = frappe.cache().get_value(key)

#         # ── STEP 2: Check if OTP exists ────────────────────────────────────────
#         if not stored_otp:
#             return Response(
#                 json.dumps({
#                     "status":  "error",
#                     "message": "OTP expired or not found. Please request a new OTP.",
#                 }),
#                 status=404,
#                 mimetype="application/json",
#             )

#         # ── STEP 3: Check if OTP matches ──────────────────────────────────────
#         if str(stored_otp) != str(otp):
#             return Response(
#                 json.dumps({
#                     "status":  "error",
#                     "message": "Invalid OTP. Please try again.",
#                 }),
#                 status=400,
#                 mimetype="application/json",
#             )

#         # ── STEP 4: OTP matched — delete from cache immediately ───────────────
#         frappe.cache().delete_key(key)

#         return Response(
#             json.dumps({
#                 "status":  "success",
#                 "message": "OTP verified successfully",
#                 "mobile":  mobile_no,
#             }),
#             status=200,
#             mimetype="application/json",
#         )

#     except Exception as e:
#         frappe.log_error(
#             title="verify_otp error",
#             message=frappe.get_traceback()
#         )
#         return Response(
#             json.dumps({
#                 "status":  "error",
#                 "message": str(e),
#             }),
#             status=500,
#             mimetype="application/json",
#         )


# # ════════════════════════════════════════════════════════════════════════════════
# # INTERNAL — Send OTP via WhatsApp (not exposed as API)
# # ════════════════════════════════════════════════════════════════════════════════

# def _send_otp_whatsapp(mobile_no, otp):
#     """
#     Internal helper — sends OTP via WhatsApp using Whatsapp Saudi config.
#     Returns {"success": True} or {"success": False, "error": "..."}
#     """
#     try:
#         # ── Fetch WhatsApp config ──────────────────────────────────────────────
#         wa_config    = frappe.get_doc("Whatsapp Saudi")
#         url          = wa_config.get("message_url")
#         instance_id  = wa_config.get("instance_id")
#         token        = wa_config.get("token")

#         # ── Clean phone number ─────────────────────────────────────────────────
#         phone = _clean_phone_number(mobile_no)

#         frappe.log_error(
#             title="OTP WhatsApp send",
#             message=f"To: {phone} | OTP: {otp}"
#         )

#         # ── Build message ──────────────────────────────────────────────────────
#         message = (
#             f"رمز التحقق لاستبدال نقاط الولاء في الجواد بريميوم هو *{otp}*.\n"
#             "هذا الرمز صالح لمدة 5 دقائق يُرجى مشاركته مع أمين الصندوق للتحقق.\n\n"
#             f"The verification code for redeeming your loyalty points in Aljawad Premium is *{otp}*. "
#             "This is valid for 5 minutes. Please share it with the cashier for validation."
#         )

#         # ── Send request ───────────────────────────────────────────────────────
#         querystring = {
#             "instanceid": instance_id,
#             "token":      token,
#             "phone":      phone,
#             "body":       message,
#         }

#         response      = requests.get(url, params=querystring, timeout=15)
#         response_dict = response.json()

#         frappe.log_error(
#             title="OTP WhatsApp response",
#             message=frappe.as_json(response_dict)
#         )

#         # ── Handle response ────────────────────────────────────────────────────
#         if response.status_code == 200 and response_dict.get("sent") and response_dict.get("id"):
#             # Log successful send
#             frappe.get_doc({
#                 "doctype": "whatsapp saudi success log",
#                 "title":   "OTP sent successfully",
#                 "message": otp,
#                 "to_number": phone,
#                 "time":    now_datetime(),
#             }).insert(ignore_permissions=True)

#             return {"success": True}

#         else:
#             frappe.log_error(
#                 title="OTP WhatsApp send failed",
#                 message=frappe.as_json(response_dict)
#             )
#             return {
#                 "success": False,
#                 "error":   response_dict,
#             }

#     except requests.exceptions.Timeout:
#         frappe.log_error(
#             title="OTP WhatsApp timeout",
#             message=frappe.get_traceback()
#         )
#         return {"success": False, "error": "WhatsApp API timed out"}

#     except Exception as e:
#         frappe.log_error(
#             title="OTP WhatsApp exception",
#             message=frappe.get_traceback()
#         )
#         return {"success": False, "error": str(e)}


# # ════════════════════════════════════════════════════════════════════════════════
# # INTERNAL — Clean phone number
# # ════════════════════════════════════════════════════════════════════════════════

# def _clean_phone_number(number):
#     """
#     Normalize phone number to international format without + or 00 prefix.
#     e.g. +966501234567 → 966501234567
#          00966501234567 → 966501234567
#          0501234567     → 966501234567
#          501234567      → 966501234567
#     """
#     phone = number.replace("+", "").replace("-", "").replace(" ", "")

#     if phone.startswith("00"):
#         phone = phone[2:]
#     elif phone.startswith("0"):
#         if len(phone) == 10:
#             phone = "966" + phone[1:]
#     else:
#         if len(phone) < 10:
#             phone = "966" + phone

#     if phone.startswith("0"):
#         phone = phone[1:]

#     return phone        
# ════════════════════════════════════════════════════════════════════════════════
# OTP — GENERATE & SEND via WhatsApp
# ════════════════════════════════════════════════════════════════════════════════

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

        return Response(
            json.dumps({
                "status":  "success",
                "message": "OTP verified successfully",
                "mobile":  mobile_no,
            }),
            status=200, mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(title="verify_otp error", message=frappe.get_traceback())
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