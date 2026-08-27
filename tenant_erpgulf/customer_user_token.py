# import base64
# import json
# import re

# import frappe
# from werkzeug.wrappers import Response

# from tenant_erpgulf.customer_oauth_utils import issue_oauth_tokens_for_app

# # NOTE: adjust the import path above to wherever customer_oauth_utils.py
# # actually lives in your app, e.g.:
# #   from your_app.your_app.api.customer_oauth_utils import issue_oauth_tokens_for_app


# @frappe.whitelist(allow_guest=True)
# def verify_otp(mobile_no=None, otp=None, password=None):
#     """
#     Verify the OTP sent via generate_and_send_otp, optionally check the
#     customer's password (driven by custom_password_policy), and — on
#     success — issue an OAuth2 access token.

#     app_key is no longer accepted from the caller — it's derived internally
#     from the site's OAuth Client, same as generate_token_secure_for_customers.

#     Params:
#         mobile_no : phone number used to look up the Customer (same matching
#                     logic as generate_and_send_otp) and the OTP cache key.
#         otp       : the OTP code entered by the user. Always required and
#                     always checked against what generate_and_send_otp
#                     cached — custom_otp_policy is not consulted here.
#         password  : Not verified against any existing value — it's written
#                     straight into the Customer's custom_password field once
#                     OTP/identity is confirmed. custom_password_policy only
#                     controls whether it's expected:
#                     - "Mandatory": required; missing password = rejected.
#                     - "Optional": saved if supplied; omitted = skipped, no
#                       error and custom_password left as-is.
#                     - "No" (or unset): ignored entirely, even if supplied.
#     """
#     try:
#         if not mobile_no:
#             return Response(
#                 json.dumps({
#                     "status":  "error",
#                     "message": "mobile_no is required",
#                     "user_count": 0,
#                 }),
#                 status=400, mimetype="application/json",
#             )

#         frappe.log_error(
#             title="Customer OTP login attempt",
#             message=f"{mobile_no}",
#         )

#         # ── STEP 1: Look up the Customer whose mobile_no matches the payload ──
#         customer = _find_customer_by_mobile(mobile_no)

#         if not customer:
#             return Response(
#                 json.dumps({
#                     "status":  "error",
#                     "message": "Invalid Customer ID or Password",
#                     "user_count": 0,
#                 }),
#                 status=401, mimetype="application/json",
#             )

#         customer_id     = customer["name"]
#         customer_mobile = customer["mobile_no"]
#         password_policy = customer.get("custom_password_policy") or "No"
#         stored_password = customer.get("custom_password")

#         # ── STEP 2: OTP check — always required, custom_otp_policy is not
#         # consulted here (that policy only governs whether generate_and_send_otp
#         # actually sends one; verification here is unconditional).
#         if not otp:
#             return Response(
#                 json.dumps({
#                     "status":  "error",
#                     "message": "OTP is required",
#                     "user_count": 0,
#                 }),
#                 status=400, mimetype="application/json",
#             )

#         key        = f"otp:{customer_mobile}"
#         cached_otp = frappe.cache().get_value(key)

#         if not cached_otp or str(cached_otp) != str(otp):
#             return Response(
#                 json.dumps({
#                     "status":  "error",
#                     "message": "Invalid or expired OTP",
#                     "user_count": 0,
#                 }),
#                 status=401, mimetype="application/json",
#             )
#         frappe.cache().delete_value(key)

#         # ── STEP 3: Password handling, driven by custom_password_policy ─────
#         # Not compared against the existing stored value — whatever is sent
#         # here is simply (re)written into custom_password once OTP/identity
#         # is confirmed. Policy only controls whether a password is expected.
#         if password_policy == "Mandatory":
#             if not password:
#                 return Response(
#                     json.dumps({
#                         "status":  "error",
#                         "message": "password is required",
#                         "user_count": 0,
#                     }),
#                     status=400, mimetype="application/json",
#                 )
#             frappe.db.set_value("Customer", customer_id, "custom_password", password)
#             stored_password = password

