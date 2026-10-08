import frappe
from frappe import _

LOG_DOCTYPE = "Asset Maintenance Log"
LOG_EMAIL_FIELD = "custom__customer_email"   # change if the real fieldname is custom_customer_email
LOG_TOKEN_FIELD = "custom_customer_token"


def get_customer_emails(customer_id):
    """Get every email that belongs to the customer (its primary email plus emails of linked Contacts)."""
    emails = set()

    primary = frappe.db.get_value("Customer", customer_id, "email_id")
    if primary:
        emails.add(primary.strip().lower())

    contact_names = frappe.get_all(
        "Dynamic Link",
        filters={"link_doctype": "Customer", "link_name": customer_id, "parenttype": "Contact"},
        pluck="parent",
    )
    if contact_names:
        for email in frappe.get_all(
            "Contact Email",
            filters={"parenttype": "Contact", "parent": ["in", contact_names]},
            pluck="email_id",
        ):
            if email:
                emails.add(email.strip().lower())

    return emails


def _set_log_token(log_name, token):
    """Write the token on one Asset Maintenance Log after a permission check."""
    if not frappe.has_permission(LOG_DOCTYPE, "write", log_name):
        frappe.throw(
            _("Not permitted to update {0} {1}").format(LOG_DOCTYPE, log_name),
            frappe.PermissionError,
        )
    # set_value also works on submitted logs, where save() would fail
    frappe.db.set_value(LOG_DOCTYPE, log_name, LOG_TOKEN_FIELD, token)


@frappe.whitelist(allow_guest=False)
def update_customer_token(customer_id, token):
    """
    Store the FCM token on the Customer and on every Asset Maintenance Log
    whose customer email belongs to this customer.

    Args:
        customer_id : Customer name
        token       : FCM registration token from the mobile app
    """
    customer_id = (customer_id or "").strip()
    # Remove spaces, line breaks and stray quotes, which make FCM reject the token
    token = (token or "").strip().strip('"').strip("'")

    if not customer_id or not token:
        frappe.throw(_("customer_id and token are required"))

    if any(ch.isspace() for ch in token):
        frappe.throw(_("Token must not contain spaces or line breaks"))

    if not frappe.db.exists("Customer", customer_id):
        frappe.throw(_("Customer {0} not found").format(customer_id), frappe.DoesNotExistError)

    # 1. Update the Customer
    customer = frappe.get_doc("Customer", customer_id)
    customer.custom_token = token
    customer.save()  # checks the caller's write permission on Customer

    # 2. Update every log whose email belongs to this customer
    updated_logs = []
    customer_emails = get_customer_emails(customer_id)

    if customer_emails:
        logs = frappe.get_all(
            LOG_DOCTYPE,
            filters={LOG_EMAIL_FIELD: ["is", "set"]},
            fields=["name", LOG_EMAIL_FIELD],
        )
        for log in logs:
            if (log.get(LOG_EMAIL_FIELD) or "").strip().lower() in customer_emails:
                _set_log_token(log.name, token)
                updated_logs.append(log.name)

    frappe.db.commit()

    return {
        "status": "success",
        "customer_id": customer.name,
        "custom_token": customer.custom_token,
        "customer_emails": sorted(customer_emails),
        "updated_maintenance_logs": updated_logs,
    }