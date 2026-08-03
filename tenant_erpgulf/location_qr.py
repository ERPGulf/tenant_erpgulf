import io
import os
from base64 import b64encode

import frappe
from frappe import _
from pyqrcode import create as qr_create   # match whatever import your employee.py uses

def create_location_qr(doc, method=None, scale=8):
    """Create QR Code after inserting Location. QR contains the location id."""

    if not hasattr(doc, "custom_location_qr"):
        return

    fields = frappe.get_meta("Location").fields

    for field in fields:
        if field.fieldname == "custom_location_qr" and field.fieldtype == "Attach Image":

            if not doc.name:
                frappe.throw(_("Location id missing in the document"))

            base64_string = b64encode(doc.name.encode()).decode()

            qr_image = io.BytesIO()
            qr = qr_create(base64_string, error="L")
            qr.png(qr_image, scale=scale, quiet_zone=1)

            filename = f"QR-CODE-{doc.name}.png".replace(os.path.sep, "__")

            _file = frappe.get_doc({
                "doctype": "File",
                "file_name": filename,
                "content": qr_image.getvalue(),
                "is_private": 0,
                "attached_to_doctype": "Location",
                "attached_to_name": doc.name,
                "attached_to_field": "custom_location_qr",
            })
            _file.save()

            doc.db_set("custom_location_qr", _file.file_url)
            doc.notify_update()

            break
# def create_location_qr(doc, method=None):
#     """Create QR Code after inserting Location. QR contains the location id."""

#     if not hasattr(doc, "custom_location_qr"):
#         return

#     fields = frappe.get_meta("Location").fields

#     for field in fields:
#         if field.fieldname == "custom_location_qr" and field.fieldtype == "Attach Image":

#             if not doc.name:
#                 frappe.throw(_("Location id missing in the document"))

#             # payload = just the location id, matching what
#             # get_location_full_details expects as location_name
#             base64_string = b64encode(doc.name.encode()).decode()

#             qr_image = io.BytesIO()
#             qr = qr_create(base64_string, error="L")
#             qr.png(qr_image, scale=8, quiet_zone=1)

#             filename = f"QR-CODE-{doc.name}.png".replace(os.path.sep, "__")

#             _file = frappe.get_doc({
#                 "doctype": "File",
#                 "file_name": filename,
#                 "content": qr_image.getvalue(),
#                 "is_private": 0,
#                 "attached_to_doctype": "Location",
#                 "attached_to_name": doc.name,
#                 "attached_to_field": "custom_location_qr",
#             })
#             _file.save()

#             doc.db_set("custom_location_qr", _file.file_url)
#             doc.notify_update()

#             break


# @frappe.whitelist()
# def backfill_qr_for_existing_locations():
#     """Run once to generate QR codes for Locations created before this
#     feature existed. Skips ones that already have a QR."""
#     locations = frappe.get_all(
#         "Location",
#         filters={"custom_location_qr": ["in", ["", None]]},
#         pluck="name",
#     )

#     for loc in locations:
#         location_doc = frappe.get_doc("Location", loc)
#         create_location_qr(location_doc)
    
#     return {"status": "success", "count": len(locations), "locations": locations}
@frappe.whitelist()
def backfill_qr_for_existing_locations(scale=8):
    """Generate/regenerate QR for ALL Locations."""
    locations = frappe.get_all("Location", pluck="name")

    for loc in locations:
        create_location_qr(frappe.get_doc("Location", loc), scale=scale)

    frappe.db.commit()
    return {"status": "success", "count": len(locations), "locations": locations}