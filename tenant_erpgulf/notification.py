import frappe
from frappe.utils import getdate, nowdate, add_days


def auto_cancel_overdue_maintenance_logs():
    """Runs nightly via scheduler. Cancels maintenance logs where:
    1. The latest reschedule entry's date has already passed, or
    2. Quotation was Approved 3+ days ago and still isn't Paid.
    """
    _cancel_on_missed_reschedule()
    _cancel_on_unpaid_quotation()


def _cancel_on_missed_reschedule():
    logs = frappe.get_all(
        "Asset Maintenance Log",
        filters={"maintenance_status": ["not in", ["Completed", "Cancelled"]]},
        pluck="name",
    )
    for log_name in logs:
        doc = frappe.get_doc("Asset Maintenance Log", log_name)
        if not doc.custom_reschedule_history_table:
            continue

        third_row = next(
            (row for row in doc.custom_reschedule_history_table if row.idx == 3),
            None,
        )
        if not third_row:
            continue

        if third_row.scheduled_date and getdate(third_row.scheduled_date) < getdate(nowdate()):
            doc.maintenance_status = "Cancelled"
            doc.save(ignore_permissions=True)
            frappe.db.commit()


def _cancel_on_unpaid_quotation():
    logs = frappe.get_all(
        "Asset Maintenance Log",
        filters={
            "custom_quotation_status": "Quotation Approved",
            "maintenance_status": ["not in", ["Completed", "Cancelled"]],
            "custom_quotation_approved_on": ["<=", add_days(nowdate(), -3)],
        },
        pluck="name",
    )
    for log_name in logs:
        doc = frappe.get_doc("Asset Maintenance Log", log_name)
        doc.maintenance_status = "Cancelled"
        doc.save(ignore_permissions=True)
        frappe.db.commit()


@frappe.whitelist()
def run_auto_cancel_overdue_maintenance_logs():
    """Manual/API trigger:
    POST /api/method/tenant_erpgulf.tenant_erpgulf.tasks.run_auto_cancel_overdue_maintenance_logs
    """
    frappe.only_for(["System Manager", "Administrator"])
    auto_cancel_overdue_maintenance_logs()
    return {"status": "done"}