#         elif password_policy == "Optional":
#             # Only save if the caller actually supplied one.
#             if password:
#                 frappe.db.set_value("Customer", customer_id, "custom_password", password)
#                 stored_password = password

#         # password_policy == "No" (or anything else) → password ignored entirely,
#         # even if the caller passes one — custom_password is left untouched.

#         # ── GET customer phone from primary contact ─────────────────────────
#         customer_phone = None
#         try:
#             primary_contact = customer.get("customer_primary_contact")
#             if primary_contact:
#                 phone_row = frappe.db.get_value(
#                     "Contact Phone",
#                     {"parent": primary_contact},
#                     "phone",
#                     as_dict=True
#                 )
#                 if phone_row:
#                     customer_phone = phone_row.phone
#         except Exception:
#             customer_phone = None

#         # ── STEP 4: Derive app_key from the site's OAuth Client ─────────────
#         auth_client_name = frappe.db.get_value("OAuth Client", {}, "name")
#         if not auth_client_name:
#             return Response(
#                 json.dumps({"status": "error", "message": "No OAuth Client found"}),
#                 status=500,
#                 mimetype="application/json"
#             )

#         auth_client = frappe.get_doc("OAuth Client", auth_client_name)

#         app_name = auth_client.app_name
#         if not app_name:
#             return Response(
#                 json.dumps({"status": "error", "message": "App name missing in OAuth Client"}),
#                 status=500,
#                 mimetype="application/json"
#             )

#         client_secret = auth_client.client_secret
#         if not client_secret:
#             return Response(
#                 json.dumps({"status": "error", "message": "Client secret missing in OAuth Client"}),
#                 status=500,
#                 mimetype="application/json"
#             )

#         host_name = frappe.local.conf.get("host_name")
#         if not host_name:
#             return Response(
#                 json.dumps({"status": "error", "message": "host_name missing in site config"}),
#                 status=500,
#                 mimetype="application/json"
#             )

#         app_key = base64.b64encode(app_name.encode()).decode("utf-8")

#         # ── STEP 5: Issue the OAuth2 token via the shared helper ────────────
#         error_response, token_json = issue_oauth_tokens_for_app(app_key)
#         if error_response:
#             return error_response

#         return Response(
#             json.dumps({
#                 "status": "success",
#                 "data": {
#                     "token": token_json,
#                     "customer": {
#                         "id":            customer_id,
#                         "customer_name": customer.get("customer_name"),
#                         "phone":         customer_phone or customer_mobile,
#                         "email":         customer.get("email_id"),
#                     },
#                     "time": str(frappe.utils.now_datetime()),
#                 }
#             }),
#             status=200,
#             mimetype="application/json",
#         )

#     except Exception as e:
#         frappe.log_error(title="verify_otp error", message=frappe.get_traceback())
#         return Response(
#             json.dumps({"status": "error", "message": str(e), "user_count": 0}),
#             status=500, mimetype="application/json",
#         )


# # ════════════════════════════════════════════════════════════════════════════════
# # INTERNAL — Match incoming phone number against Customer.mobile_no
# # ════════════════════════════════════════════════════════════════════════════════

# def _find_customer_by_mobile(mobile_no):
#     """
#     Matches on the last 9 digits so formatting differences between the
#     incoming payload (e.g. 05xxxxxxxx, +9665xxxxxx, 9665xxxxxx) and however
#     the number is stored on Customer don't cause a false miss.
#     """
#     local_number = _extract_local_number(mobile_no)

#     if not local_number:
#         return None

#     rows = frappe.db.sql(
#         """
#         select
#             name,
#             customer_name,
#             mobile_no,
#             custom_password,
#             custom_password_policy,
#             customer_primary_contact,
#             email_id
#         from `tabCustomer`
#         where mobile_no like %s
#         limit 1
#         """,
#         (f"%{local_number}",),
#         as_dict=True,
#     )

#     return rows[0] if rows else None


