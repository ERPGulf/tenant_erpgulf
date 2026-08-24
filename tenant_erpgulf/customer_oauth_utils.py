"""
Shared helper for issuing OAuth2 "password grant" tokens for the customer
portal integration.

This is factored out of generate_token_secure_for_customers() so that the
same token-issuance logic can also be called from verify_otp() for
customers who have `custom_password_required` unchecked (password-less /
OTP-only login).

Nothing about the existing generate_token_secure_for_customers() behaviour
changes — this module just extracts STEP 1-4 of that function's original
"FROM HERE: EXACT SAME CODE AS generate_token_secure_for_users" block into
a reusable function.
"""

import base64
import json

import frappe
import requests
from frappe.utils.password import get_decrypted_password
from werkzeug.wrappers import Response


def issue_oauth_tokens_for_app(app_key):
    """
    Decode app_key, resolve the matching OAuth Client, load the tenant's
    service-account credentials from "Tenant Erpgulf Setting Page", and
    request an OAuth2 password-grant token from this site's own
    /api/method/frappe.integrations.oauth2.get_token endpoint.

    Returns a 2-tuple:
        (None, token_json)        on success — token_json is the raw dict
                                   returned by the OAuth2 endpoint
                                   (access_token, refresh_token, etc.)
        (error_response, None)    on failure — error_response is a ready-to
                                   -return werkzeug Response; just
                                   `return error_response` from the caller.
    """

    # ── STEP 0: Tenant service-account credentials ─────────────────────────
    try:
        system_settings = frappe.get_doc("Tenant Erpgulf Setting Page")
        username = system_settings.customer_user
        password = get_decrypted_password(
            "Tenant Erpgulf Setting Page",
            system_settings.name,
            "password",
        )
    except Exception as e:
        return Response(
            json.dumps({
                "status": "error",
                "message": f"Customer user settings not configured: {str(e)}",
                "user_count": 0,
            }),
            status=500,
            mimetype="application/json",
        ), None

    if not username or not password:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Customer user settings not configured",
                "user_count": 0,
            }),
            status=500,
            mimetype="application/json",
        ), None

    # ── STEP 1: Decode app_key ──────────────────────────────────────────────
    try:
        decoded_app_key = base64.b64decode(app_key).decode("utf-8")
    except Exception:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Security Parameters are not valid",
                "user_count": 0,
            }),
            status=401,
            mimetype="application/json",
        ), None

    # ── STEP 2: Fetch OAuth Client by app_name ──────────────────────────────
    oauth_client = frappe.db.get_value(
        "OAuth Client",
        {"app_name": decoded_app_key},
        ["name", "client_id", "client_secret", "user"],
        as_dict=True,
    )

    if not oauth_client or not oauth_client.get("client_id"):
        return Response(
            json.dumps({
                "status": "error",
                "message": "Security Parameters are not valid",
                "user_count": 0,
            }),
            status=401,
            mimetype="application/json",
        ), None

    # ── STEP 3: Validate host_name config ───────────────────────────────────
    host_name = frappe.local.conf.get("host_name")
    if not host_name:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Server configuration error: host_name missing",
                "user_count": 0,
            }),
            status=500,
            mimetype="application/json",
        ), None

    # ── STEP 4: Request token from Frappe OAuth2 endpoint ───────────────────
    token_url = f"{host_name}/api/method/frappe.integrations.oauth2.get_token"

    payload = {
        "username": username,
        "password": password,
        "grant_type": "password",
        "client_id": oauth_client["client_id"],
        "client_secret": oauth_client["client_secret"],
    }

    try:
        token_response = requests.post(
            token_url,
            data=payload,
            headers={"Accept": "application/json"},
            timeout=30,
        )
    except requests.exceptions.Timeout:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Token server timed out",
                "user_count": 0,
            }),
            status=504,
            mimetype="application/json",
        ), None

    if token_response.status_code == 200:
        return None, token_response.json()

    try:
        detail = token_response.json()
    except Exception:
        detail = token_response.text

    return Response(
        json.dumps({
            "status": "error",
            "message": "Invalid credentials or unauthorized",
            "detail": detail,
        }),
        status=401,
        mimetype="application/json",
    ), None