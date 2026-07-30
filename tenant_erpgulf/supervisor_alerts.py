# your_app/supervisor_alerts.py
import frappe

@frappe.whitelist()
def add_supervisor_alert(asset_maintenance_log, title, description):
    doc = frappe.get_doc("Asset Maintenance Log", asset_maintenance_log)
    doc.append("custom_supervisor_alert", {
        "title": title,
        "description": description
    })
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success", "name": doc.name}