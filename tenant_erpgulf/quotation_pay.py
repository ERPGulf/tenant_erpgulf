import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def update_quotation_approval(quotation_id, is_approved):
    """
    API to approve or reject a Quotation by updating custom_quotation_status.

    Params:
        quotation_id → Quotation name (e.g. "SAL-QTN-2026-00001")
        is_approved  → true  → sets custom_quotation_status = "Approved"
                       false → sets custom_quotation_status = "Rejected"
    """

    if not quotation_id:
        frappe.throw(_("quotation_id is required"), frappe.MandatoryError)

    if not frappe.db.exists("Quotation", quotation_id):
        frappe.throw(
            _("Quotation '{0}' not found").format(quotation_id),
            frappe.DoesNotExistError,
        )

    # ── Cast is_approved to bool (comes as string from API) ───────
    if isinstance(is_approved, str):
        is_approved = is_approved.lower() in ("1", "true", "yes")

    new_status = "Approved" if is_approved else "Rejected"

    # ── Update custom_quotation_status on Quotation ───────────────
    frappe.db.set_value(
        "Quotation",
        quotation_id,
        "custom_quotation_status",
        new_status,
        update_modified=True,
    )
    frappe.db.commit()

    return {
        "success":     True,
        "quotationId": quotation_id,
        "status":      new_status,
        "message":     f"Quotation {quotation_id} has been {new_status.lower()} successfully",
    }


@frappe.whitelist(allow_guest=False)
def update_payment_status(request_id, is_paid):
    """
    API to mark payment as cleared on Asset Maintenance Log
    linked to a Maintenance Request.

    Params:
        request_id → Maintenance Request name
        is_paid    → true  → sets custom_quotation_status = "Paid"
                     false → do nothing
    """

    if not request_id:
        frappe.throw(_("request_id is required"), frappe.MandatoryError)

    if not frappe.db.exists("Maintenance Request", request_id):
        frappe.throw(
            _("Maintenance Request '{0}' not found").format(request_id),
            frappe.DoesNotExistError,
        )

    # ── Cast is_paid to bool (comes as string from API) ───────────
    if isinstance(is_paid, str):
        is_paid = is_paid.lower() in ("1", "true", "yes")

    # ── If false, do nothing ──────────────────────────────────────
    if not is_paid:
        return {
            "success": True,
            "message": "No changes made. is_paid is false.",
        }

    # ── Fetch Maintenance Request ─────────────────────────────────
    mr = frappe.get_doc("Maintenance Request", request_id)

    if not mr.maintenance_log:
        frappe.throw(
            _("No Maintenance Log linked to this Maintenance Request."),
            frappe.ValidationError,
        )

    # ── Update custom_quotation_status = "Paid" on Maintenance Log ─
    frappe.db.set_value(
        "Asset Maintenance Log",
        mr.maintenance_log,
        "custom_quotation_status",
        "Paid",
        update_modified=True,
    )
    frappe.db.commit()

    return {
        "success":        True,
        "requestId":      request_id,
        "maintenanceLog": mr.maintenance_log,
        "status":         "Paid",
        "message":        f"Payment marked as cleared on Maintenance Log {mr.maintenance_log}",
    }   

import frappe
import json
from datetime import timedelta, date
from werkzeug.wrappers import Response


