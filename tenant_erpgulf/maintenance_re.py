import frappe
from frappe import _


@frappe.whitelist()
def create_maintenance_log_from_request(maintenance_request):
    """
    Creates an Asset Maintenance Log from a Maintenance Request.
    Auto-fills fields and stores the log link back in the request.

    Field Mappings:
      Maintenance Request → Asset Maintenance Log
      ─────────────────────────────────────────────────────────────
      asset               → asset
      maintenance_type    → custom_maintenance_types   (e.g. "Preventive Maintenance")
      customer            → (used for reference / remarks)
      description         → description
      flat                → (stored in remarks)
      room                → (stored in remarks)
      location            → (stored in remarks)
      ── Fixed values ──
      custom_asset_maintenance_type → "Reactive"   (always set)
      maintenance_status            → "Planned"    (default)
    """

    # ── Fetch the Maintenance Request ─────────────────────────────
    mr = frappe.get_doc("Maintenance Request", maintenance_request)

    if mr.docstatus != 1:
        frappe.throw(_("Maintenance Request must be submitted before creating a Maintenance Log."))

    if mr.status != "Under Process":
        frappe.throw(_("Maintenance Log can only be created when status is 'Under Process'."))

    if mr.maintenance_log:
        frappe.throw(
            _("A Maintenance Log ({0}) already exists for this request.").format(mr.custom_maintenance_log)
        )

    # ── Fetch the Asset Maintenance record for this asset ─────────
    # Asset Maintenance Log requires a parent "Asset Maintenance" record
    

    

    # ── Build remarks from request details ────────────────────────
    

    # ── Create the Asset Maintenance Log ──────────────────────────
    log = frappe.new_doc("Asset Maintenance Log")
    log.custom_asset                      = mr.asset
    log.custom_maintenance_types   = mr.maintenance_type        # "Preventive Maintenance"
    log.custom_asset_maintenance_type = "Reactive"              # always "Reactive"                  # back-link (optional custom field)

    log.insert(ignore_permissions=False)
    frappe.db.commit()

    # ── Store the Maintenance Log link back in Maintenance Request ─
    frappe.db.set_value(
        "Maintenance Request",
        mr.name,
        "maintenance_log",
        log.name,
        update_modified=True
    )
    frappe.db.commit()

    return {
        "success": True,
        "maintenance_log": log.name
    }