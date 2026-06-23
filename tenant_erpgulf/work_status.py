import frappe
from frappe import _


def get_field_change_date(doctype, docname, field, value):
    """
    Fetch the date when a specific field was set to a specific value
    by scanning Document Version history (activity log).
    """
    try:
        versions = frappe.get_all(
            "Version",
            filters={
                "ref_doctype": doctype,
                "docname":     docname,
            },
            fields=["data", "creation"],
            order_by="creation asc",
        )

        for version in versions:
            import json
            data = json.loads(version.get("data") or "{}")
            changed = data.get("changed", [])
            for change in changed:
                # change format: [fieldname, old_value, new_value]
                if (
                    len(change) >= 3
                    and change[0] == field
                    and str(change[2]) == str(value)
                ):
                    return str(version["creation"])
    except Exception:
        pass
    return None


@frappe.whitelist(allow_guest=False)
def get_work_status(request_id):
    """
    GET API to fetch Maintenance Request details with status timeline.

    Params:
        request_id → Maintenance Request name (e.g. "MR-2026-00001")
    """

    if not request_id:
        frappe.throw(_("request_id is required"), frappe.MandatoryError)

    if not frappe.db.exists("Maintenance Request", request_id):
        frappe.throw(
            _("Maintenance Request '{0}' not found").format(request_id),
            frappe.DoesNotExistError,
        )

    doc = frappe.get_doc("Maintenance Request", request_id)

    # ── Fetch asset_name from Asset doctype ───────────────────────
    asset_name = None
    if doc.asset:
        asset_name = frappe.db.get_value("Asset", doc.asset, "asset_name")

    # ── Status flags ──────────────────────────────────────────────
    is_submitted   = doc.docstatus == 1
    current_status = doc.status
    is_rejected    = current_status == "Rejected"

    # ── Fetch Maintenance Log ─────────────────────────────────────
    custom_quotation        = None
    quotation_grand_total   = None
    quotation_modified      = None
    custom_quotation_status = None
    technician_name         = None
    technician_phone        = None
    technician_assigned_at  = None
    maintenance_status      = None
    log_modified            = None
    log_quotation_status    = None

    # ── Status change dates from Version history ──────────────────
    work_in_progress_at  = None
    work_completed_at    = None
    payment_cleared_at   = None
    quotation_issued_at  = None
    technician_set_at    = None

    if doc.maintenance_log:
        log = frappe.db.get_value(
            "Asset Maintenance Log",
            doc.maintenance_log,
            [
                "custom_quotation",
                "custom_assign_to",
                "assign_to_name",
                "modified",
                "maintenance_status",
                "custom_quotation_status",
            ],
            as_dict=True,
        )

        if log:
            maintenance_status   = log.get("maintenance_status")
            log_modified         = log.get("modified")
            log_quotation_status = log.get("custom_quotation_status")

            # ── Fetch status change dates from Version history ────
            # When maintenance_status changed to "Planned" (work started)
            work_in_progress_at = get_field_change_date(
                "Asset Maintenance Log",
                doc.maintenance_log,
                "maintenance_status",
                "Planned",
            )

            # When maintenance_status changed to "Completed"
            work_completed_at = get_field_change_date(
                "Asset Maintenance Log",
                doc.maintenance_log,
                "maintenance_status",
                "Completed",
            )

            # When custom_quotation_status changed to "Paid"
            payment_cleared_at = get_field_change_date(
                "Asset Maintenance Log",
                doc.maintenance_log,
                "custom_quotation_status",
                "Paid",
            )

            # When custom_quotation was first set (Quotation issued)
            quotation_issued_at = get_field_change_date(
                "Asset Maintenance Log",
                doc.maintenance_log,
                "custom_quotation_status",
                "Quotation issued",
            )

            # When custom_assign_to was first set (Technician assigned)
            if log.get("custom_assign_to"):
                technician_set_at = get_field_change_date(
                    "Asset Maintenance Log",
                    doc.maintenance_log,
                    "custom_assign_to",
                    log["custom_assign_to"],
                )

            # ── Quotation details ─────────────────────────────────
            if log.get("custom_quotation"):
                custom_quotation = log["custom_quotation"]

                quotation_data = frappe.db.get_value(
                    "Quotation",
                    custom_quotation,
                    ["grand_total", "modified", "custom_quotation_status"],
                    as_dict=True,
                )
                if quotation_data:
                    quotation_grand_total   = quotation_data.get("grand_total")
                    quotation_modified      = quotation_data.get("modified")
                    custom_quotation_status = quotation_data.get("custom_quotation_status")

            # ── Technician details from User doctype ──────────────
            if log.get("custom_assign_to"):
                technician_name        = log.get("assign_to_name") or log.get("custom_assign_to")
                technician_assigned_at = technician_set_at or log.get("modified")

                user_data = frappe.db.get_value(
                    "User",
                    log["custom_assign_to"],
                    ["phone", "full_name"],
                    as_dict=True,
                )
                if user_data:
                    technician_phone = user_data.get("phone")
                    technician_name  = user_data.get("full_name") or technician_name

    # ── Quotation approval flags ──────────────────────────────────
    quotation_approved = custom_quotation_status == "Approved"
    quotation_rejected = custom_quotation_status == "Rejected"

    # ── Work status flags ─────────────────────────────────────────
    work_in_progress = bool(
        maintenance_status and
        maintenance_status not in ["Completed", "Cancelled"]
    )
    work_completed  = maintenance_status == "Completed"
    payment_cleared = log_quotation_status == "Paid"

    # ── Status Timeline ───────────────────────────────────────────
    statuses = [

        # ── Step 1: REQUEST_SUBMITTED ─────────────────────────────
        {
            "code":        "REQUEST_SUBMITTED",
            "title":       "Request Submitted",
            "completed":   is_submitted,
            "completedAt": str(doc.date_of_submit) if doc.date_of_submit else None,
            "details": {
                "remarks": "Request submitted by customer"
            }
        },

        # ── Step 2: UNDER_REVIEW ──────────────────────────────────
        {
            "code":        "UNDER_REVIEW",
            "title":       "Under Review",
            "completed":   not is_rejected,
            "completedAt": str(doc.custom_status_changed_date) if not is_rejected and doc.custom_status_changed_date else None,
            "details": {
                "reviewedBy": "Maintenance Team",
                "remarks":    "Request verified" if not is_rejected else "Request rejected"
            }
        },

        # ── Step 3: QUOTATION_ISSUED ──────────────────────────────
        {
            "code":        "QUOTATION_ISSUED",
            "title":       "Quotation Issued",
            "completed":   bool(custom_quotation),
            "completedAt": quotation_issued_at or (str(quotation_modified) if quotation_modified else None),
            "details": {
                "quotationNo": custom_quotation,
                "amount":      quotation_grand_total,
                "remarks":     "Quotation issued to customer" if custom_quotation else "Quotation not yet issued"
            }
        },

        # ── Step 4: QUOTATION_APPROVED ────────────────────────────
        {
            "code":        "QUOTATION_APPROVED",
            "title":       "Quotation Approved" if not quotation_rejected else "Quotation Rejected",
            "completed":   quotation_approved,
            "completedAt": str(quotation_modified) if quotation_approved and quotation_modified else None,
            "details": {
                "approvedBy": "Customer",
                "status":     custom_quotation_status or "Pending",
                "remarks":    "Quotation approved by customer" if quotation_approved
                              else ("Quotation rejected by customer" if quotation_rejected
                              else "Awaiting customer approval")
            }
        },

        # ── Step 5: TECHNICIAN_ASSIGNED ───────────────────────────
        {
            "code":        "TECHNICIAN_ASSIGNED",
            "title":       "Technician Assigned",
            "completed":   bool(technician_name),
            "completedAt": str(technician_assigned_at) if technician_assigned_at and technician_name else None,
            "details": {
                "technicianName": technician_name,
                "contactNumber":  technician_phone,
                "remarks":        "Technician assigned for maintenance" if technician_name else "Technician not yet assigned"
            }
        },

        # ── Step 6: WORK_IN_PROGRESS ──────────────────────────────
        {
            "code":        "WORK_IN_PROGRESS",
            "title":       "Work In Progress",
            "completed":   work_in_progress,
            "completedAt": work_in_progress_at or (str(log_modified) if work_in_progress and log_modified else None),
            "details": {
                "maintenanceStatus": maintenance_status,
                "remarks":           "Inspection ongoing" if work_in_progress else "Work not yet started"
            }
        },

        # ── Step 7: WORK_COMPLETED ────────────────────────────────
        {
            "code":        "WORK_COMPLETED",
            "title":       "Work Completed",
            "completed":   work_completed,
            "completedAt": work_completed_at or (str(log_modified) if work_completed and log_modified else None),
            "details": {
                "remarks": "Maintenance work completed successfully" if work_completed else "Work pending completion"
            }
        },

        # ── Step 8: PAYMENT_CLEARED ───────────────────────────────
        {
            "code":        "PAYMENT_CLEARED",
            "title":       "Payment Cleared",
            "completed":   payment_cleared,
            "completedAt": payment_cleared_at or (str(log_modified) if payment_cleared and log_modified else None),
            "details": {
                "remarks": "Payment cleared successfully" if payment_cleared else "Payment pending"
            }
        },
    ]

    return {
        "success": True,
        "data": {
            "requestId":   doc.name,
            "title":       doc.description,
            "requestType": doc.maintenance_type,
            "requestDate": str(doc.date_of_submit) if doc.date_of_submit else None,
            "assetName":   asset_name,
            "statuses":    statuses,
        }
    }