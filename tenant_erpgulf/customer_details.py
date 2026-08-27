import json
import random
import re

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime
from werkzeug.wrappers import Response


# ════════════════════════════════════════════════════════════════════════════════
# PUBLIC — Generate & send OTP, matched by phone number
# ════════════════════════════════════════════════════════════════════════════════

@frappe.whitelist(allow_guest=True)
def generate_and_send_otp(mobile_no=None):
    try:
        if not mobile_no:
            return Response(
                json.dumps({"status": "error", "message": "mobile_no is required"}),
                status=400, mimetype="application/json",
            )

        # ── STEP 1: Look up the Customer whose mobile_no matches the payload ──
        customer = _find_customer_by_mobile(mobile_no)

        if not customer:
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "No customer found for the given phone number",
                }),
                status=404, mimetype="application/json",
            )

        customer_id     = customer["name"]
        customer_mobile = customer["mobile_no"]
        password_policy = customer.get("custom_password_policy") or "No"
        otp_policy      = customer.get("custom_otp_policy") or "No"

        # ── Fetch WhatsApp Saudi config ────────────────────────────────────────
        wa_config   = frappe.get_doc("Whatsapp Saudi")
        is_testing  = wa_config.get("testing")                        # testing checkbox
        testing_otp = str(wa_config.get("testing_otp") or "")        # fixed OTP field

        # ── STEP 2: Determine OTP ──────────────────────────────────────────────
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

        # ── STEP 3: Cache OTP against mobile number (expires in 5 min) ────────
        key = f"otp:{customer_mobile}"
        frappe.cache().set_value(key, otp, expires_in_sec=300)

        # ── STEP 4: If testing — skip WhatsApp, return OTP in response ────────
        if is_testing:
            frappe.log_error(
                title="[OTP] Testing mode — OTP not sent via WhatsApp",
                message=f"customer_id={customer_id} | mobile={customer_mobile} | otp={otp}"
            )
            return Response(
                json.dumps({
                    "status":          "success",
                    "message":         "OTP sent successfully",   # ← returned only in testing mode
                    "customer_id":     customer_id,
                    "password_policy": password_policy,
                    "otp_policy":      otp_policy,
                }),
                status=200, mimetype="application/json",
            )

        # ── STEP 5: Live mode — send via WhatsApp, never expose OTP ──────────
        send_result = _send_otp_whatsapp(customer_mobile, otp)

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
                "status":          "success",
                "message":         "OTP sent successfully",
                "customer_id":     customer_id,
                "mobile":          customer_mobile,
                "password_policy": password_policy,
                "otp_policy":      otp_policy,
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
# INTERNAL — Match incoming phone number against Customer.mobile_no
# ════════════════════════════════════════════════════════════════════════════════

def _find_customer_by_mobile(mobile_no):
    """
    Matches on the last 9 digits so formatting differences between the
    incoming payload (e.g. 05xxxxxxxx, +9665xxxxxx, 9665xxxxxx) and however
    the number is stored on Customer don't cause a false miss.
    """
    local_number = _extract_local_number(mobile_no)

    if not local_number:
        return None

    rows = frappe.db.sql(
        """
        select name, mobile_no, custom_password_policy, custom_otp_policy
        from `tabCustomer`
        where mobile_no like %s
        limit 1
        """,
        (f"%{local_number}",),
        as_dict=True,
    )

    return rows[0] if rows else None


def _extract_local_number(phone):
    """Strip everything but digits and return the last 9 (Saudi local length)."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else digits


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