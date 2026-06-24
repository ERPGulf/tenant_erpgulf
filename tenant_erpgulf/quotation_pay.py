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