
import frappe
import base64
import json
import requests
from werkzeug.wrappers import Response


@frappe.whitelist(allow_guest=True)
def generate_token_secure_for_customers(customer_id, password, app_key):
    """
    Generate OAuth2 access token for customers.

    Params:
        customer_id : ERPNext Customer document name / ID
        password    : Customer's custom_password field value
        app_key     : Base64-encoded OAuth app_name
    """
    frappe.log_error(
        title="Customer login attempt",
        message=f"{customer_id}    {app_key}",
    )

    # ── PRE-CHECK: Validate customer ID and password first ────────────────────
    customer_doc = frappe.db.get_value(
        "Customer",
        {"name": customer_id},
        ["name", "customer_name", "custom_password", "customer_primary_contact", "email_id"],
        as_dict=True
    )

    if not customer_doc:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Invalid Customer ID or Password",
                "user_count": 0
            }),
            status=401,
            mimetype="application/json",
        )

    from frappe.utils.password import get_decrypted_password

    try:
        stored_password = get_decrypted_password("Customer", customer_id, "custom_password")
    except Exception:
        stored_password = None

    if not stored_password or stored_password != password:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Invalid Customer ID or Password",
                "user_count": 0
            }),
            status=401,
            mimetype="application/json",
        )

    # ── GET customer phone from primary contact ────────────────────────────────
    customer_phone = None
    try:
        primary_contact = customer_doc.get("customer_primary_contact")
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

    # ── GET username and password from Tenant Erpgulf Setting Page ───────────
    try:
        system_settings = frappe.get_doc("Tenant Erpgulf Setting Page")
        username = system_settings.customer_user
        password = get_decrypted_password(
            "Tenant Erpgulf Setting Page",
            system_settings.name,
            "password"
        )
    except Exception as e:
        return Response(
            json.dumps({
                "status": "error",
                "message": f"Customer user settings not configured: {str(e)}",
                "user_count": 0
            }),
            status=500,
            mimetype="application/json",
        )

    if not username or not password:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Customer user settings not configured",
                "user_count": 0
            }),
            status=500,
            mimetype="application/json",
        )

    # ── FROM HERE: EXACT SAME CODE AS generate_token_secure_for_users ─────────
    try:
        # ── STEP 1: Decode app_key ────────────────────────────────────────────
        try:
            decoded_app_key = base64.b64decode(app_key).decode("utf-8")
        except Exception:
            return Response(
                json.dumps({
                    "status": "error",
                    "message": "Security Parameters are not valid",
                    "user_count": 0
                }),
                status=401,
                mimetype="application/json",
            )

        # ── STEP 2: Fetch OAuth Client by app_name ────────────────────────────
        oauth_client = frappe.db.get_value(
            "OAuth Client",
            {"app_name": decoded_app_key},
            ["name", "client_id", "client_secret", "user"],
            as_dict=True
        )

        if not oauth_client or not oauth_client.get("client_id"):
            return Response(
                json.dumps({
                    "status": "error",
                    "message": "Security Parameters are not valid",
                    "user_count": 0
                }),
                status=401,
                mimetype="application/json",
            )

        # ── STEP 3: Validate host_name config ─────────────────────────────────
        host_name = frappe.local.conf.get("host_name")
        if not host_name:
            return Response(
                json.dumps({
                    "status": "error",
                    "message": "Server configuration error: host_name missing",
                    "user_count": 0
                }),
                status=500,
                mimetype="application/json",
            )

        # ── STEP 4: Request token from Frappe OAuth2 endpoint ─────────────────
        token_url = f"{host_name}/api/method/frappe.integrations.oauth2.get_token"

        payload = {
            "username": username,
            "password": password,
            "grant_type": "password",
            "client_id": oauth_client["client_id"],
            "client_secret": oauth_client["client_secret"],
        }

        token_response = requests.post(
            token_url,
            data=payload,
            headers={"Accept": "application/json"},
            timeout=30
        )

        # ── STEP 5: Return token + customer data or error ──────────────────────
        if token_response.status_code == 200:
            return Response(
                json.dumps({
                    "status": "success",
                    "data": {
                        "token": token_response.json(),
                        "customer": {
                            "id": customer_doc.name,
                            "customer_name": customer_doc.customer_name,
                            "phone": customer_phone,
                            "email": customer_doc.get("email_id"),
                        },
                        "time": str(frappe.utils.now_datetime()),
                    }
                }),
                status=200,
                mimetype="application/json",
            )
        else:
            return Response(
                json.dumps({
                    "status": "error",
                    "message": "Invalid credentials or unauthorized",
                    "detail": token_response.json()
                }),
                status=401,
                mimetype="application/json",
            )

    except requests.exceptions.Timeout:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Token server timed out",
                "user_count": 0
            }),
            status=504,
            mimetype="application/json",
        )

    except Exception as e:
        return Response(
            json.dumps({
                "status": "error",
                "message": str(e),
                "user_count": 0
            }),
            status=500,
            mimetype="application/json",
        )


@frappe.whitelist(allow_guest=True)
def refresh_customer_token(refresh_token):
    """
    Create a new access token using a refresh token.

    Params:
        refresh_token: The refresh token string received during initial login
    """
    frappe.log_error(
        title="Customer token refresh attempt",
        message=f"Refresh token used: {refresh_token[:20]}..." if refresh_token else "No token provided",
    )

    # ── VALIDATE INPUT ─────────────────────────────────────────────────────────
    if not refresh_token:
        return Response(
            json.dumps({
                "status": "error",
                "message": "Refresh token is required",
            }),
            status=400,
            mimetype="application/json",
        )

    # ── VALIDATE HOST CONFIG ───────────────────────────────────────────────────
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

    # ── REQUEST NEW TOKEN FROM FRAPPE OAuth2 ENDPOINT ─────────────────────────
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

        # ── RETURN NEW TOKEN DATA OR ERROR ─────────────────────────────────────
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