@frappe.whitelist(allow_guest=False)
def get_customer_quotations(customer_id):
    """
    Returns all quotations linked to a customer's Asset Maintenance Logs.

    Data chain:
        Customer → Maintenance Request (customer field)
                 → Asset Maintenance Log (maintenance_log field)
                 → Quotation (custom_quotation)

    Status logic (derived — not passed as param):
        AML.custom_quotation_status is null/empty → "awaiting_approval"
        AML.custom_quotation_status == "Paid"     → "paid"
        anything else (Pending / Unpaid / etc.)   → "awaiting_payment"

    Response shape per quotation:
        {
            "quotationId":     "SAL-QTN-2026-00043",
            "description":     "Electrical portable appliance testing",
            "maintenanceLogId":"ACC-AML-2026-00113",
            "requestId":       "188aam279e",
            "typeOfTask":      "Reactive",
            "amount":          "AED 1500.00",
            "taxAmount":       "AED 150.00",
            "grandTotal":      "AED 1650.00",
            "issuedDate":      "2026-06-01",
            "dueDate":         "2026-06-08",
            "status":          "awaiting_payment"  | "paid" | "awaiting_approval"
        }
    """

    try:
        # ── STEP 1: Auth ───────────────────────────────────────────────────────
        current_user = frappe.session.user
        if not current_user or current_user == "Guest":
            return Response(
                json.dumps({"status": "error", "message": "Unauthorized. Please provide a valid Bearer token."}),
                status=401,
                mimetype="application/json",
            )

        # ── STEP 2: Validate input ─────────────────────────────────────────────
        if not customer_id:
            return Response(
                json.dumps({"status": "error", "message": "customer_id is required."}),
                status=400,
                mimetype="application/json",
            )

        # ── STEP 3: Fetch all Maintenance Requests for this customer ───────────
        mr_records = frappe.get_all(
            "Maintenance Request",
            filters={"customer": customer_id},
            fields=["name", "maintenance_log", "description"],
        )

        if not mr_records:
            return _empty_response(customer_id)

        # Build maps:
        #   aml_name → mr_name
        #   aml_name → mr_description  (used as quotation description)
        aml_to_mr   = {}
        aml_to_desc = {}
        for mr in mr_records:
            if mr.get("maintenance_log"):
                aml_to_mr[mr["maintenance_log"]]   = mr["name"]
                aml_to_desc[mr["maintenance_log"]]  = mr.get("description") or ""

        aml_names = list(aml_to_mr.keys())
        if not aml_names:
            return _empty_response(customer_id)

        # ── STEP 4: Fetch Asset Maintenance Logs that have a quotation ─────────
        aml_records = frappe.get_all(
            "Asset Maintenance Log",
            filters={
                "name":             ["in", aml_names],
                "custom_quotation": ["!=", ""],
            },
            fields=[
                "name",
                "custom_quotation",
                "custom_quotation_status",
                "custom_asset_maintenance_type",
            ],
        )

        if not aml_records:
            return _empty_response(customer_id)

        # ── STEP 5: Batch-fetch Quotation details ──────────────────────────────
        quotation_ids = [a["custom_quotation"] for a in aml_records if a.get("custom_quotation")]

        quotation_map = {}
        if quotation_ids:
            qtns = frappe.get_all(
                "Quotation",
                filters={"name": ["in", quotation_ids]},
                fields=[
                    "name",
                    "currency",
                    "total",
                    "total_taxes_and_charges",
                    "grand_total",
                    "transaction_date",
                    "custom_quotation_status",  # "Approved" / "Rejected" / empty
                ],
            )
            quotation_map = {q["name"]: q for q in qtns}

        # ── STEP 6: Build response list ────────────────────────────────────────
        quotations = []

        for aml in aml_records:
            qtn_id     = aml.get("custom_quotation")
            qtn_info   = quotation_map.get(qtn_id, {})

            # ── Compute status ─────────────────────────────────────────────────
            # Quotation.custom_quotation_status → "Approved" / "Rejected" / empty
            # AML.custom_quotation_status       → "Paid" / empty / other
            qtn_approval   = (qtn_info.get("custom_quotation_status") or "").strip()
            aml_pay_status = (aml.get("custom_quotation_status") or "").strip()

            if qtn_approval != "Approved":
                # Quotation not yet approved → awaiting approval regardless of AML
                status = "awaiting_approval"
            elif aml_pay_status == "Paid":
                # Quotation approved + AML marked Paid → fully paid
                status = "paid"
            else:
                # Quotation approved but AML not yet marked Paid → awaiting payment
                status = "awaiting_payment"

            # ── Dates ──────────────────────────────────────────────────────────
            issued_date = qtn_info.get("transaction_date")
            due_date    = None
            if issued_date:
                if isinstance(issued_date, str):
                    from datetime import datetime
                    issued_date = datetime.strptime(issued_date, "%Y-%m-%d").date()
                due_date = str(issued_date + timedelta(weeks=1))
                issued_date = str(issued_date)

            # ── Currency formatting helper ─────────────────────────────────────
            currency = qtn_info.get("currency") or "AED"

            def fmt(amount):
                return f"{currency} {float(amount or 0):.2f}"

            quotations.append({
                "quotationId":     qtn_id,
                "description":     aml_to_desc.get(aml["name"], ""),
                "maintenanceLogId": aml["name"],
                "requestId":       aml_to_mr.get(aml["name"]),
                "typeOfTask":      aml.get("custom_asset_maintenance_type") or None,
                "amount":          fmt(qtn_info.get("total")),
                "taxAmount":       fmt(qtn_info.get("total_taxes_and_charges")),
                "grandTotal":      fmt(qtn_info.get("grand_total")),
                "issuedDate":      issued_date,
                "dueDate":         due_date,
                "status":          status,
            })

        # ── STEP 7: Sort — pending approvals first, then awaiting payment, paid last ──
        STATUS_ORDER = {"awaiting_approval": 0, "awaiting_payment": 1, "paid": 2}
        quotations.sort(key=lambda x: STATUS_ORDER.get(x["status"], 9))

        return Response(
            json.dumps(
                {
                    "success":     True,
                    "customerId":  customer_id,
                    "count":       len(quotations),
                    "quotations":  quotations,
                },
                default=str,
            ),
            status=200,
            mimetype="application/json",
        )

    except frappe.PermissionError:
        return Response(
            json.dumps({"status": "error", "message": "You do not have permission to access this resource."}),
            status=403,
            mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(title="get_customer_quotations error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500,
            mimetype="application/json",
        )


def _empty_response(customer_id):
    return Response(
        json.dumps({
            "success":    True,
            "customerId": customer_id,
            "count":      0,
            "quotations": [],
        }),
        status=200,
        mimetype="application/json",
    )    




@frappe.whitelist(allow_guest=False)
def get_quotation_details(quotation_id):
    """
    Returns details for a single Quotation by its ID.

    Data chain (reverse-lookup):
        Quotation → Asset Maintenance Log (custom_quotation == quotation_id)
                  → Maintenance Request   (maintenance_log == AML.name)

    Response shape (identical to get_customer_quotations per-item):
        {
            "quotationId":      "SAL-QTN-2026-00043",
            "description":      "Electrical portable appliance testing",
            "maintenanceLogId": "ACC-AML-2026-00113",
            "requestId":        "188aam279e",
            "typeOfTask":       "Reactive",
            "amount":           "AED 1500.00",
            "taxAmount":        "AED 150.00",
            "grandTotal":       "AED 1650.00",
            "issuedDate":       "2026-06-01",
            "dueDate":          "2026-06-08",
            "status":           "awaiting_payment" | "paid" | "awaiting_approval"
        }

    Status logic (same as get_customer_quotations):
        Quotation.custom_quotation_status != "Approved" → "awaiting_approval"
        AML.custom_quotation_status == "Paid"           → "paid"
        otherwise                                        → "awaiting_payment"
    """

    try:
        # ── STEP 1: Auth ───────────────────────────────────────────────────────
        current_user = frappe.session.user
        if not current_user or current_user == "Guest":
            return Response(
                json.dumps({"status": "error", "message": "Unauthorized. Please provide a valid Bearer token."}),
                status=401,
                mimetype="application/json",
            )

        # ── STEP 2: Validate input ─────────────────────────────────────────────
        if not quotation_id:
            return Response(
                json.dumps({"status": "error", "message": "quotation_id is required."}),
                status=400,
                mimetype="application/json",
            )

        # ── STEP 3: Fetch the Quotation ────────────────────────────────────────
        qtn_list = frappe.get_all(
            "Quotation",
            filters={"name": quotation_id},
            fields=[
                "name",
                "currency",
                "total",
                "total_taxes_and_charges",
                "grand_total",
                "transaction_date",
                "custom_quotation_status",  # "Approved" / "Rejected" / empty
            ],
        )

        if not qtn_list:
            return Response(
                json.dumps({"status": "error", "message": f"Quotation '{quotation_id}' not found."}),
                status=404,
                mimetype="application/json",
            )

        qtn_info = qtn_list[0]

        # ── STEP 4: Find the linked Asset Maintenance Log ──────────────────────
        aml_list = frappe.get_all(
            "Asset Maintenance Log",
            filters={"custom_quotation": quotation_id},
            fields=[
                "name",
                "custom_quotation",
                "custom_quotation_status",
                "custom_asset_maintenance_type",
            ],
        )

        if not aml_list:
            return Response(
                json.dumps({"status": "error", "message": f"No Asset Maintenance Log linked to Quotation '{quotation_id}'."}),
                status=404,
                mimetype="application/json",
            )

        aml = aml_list[0]

        # ── STEP 5: Find the linked Maintenance Request ────────────────────────
        mr_list = frappe.get_all(
            "Maintenance Request",
            filters={"maintenance_log": aml["name"]},
            fields=["name", "description"],
        )

        mr_name   = mr_list[0]["name"]        if mr_list else None
        mr_desc   = mr_list[0].get("description") or "" if mr_list else ""

        # ── STEP 6: Compute status (same logic as get_customer_quotations) ─────
        qtn_approval   = (qtn_info.get("custom_quotation_status") or "").strip()
        aml_pay_status = (aml.get("custom_quotation_status") or "").strip()

        if qtn_approval != "Approved":
            status = "awaiting_approval"
        elif aml_pay_status == "Paid":
            status = "paid"
        else:
            status = "awaiting_payment"

        # ── STEP 7: Dates ──────────────────────────────────────────────────────
        issued_date = qtn_info.get("transaction_date")
        due_date    = None
        if issued_date:
            if isinstance(issued_date, str):
                from datetime import datetime
                issued_date = datetime.strptime(issued_date, "%Y-%m-%d").date()
            due_date    = str(issued_date + timedelta(weeks=1))
            issued_date = str(issued_date)

        # ── STEP 8: Currency formatting ────────────────────────────────────────
        currency = qtn_info.get("currency") or "AED"

        def fmt(amount):
            return f"{currency} {float(amount or 0):.2f}"

        # ── STEP 9: Build and return response ─────────────────────────────────
        return Response(
            json.dumps(
                {
                    "success": True,
                    "quotation": {
                        "quotationId":      quotation_id,
                        "description":      mr_desc,
                        "maintenanceLogId": aml["name"],
                        "requestId":        mr_name,
                        "typeOfTask":       aml.get("custom_asset_maintenance_type") or None,
                        "amount":           fmt(qtn_info.get("total")),
                        "taxAmount":        fmt(qtn_info.get("total_taxes_and_charges")),
                        "grandTotal":       fmt(qtn_info.get("grand_total")),
                        "issuedDate":       issued_date,
                        "dueDate":          due_date,
                        "status":           status,
                    },
                },
                default=str,
            ),
            status=200,
            mimetype="application/json",
        )

    except frappe.PermissionError:
        return Response(
            json.dumps({"status": "error", "message": "You do not have permission to access this resource."}),
            status=403,
            mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(title="get_quotation_details error", message=frappe.get_traceback())
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500,
            mimetype="application/json",
        )    