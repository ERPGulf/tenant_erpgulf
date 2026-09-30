import frappe
from frappe import _


@frappe.whitelist(allow_guest = False)
def update_customer_token(customer_id, token):
    if not customer_id or not token:
        frappe.throw(_("customer_id and token are required"))

    if not frappe.db.exists("Customer", customer_id):
        frappe.throw(_("Customer {0} not found").format(customer_id), frappe.DoesNotExistError)

    customer = frappe.get_doc("Customer", customer_id)
    customer.custom_token = token
    customer.save()  # checks the caller's write permission on Customer

    return {
        "status": "success",
        "customer_id": customer.name,
        "custom_token": customer.custom_token,
    }