# def _extract_local_number(phone):
#     """Strip everything but digits and return the last 9 (Saudi local length)."""
#     digits = re.sub(r"\D", "", phone or "")
#     return digits[-9:] if len(digits) >= 9 else digits
import base64
import json
import re

import frappe
from werkzeug.wrappers import Response

from tenant_erpgulf.customer_oauth_utils import issue_oauth_tokens_for_app

# NOTE: adjust the import path above to wherever customer_oauth_utils.py
# actually lives in your app, e.g.:
#   from your_app.your_app.api.customer_oauth_utils import issue_oauth_tokens_for_app


@frappe.whitelist(allow_guest=True)
def verify_otp(mobile_no=None, otp=None, password=None):
    """
    Verify the OTP sent via generate_and_send_otp, optionally check the
    customer's password (driven by custom_password_policy), and — on
    success — issue an OAuth2 access token.

    app_key is no longer accepted from the caller — it's derived internally
    from the site's OAuth Client, same as generate_token_secure_for_customers.

    Params:
        mobile_no : phone number used to look up the Customer (same matching
                    logic as generate_and_send_otp) and the OTP cache key.
        otp       : the OTP code entered by the user. Always required and
                    always checked against what generate_and_send_otp
                    cached — custom_otp_policy is not consulted here.
        password  : Not verified against any existing value — it's written
                    straight into the Customer's custom_password field once
                    OTP/identity is confirmed, exactly as received (no
                    hashing, no transformation). custom_password_policy only
                    controls whether it's expected:
                    - "Mandatory": required; missing password = rejected.
                    - "Optional": saved if supplied; omitted = skipped, no
                      error and custom_password left as-is.
                    - "No" (or unset): ignored entirely, even if supplied.
    """
    try:
        if not mobile_no:
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "mobile_no is required",
                    "user_count": 0,
                }),
                status=400, mimetype="application/json",
            )

        frappe.log_error(
            title="Customer OTP login attempt",
            message=f"{mobile_no}",
        )

        # ── STEP 1: Look up the Customer whose mobile_no matches the payload ──
        customer = _find_customer_by_mobile(mobile_no)

        if not customer:
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "Invalid Customer ID or Password",
                    "user_count": 0,
                }),
                status=401, mimetype="application/json",
            )

        customer_id     = customer["name"]
        customer_mobile = customer["mobile_no"]
        password_policy = customer.get("custom_password_policy") or "No"
        stored_password = customer.get("custom_password")

        # ── STEP 2: OTP check — always required, custom_otp_policy is not
        # consulted here (that policy only governs whether generate_and_send_otp
        # actually sends one; verification here is unconditional).
        if not otp:
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "OTP is required",
                    "user_count": 0,
                }),
                status=400, mimetype="application/json",
            )

        key        = f"otp:{customer_mobile}"
        cached_otp = frappe.cache().get_value(key)

        if not cached_otp or str(cached_otp) != str(otp):
            return Response(
                json.dumps({
                    "status":  "error",
                    "message": "Invalid or expired OTP",
                    "user_count": 0,
                }),
                status=401, mimetype="application/json",
            )
        frappe.cache().delete_value(key)

        # ── STEP 3: Password handling, driven by custom_password_policy ─────
        # Not compared against the existing stored value — whatever is sent
        # here is simply (re)written into custom_password once OTP/identity
        # is confirmed, stored exactly as received (no hashing). Policy only
        # controls whether a password is expected.
        if password_policy == "Mandatory":
            if not password:
                return Response(
                    json.dumps({
                        "status":  "error",
                        "message": "password is required",
                        "user_count": 0,
                    }),
                    status=400, mimetype="application/json",
                )
            _write_custom_password(customer_id, password)
            stored_password = password

        elif password_policy == "Optional":
            # Only save if the caller actually supplied one.
            if password:
                _write_custom_password(customer_id, password)
                stored_password = password

        # password_policy == "No" (or anything else) → password ignored entirely,
        # even if the caller passes one — custom_password is left untouched.

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

        # ── STEP 4: Derive app_key from the site's OAuth Client ─────────────
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

        # ── STEP 5: Issue the OAuth2 token via the shared helper ────────────
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
                    "time": str(frappe.utils.now_datetime()),
                }
            }),
            status=200,
            mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(title="verify_otp error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e), "user_count": 0}),
            status=500, mimetype="application/json",
        )


