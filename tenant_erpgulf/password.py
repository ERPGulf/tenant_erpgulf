import json

import frappe
from frappe.utils import cint
from werkzeug.wrappers import Response


@frappe.whitelist(allow_guest=True)
def check_password_required(customer_id):
    """
    Given a customer_id, report whether password-based login is enabled
    or disabled for that customer (i.e. the custom_password_required
    checkbox on the Customer doctype).

    Params:
        customer_id : ERPNext Customer document name / ID

    Response:
        {
            "status": "success",
            "customer_id": "...",
            "password_required": true | false
        }
    """
    try:
        if not customer_id:
            return Response(
                json.dumps({
                    "status": "error",
                    "message": "customer_id is required",
                }),
                status=400, mimetype="application/json",
            )

        customer = frappe.db.get_value(
            "Customer",
            customer_id,
            ["name", "custom_password_required"],
            as_dict=True,
        )

        if not customer:
            return Response(
                json.dumps({
                    "status": "error",
                    "message": "Invalid Customer ID",
                }),
                status=404, mimetype="application/json",
            )

        # Default to "required" (1) when the field is missing/None, so this
        # matches the same fallback used in generate_token_secure_for_customers
        # and verify_otp.
        password_required = customer.get("custom_password_required")
        password_required = 1 if password_required is None else cint(password_required)

        return Response(
            json.dumps({
                "status": "success",
                "customer_id": customer.name,
                "password_required": bool(password_required),
            }),
            status=200, mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(title="check_password_required error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500, mimetype="application/json",
        )