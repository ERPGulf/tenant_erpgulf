import base64
import json
import random
import re

import frappe
import requests
from frappe.utils import now_datetime
from werkzeug.wrappers import Response

from tenant_erpgulf.customer_oauth_utils import issue_oauth_tokens_for_app

# NOTE: adjust the import path above to wherever customer_oauth_utils.py
# actually lives in your app, e.g.:
#   from your_app.your_app.api.customer_oauth_utils import issue_oauth_tokens_for_app


# ════════════════════════════════════════════════════════════════════════════════
# PUBLIC — Sign in an existing customer by phone number
# ════════════════════════════════════════════════════════════════════════════════

@frappe.whitelist(allow_guest=True)
def sign_in(mobile_no=None, password=None):
    """
    Sign in an existing customer, looked up by phone number.

    Params:
        mobile_no : phone number used to look up the Customer (same matching
                    logic as generate_and_send_otp / verify_otp).
        password  : compared as plain text against the Customer's
                    custom_password column (NOT overwritten — this is
                    sign-in, not onboarding). Matches how verify_otp.py
                    writes it (frappe.db.set_value, plain text, bypassing
                    Frappe's Password-fieldtype encryption). Driven by
                    custom_password_policy:
                    - "Mandatory": required, must be supplied and must match.
                    - "Optional": only checked if the caller actually supplies
                      one; omitted password = pass.
                    - "No" (or unset): ignored entirely.

    OTP, driven by custom_otp_policy:
        - "Mandatory" or "Optional": an OTP is generated, cached, and sent via
          WhatsApp to the customer's mobile number. Sign-in is NOT completed
          in this call — this only returns "OTP sent". The client must then
          call verify_sign_in_otp(mobile_no, otp) below to receive the access
          + refresh token.
        - "No" (or unset): no OTP is needed — the access + refresh token is
          issued immediately, in this same call.
    """
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
        stored_password = customer.get("custom_password")

        # ── STEP 2: Password check, driven by custom_password_policy ────────
        # Plain-text compare against the tabCustomer.custom_password column —
        # matches verify_otp.py's write side (frappe.db.set_value), not
        # Frappe's Password-fieldtype encryption. Never overwritten here.
        if password_policy == "Mandatory":
            if not password:
                return Response(
                    json.dumps({
                        "status":  "error",
                        "message": "Password is required",
                    }),
                    status=400, mimetype="application/json",
                )
            if not stored_password or stored_password != password:
                return Response(
                    json.dumps({
                        "status":  "error",
                        "message": "Invalid password",
                    }),
                    status=401, mimetype="application/json",
                )

        elif password_policy == "Optional":
            # Only checked if the caller actually supplied one.
            if password and (not stored_password or stored_password != password):
                return Response(
                    json.dumps({
                        "status":  "error",
                        "message": "Invalid password",
                    }),
                    status=401, mimetype="application/json",
                )

        # password_policy == "No" (or anything else) → not checked at all,
        # even if the caller supplies one.

        # ── STEP 3: OTP dispatch, driven by custom_otp_policy ────────────────
        if otp_policy in ("Mandatory", "Optional"):
            return _send_sign_in_otp(customer_id, customer_mobile, password_policy, otp_policy)

        # otp_policy == "No" (or anything else) → no OTP needed, issue token now.
        return _issue_sign_in_token(customer, customer_id, customer_mobile, password_policy, otp_policy)

    except Exception as e:
        frappe.log_error(title="sign_in error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500, mimetype="application/json",
        )


# ════════════════════════════════════════════════════════════════════════════════
# PUBLIC — Step 2 of sign-in when custom_otp_policy is Mandatory/Optional
# ════════════════════════════════════════════════ ════════════════════════════════

@frappe.whitelist(allow_guest=True)
def verify_sign_in_otp(mobile_no=None, otp=None):
    """
    Completes sign-in after sign_in() sent an OTP (custom_otp_policy was
    Mandatory or Optional). Only checks the OTP — password was already
    checked in sign_in() and is NOT re-checked or overwritten here.

    On success, issues the access + refresh token via the same OAuth-Client
    derived app_key structure used by sign_in()'s otp_policy == "No" path.

    Params:
        mobile_no : same phone number passed to sign_in().
        otp       : the OTP code entered by the user. Always required here —
                    this endpoint is only reached when sign_in() already
                    decided an OTP was necessary and sent one.
    """
    try:
        if not mobile_no or not otp:
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "mobile_no and otp are required",
                }),
                status=400, mimetype="application/json",
            )

        customer = _find_customer_by_mobile(mobile_no)

        if not customer:
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "Invalid Customer ID or OTP",
                }),
                status=401, mimetype="application/json",
            )

        customer_id     = customer["name"]
        customer_mobile = customer["mobile_no"]
        password_policy = customer.get("custom_password_policy") or "No"
        otp_policy      = customer.get("custom_otp_policy") or "No"

        # ── Verify OTP against cache (set by sign_in / _send_sign_in_otp) ───
        key        = f"otp:{customer_mobile}"
        cached_otp = frappe.cache().get_value(key)

        if not cached_otp or str(cached_otp) != str(otp):
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "Invalid or expired OTP",
                }),
                status=401, mimetype="application/json",
            )

        frappe.cache().delete_value(key)

        # ── OTP verified — issue access + refresh token ─────────────────────
        return _issue_sign_in_token(customer, customer_id, customer_mobile, password_policy, otp_policy)

    except Exception as e:
        frappe.log_error(title="verify_sign_in_otp error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500, mimetype="application/json",
        )


# ════════════════════════════════════════════════════════════════════════════════
# INTERNAL — Send sign-in OTP (mirrors generate_and_send_otp)
# ════════════════════════════════════════════════════════════════════════════════

