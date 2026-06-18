import frappe
from frappe import _
import base64
import json
import requests
from werkzeug.wrappers import Response


@frappe.whitelist(allow_guest=True)
def generate_token_secure(api_key, api_secret, app_key):
    """
    Generate OAuth2 access token using ERPNext credentials.
    
    Params:
        api_key     : ERPNext username (e.g. user@example.com)
        api_secret  : ERPNext password
        app_key     : Base64-encoded OAuth app_name
    """
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
            "username": api_key,
            "password": api_secret,
            "grant_type": "password",
            "client_id": oauth_client["client_id"],
            "client_secret": oauth_client["client_secret"],
        }

        token_response = requests.post(
            token_url,
            data=payload,                          # form-encoded, not JSON
            headers={"Accept": "application/json"},
            timeout=30
        )

        # ── STEP 5: Return token or error ─────────────────────────────────────
        if token_response.status_code == 200:
            return Response(
                json.dumps({
                    "status": "success",
                    "data": token_response.json()
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
                "message": str(e),              # ← str(e) fixes your original bug
                "user_count": 0
            }),
            status=500,
            mimetype="application/json",
        )


@frappe.whitelist(allow_guest=True)
def generate_token_secure_for_users(username, password, app_key):
    """
    Generate OAuth2 access token for POS users with user profile & branch info.

    Params:
        username : ERPNext user email
        password : ERPNext password
        app_key  : Base64-encoded OAuth app_name
    """
    frappe.log_error(
        title="Login attempt",
        message=f"{username}    {password}    {app_key}",
    )

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

        # ── STEP 5: Fetch user profile ─────────────────────────────────────────
        user_info = frappe.get_list(
            "User",
            fields=["name as id", "full_name", "mobile_no as phone", "email"],
            filters={"name": ["like", username]},
        )

        # ── STEP 6: Fetch POS system settings ─────────────────────────────────
        try:
            system_settings = frappe.get_doc("Claudion POS setting")
            branch_id = system_settings.branch
        except Exception:
            branch_id = None

        # ── STEP 7: Return token + user data or error ──────────────────────────
        if token_response.status_code == 200:
            return Response(
                json.dumps({
                    "status": "success",
                    "data": {
                        "token": token_response.json(),
                        "user": user_info[0] if user_info else {},
                        "time": str(frappe.utils.now_datetime()),
                        "branch_id": branch_id,
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
                "message": str(e),          # str(e) prevents non-serializable crash
                "user_count": 0
            }),
            status=500,
            mimetype="application/json",
        )