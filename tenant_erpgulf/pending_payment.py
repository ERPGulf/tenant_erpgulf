import frappe
from frappe import _
from frappe.utils import flt
 
 
@frappe.whitelist()
def get_unpaid_maintenance_summary(customer_id):
    """
    Return the count and total amount of "unpaid" Maintenance Requests
    for a given customer.
 
    A Maintenance Request counts as unpaid when:
      - its linked Asset Maintenance Log (maintenance_log) has
        custom_quotation_status == "Quotation approved", AND
      - that log has a custom_quotation set.
 
    The unpaid amount is the grand_total of that Quotation.
    """
    if not customer_id:
        frappe.throw(_("customer_id is required"))
 
    maintenance_requests = frappe.get_all(
        "Maintenance Request",
        filters={
            "customer": customer_id,
            "maintenance_log": ["is", "set"],
        },
        fields=["name", "maintenance_log", "status"],
    )
 
    unpaid_count = 0
    unpaid_amount = 0.0
    unpaid_requests = []
 
    for mr in maintenance_requests:
        log_name = mr.get("maintenance_log")
 
        if not log_name or not frappe.db.exists("Asset Maintenance Log", log_name):
            continue
 
        quotation_status, quotation_name = frappe.db.get_value(
            "Asset Maintenance Log",
            log_name,
            ["custom_quotation_status", "custom_quotation"],
        )
 
        if quotation_status != "Quotation approved" or not quotation_name:
            continue
 
        if not frappe.db.exists("Quotation", quotation_name):
            continue
 
        grand_total = flt(frappe.db.get_value("Quotation", quotation_name, "grand_total"))
 
        unpaid_count += 1
        unpaid_amount += grand_total
        unpaid_requests.append(
            {
                "maintenance_request": mr["name"],
                "maintenance_log": log_name,
                "quotation": quotation_name,
                "amount": grand_total,
            }
        )
 
    return {
        "customer": customer_id,
        "unpaid_count": unpaid_count,
        "unpaid_amount": unpaid_amount,
    }
 