def _send_sign_in_otp(customer_id, customer_mobile, password_policy, otp_policy):
    # ── Fetch WhatsApp Saudi config ────────────────────────────────────────
    wa_config   = frappe.get_doc("Whatsapp Saudi")
    is_testing  = wa_config.get("testing")                        # testing checkbox
    testing_otp = str(wa_config.get("testing_otp") or "")        # fixed OTP field

    # ── Determine OTP ────────────────────────────────────────────────────
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

    # ── Cache OTP against mobile number (expires in 5 min) ────────────────
    key = f"otp:{customer_mobile}"
    frappe.cache().set_value(key, otp, expires_in_sec=300)

    # ── Testing mode — skip WhatsApp, return OTP in response ──────────────
    if is_testing:
        frappe.log_error(
            title="[Sign-in OTP] Testing mode — OTP not sent via WhatsApp",
            message=f"customer_id={customer_id} | mobile={customer_mobile} | otp={otp}"
        )
        return Response(
            json.dumps({
                "status":          "success",
                "message":         "OTP sent successfully. Call verify_sign_in_otp to complete sign-in.",
                "customer_id":     customer_id,
                "password_policy": password_policy,
                "otp_policy":      otp_policy,
            }),
            status=200, mimetype="application/json",
        )

    # ── Live mode — send via WhatsApp, never expose OTP ────────────────────
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
            "message":         "OTP sent successfully. Call verify_sign_in_otp to complete sign-in.",
            "customer_id":     customer_id,
            "mobile":          customer_mobile,
            "password_policy": password_policy,
            "otp_policy":      otp_policy,
            # otp intentionally omitted in live mode
        }),
        status=200, mimetype="application/json",
    )


# ════════════════════════════════════════════════════════════════════════════════
# INTERNAL — Issue the access token directly (otp_policy == "No" path)
# ════════════════════════════════════════════════════════════════════════════════

def _issue_sign_in_token(customer, customer_id, customer_mobile, password_policy, otp_policy):
    # ── GET customer phone from primary contact ─────────────────────────
    customer_phone = None
    try:
        primary_contact = customer.get("customer_primary_contact")
        if primary_contact:
            phone_row = frappe.db.get_value(
                "Contact Phone",
                {"parent": primary_contact},
                "phone",
                as_dict=True
            )
            if phone_row:
                customer_phone = phone_row.phone
    except Exception:
        customer_phone = None

    # ── Derive app_key from the site's OAuth Client ─────────────────────
    auth_client_name = frappe.db.get_value("OAuth Client", {}, "name")
    if not auth_client_name:
        return Response(
            json.dumps({"status": "error", "message": "No OAuth Client found"}),
            status=500,
            mimetype="application/json"
        )

    auth_client = frappe.get_doc("OAuth Client", auth_client_name)

    app_name = auth_client.app_name
    if not app_name:
        return Response(
            json.dumps({"status": "error", "message": "App name missing in OAuth Client"}),
            status=500,
            mimetype="application/json"
        )

    client_secret = auth_client.client_secret
    if not client_secret:
        return Response(
            json.dumps({"status": "error", "message": "Client secret missing in OAuth Client"}),
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

    app_key = base64.b64encode(app_name.encode()).decode("utf-8")

    # ── Issue the OAuth2 token via the shared helper ─────────────────────
    error_response, token_json = issue_oauth_tokens_for_app(app_key)
    if error_response:
        return error_response

    return Response(
        json.dumps({
            "status": "success",
            "data": {
                "token": token_json,
                "customer": {
                    "id":            customer_id,
                    "customer_name": customer.get("customer_name"),
                    "phone":         customer_phone or customer_mobile,
                    "email":         customer.get("email_id"),
                },
                "password_policy": password_policy,
                "otp_policy":      otp_policy,
                "time": str(frappe.utils.now_datetime()),
            }
        }),
        status=200,
        mimetype="application/json",
    )


# ════════════════════════════════════════════════════════════════════════════════
# INTERNAL — Match incoming phone number against Customer.mobile_no
# ════════════════════════════════════════════════════════════════════════════════

_CUSTOMER_LOOKUP_FIELDS = """
    name,
    customer_name,
    mobile_no,
    custom_password,
    custom_password_policy,
    custom_otp_policy,
    customer_primary_contact,
    email_id
"""


def _find_customer_by_mobile(mobile_no):
    """
    Tries an EXACT match on mobile_no first — this matters for short/test
    values (e.g. "12345678") where a fuzzy suffix match could accidentally
    hit a different customer that happens to share those digits, silently
    comparing the password against the wrong record.

    Only falls back to matching the last 9 digits (with a deterministic
    `order by name` so results aren't arbitrary) to tolerate real-world
    formatting differences between the incoming payload
    (e.g. 05xxxxxxxx, +9665xxxxxx, 9665xxxxxx) and however the number is
    actually stored.
    """
    if not mobile_no:
        return None

    exact_rows = frappe.db.sql(
        f"""
        select {_CUSTOMER_LOOKUP_FIELDS}
        from `tabCustomer`
        where mobile_no = %s
        limit 1
        """,
        (mobile_no,),
        as_dict=True,
    )
    if exact_rows:
        return exact_rows[0]

    local_number = _extract_local_number(mobile_no)

    if not local_number:
        return None

    rows = frappe.db.sql(
        f"""
        select {_CUSTOMER_LOOKUP_FIELDS}
        from `tabCustomer`
        where mobile_no like %s
        order by name
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
# INTERNAL — Send OTP via WhatsApp (same as generate_and_send_otp)
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
# INTERNAL — Clean phone number (same as generate_and_send_otp)
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