# ════════════════════════════════════════════════════════════════════════════════
# INTERNAL — Write custom_password as a literal value, no hashing
# ════════════════════════════════════════════════════════════════════════════════

def _write_custom_password(customer_id, password):
    """
    custom_password is fieldtype "Password" on the Customer doctype. Going
    through doc.save() (or anything that triggers Document controller hooks)
    would route a Password-fieldtype value into Frappe's encrypted __Auth
    table instead of the plain tabCustomer column — which is exactly what we
    do NOT want here, since the requirement is: store precisely what was
    passed in, unmodified, in custom_password itself.

    To guarantee that, this bypasses frappe.db.set_value / doc.save() and
    issues a direct SQL UPDATE against the table column, then commits
    explicitly so the write is not left pending on the request transaction.

    NOTE: because the field's fieldtype is still Password, the Desk UI will
    still render it as masked dots when you open the Customer form — that is
    a client-side rendering behavior tied to the fieldtype and is unrelated
    to whether the value was actually saved. This function guarantees the
    literal value is what lands in the database column; it does not (and
    cannot) change how the Password widget displays it in Desk.
    """
    frappe.db.sql(
        """
        update `tabCustomer`
        set custom_password = %s
        where name = %s
        """,
        (password, customer_id),
    )
    frappe.db.commit()


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
        select
            name,
            customer_name,
            mobile_no,
            custom_password,
            custom_password_policy,
            customer_primary_contact,
            email_id
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
@frappe.whitelist(allow_guest=True)
def refresh_customer_token(refresh_token):
    """
    Create a new access token using a refresh token.
    Unchanged by this customization — refreshing is independent of whether
    the customer originally logged in via password or OTP.

    Params:
        refresh_token: The refresh token string received during initial login
    """
    frappe.log_error(
        title="Customer token refresh attempt",
        message=f"Refresh token used: {refresh_token[:20]}..." if refresh_token else "No token provided",
    )

    if not refresh_token:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Refresh token is required",
            }),
            status=400,
            mimetype="application/json",
        )

    host_name = frappe.local.conf.get("host_name")
    if not host_name:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Server configuration error: host_name missing",
            }),
            status=500,
            mimetype="application/json",
        )

    try:
        token_url = f"{host_name}/api/method/frappe.integrations.oauth2.get_token"

        payload = f"grant_type=refresh_token&refresh_token={refresh_token}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        token_response = requests.post(
            token_url,
            headers=headers,
            data=payload,
            timeout=30
        )

        if token_response.status_code == 200:
            try:
                message_json = token_response.json()
                new_token_data = {
                    "access_token": message_json["access_token"],
                    "expires_in": message_json["expires_in"],
                    "token_type": message_json["token_type"],
                    "scope": message_json["scope"],
                    "refresh_token": message_json["refresh_token"],
                }
                return Response(
                    json.dumps({
                        "status": "success",
                        "data": {
                            "token": new_token_data,
                            "time": str(frappe.utils.now_datetime()),
                        }
                    }),
                    status=200,
                    mimetype="application/json",
                )
            except (json.JSONDecodeError, KeyError) as e:
                return Response(
                    json.dumps({
                        "status": "error",
                        "message": f"Error parsing token response: {str(e)}",
                    }),
                    status=500,
                    mimetype="application/json",
                )
        else:
            return Response(
                json.dumps({
                    "status": "error",
                    "message": "Invalid or expired refresh token",
                    "detail": token_response.text,
                }),
                status=401,
                mimetype="application/json",
            )

    except requests.exceptions.Timeout:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Token server timed out",
            }),
            status=504,
            mimetype="application/json",
        )

    except Exception as e:
        return Response(
            json.dumps({
                "status": "error",
                "message": str(e),
            }),
            status=500,
            mimetype="application/json",
        )