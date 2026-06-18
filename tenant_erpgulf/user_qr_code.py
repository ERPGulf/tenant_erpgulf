# import frappe
# from frappe import _
# import base64
# from base64 import b64encode
# import io
# import os
# from pyqrcode import create as qr_create


# def create_qr_code(doc, method):
#     """Create QR Code after inserting Customer"""
#     if not hasattr(doc, 'custom_qr_code'):
#         return

#     fields = frappe.get_meta('Customer').fields
#     auth_client_name = frappe.db.get_value("OAuth Client", {}, "name")
#     if auth_client_name:
#         auth_client = frappe.get_doc("OAuth Client", auth_client_name)
#     else:
#         frappe.throw("No OAuth Client found")

#     app_name = auth_client.app_name
#     if not app_name:
#         frappe.throw(_('App name missing in OAuth Client'))
#     client_secret = auth_client.client_secret  
#     app_key = base64.b64encode(app_name.encode()).decode("utf-8")
    

#     for field in fields:
#         if field.fieldname == 'custom_qr_code' and field.fieldtype == 'Attach Image':

#             if not doc.name:
#                 frappe.throw(_('Customer ID missing in the document'))

#             if not doc.customer_name:
#                 frappe.throw(_('Customer name missing in the document'))

#             if not doc.customer_type:
#                 frappe.throw(_('Customer type missing for {} in the document'.format(doc.name)))

#             if not doc.customer_group:
#                 frappe.throw(_('Customer group missing for {} in the document'.format(doc.name)))

#             if not doc.territory:
#                 frappe.throw(_('Territory missing for {} in the document'.format(doc.name)))

#             if not frappe.local.conf.host_name:
#                 frappe.throw(_('API URL (host_name) is missing in site config'))

#             if not app_key:
#                 frappe.throw(_('App key could not be generated'))

#             cleaned = (
#                 f"Customer_ID: {doc.name}"
#                 f" Customer_Name: {doc.customer_name}"
#                 f" Customer_Type: {doc.customer_type}"
#                 f" Customer_Group: {doc.customer_group}"
#                 f" Territory: {doc.territory}"
#                 f" API: {frappe.local.conf.host_name}"
#                 f" App_key: {app_key}"
#                 f" Client_Secret: {client_secret}"
#             )

#             base64_string = b64encode(cleaned.encode()).decode()

#             qr_image = io.BytesIO()
#             url = qr_create(base64_string, error='L')
#             url.png(qr_image, scale=2, quiet_zone=1)

#             filename = f"QR-CODE-{doc.name}.png".replace(os.path.sep, "__")
#             _file = frappe.get_doc({
#                 "doctype": "File",
#                 "file_name": filename,
#                 "content": qr_image.getvalue(),
#                 "is_private": 0
#             })

#             _file.save()

#             doc.db_set('image', _file.file_url)
#             doc.notify_update()

#             break
import frappe
from frappe import _
import base64
from base64 import b64encode
import io
import os
import json
from pyqrcode import create as qr_create
from werkzeug.wrappers import Response


def create_qr_code(doc, method):
    """Create or Update QR Code when Customer is inserted or updated"""
    if not hasattr(doc, 'custom_qr_code'):
        return

    fields = frappe.get_meta('Customer').fields
    auth_client_name = frappe.db.get_value("OAuth Client", {}, "name")
    if auth_client_name:
        auth_client = frappe.get_doc("OAuth Client", auth_client_name)
    else:
        frappe.throw("No OAuth Client found")

    app_name = auth_client.app_name
    if not app_name:
        frappe.throw(_('App name missing in OAuth Client'))

    client_secret = auth_client.client_secret
    if not client_secret:
        frappe.throw(_('Client secret missing in OAuth Client'))

    app_key = base64.b64encode(app_name.encode()).decode("utf-8")

    for field in fields:
        if field.fieldname == 'custom_qr_code' and field.fieldtype == 'Attach Image':

            if not doc.name:
                frappe.throw(_('Customer ID missing in the document'))
            if not doc.customer_name:
                frappe.throw(_('Customer name missing in the document'))
            if not doc.customer_type:
                frappe.throw(_('Customer type missing for {} in the document'.format(doc.name)))
            if not doc.customer_group:
                frappe.throw(_('Customer group missing for {} in the document'.format(doc.name)))
            if not doc.territory:
                frappe.throw(_('Territory missing for {} in the document'.format(doc.name)))
            if not frappe.local.conf.host_name:
                frappe.throw(_('API URL (host_name) is missing in site config'))
            if not app_key:
                frappe.throw(_('App key could not be generated'))

            # ── DELETE OLD QR FILE IF EXISTS ──────────────────────────────────
            old_qr_url = frappe.db.get_value("Customer", doc.name, "custom_qr_code")
            if old_qr_url:
                old_file = frappe.db.get_value("File", {"file_url": old_qr_url}, "name")
                if old_file:
                    frappe.delete_doc("File", old_file, ignore_permissions=True)
            # ─────────────────────────────────────────────────────────────────

            cleaned = (
                f"Customer_ID: {doc.name}"
                f" Customer_Name: {doc.customer_name}"
                f" Customer_Type: {doc.customer_type}"
                f" Customer_Group: {doc.customer_group}"
                f" Territory: {doc.territory}"
                f" API: {frappe.local.conf.host_name}"
                f" App_key: {app_key}"
                f" Client_Secret: {client_secret}"
            )

            base64_string = b64encode(cleaned.encode()).decode()

            qr_image = io.BytesIO()
            url = qr_create(base64_string, error='L')
            url.png(qr_image, scale=2, quiet_zone=1)

            filename = f"QR-CODE-{doc.name}.png".replace(os.path.sep, "__")
            _file = frappe.get_doc({
                "doctype": "File",
                "file_name": filename,
                "content": qr_image.getvalue(),
                "is_private": 0
            })
            _file.save()

            doc.db_set('custom_qr_code', _file.file_url)
            doc.db_set('image', _file.file_url)
            doc.notify_update()
            break


@frappe.whitelist(allow_guest=False)
def generate_customer_qr(customer_id):
    try:
        if not frappe.db.exists("Customer", customer_id):
            return Response(
                json.dumps({
                    "status": "error",
                    "message": f"Customer '{customer_id}' not found"
                }),
                status=404,
                mimetype="application/json"
            )

        doc = frappe.get_doc("Customer", customer_id)

        auth_client_name = frappe.db.get_value("OAuth Client", {}, "name")
        if not auth_client_name:
            return Response(
                json.dumps({"status": "error", "message": "No OAuth Client found"}),
                status=500,
                mimetype="application/json"
            )

        auth_client = frappe.get_doc("OAuth Client", auth_client_name)

        app_name = auth_client.app_name
        if not app_name:
            return Response(
                json.dumps({"status": "error", "message": "App name missing in OAuth Client"}),
                status=500,
                mimetype="application/json"
            )

        client_secret = auth_client.client_secret
        if not client_secret:
            return Response(
                json.dumps({"status": "error", "message": "Client secret missing in OAuth Client"}),
                status=500,
                mimetype="application/json"
            )

        host_name = frappe.local.conf.get("host_name")
        if not host_name:
            return Response(
                json.dumps({"status": "error", "message": "host_name missing in site config"}),
                status=500,
                mimetype="application/json"
            )

        app_key = base64.b64encode(app_name.encode()).decode("utf-8")

        # ── Delete old QR if exists ───────────────────────────────────────────
        old_qr_url = frappe.db.get_value("Customer", customer_id, "custom_qr_code")
        if old_qr_url:
            old_file = frappe.db.get_value("File", {"file_url": old_qr_url}, "name")
            if old_file:
                frappe.delete_doc("File", old_file, ignore_permissions=True)

        # ── Build QR content ──────────────────────────────────────────────────
        cleaned = (
            f"Customer_ID: {doc.name}"
            f" Customer_Name: {doc.customer_name}"
            f" Customer_Type: {doc.customer_type}"
            f" Customer_Group: {doc.customer_group}"
            f" Territory: {doc.territory}"
            f" API: {host_name}"
            f" App_key: {app_key}"
            f" Client_Secret: {client_secret}"
        )

        base64_string = b64encode(cleaned.encode()).decode()

        # ── Generate QR PNG ───────────────────────────────────────────────────
        qr_image = io.BytesIO()
        qr = qr_create(base64_string, error='L')
        qr.png(qr_image, scale=2, quiet_zone=1)

        # ── Fix filename: remove path sep AND spaces ──────────────────────────
        filename = f"QR-CODE-{doc.name}.png".replace(os.path.sep, "__").replace(" ", "-")

        _file = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": qr_image.getvalue(),
            "is_private": 0
        })
        _file.save()

        doc.db_set('custom_qr_code', _file.file_url)
        doc.notify_update()

        # ── Fix URL: remove trailing slash before joining ─────────────────────
        full_qr_url = f"{host_name.rstrip('/')}{_file.file_url}"

        # ── Return PNG image directly so Postman renders it ───────────────────
        qr_image.seek(0)
        return Response(
            qr_image.getvalue(),
            status=200,
            mimetype="image/png",
            headers={
                "Content-Disposition": f"inline; filename={filename}",
                "X-Customer-ID": doc.name,
                "X-Customer-Name": doc.customer_name,
                "X-QR-Code-URL": full_qr_url        # ← URL available in Headers tab
            }
        )

    except Exception as e:
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500,
            mimetype="application/json"
        )

# import frappe
# from frappe import _


# @frappe.whitelist(allow_guest=False)
# def get_customer_maintenance_data(customer_id):
#     """
#     API to get complete maintenance data for a customer.

#     Endpoint:
#       GET /api/method/your_app.api.customer_maintenance_api.get_customer_maintenance_data
#           ?customer_id=CUST-0001

#     Returns:
#       - flats  (Location doctype, filtered by custom_customer)
#           └── rooms  (custom_room_equipment child table rows)
#                   └── assets  (Asset doctype, location=flat.name & custom_room_name=room.room_name)
#       - maintenanceRequests  (with attachmentIds array)
#       - priorityOptions      (Select options from Maintenance Request meta)
#       - maintenanceTypes     (all rows from Maintenance Type doctype)
#     """

#     if not customer_id:
#         frappe.throw(_("customer_id is required"), frappe.MandatoryError)

#     # ─────────────────────────────────────────────────────────────
#     # 1.  FLATS  (Location doctype — custom_customer = customer_id)
#     # ─────────────────────────────────────────────────────────────

#     flat_docs = frappe.get_all(
#         "Location",
#         filters={"custom_customer": customer_id},
#         fields=[
#             "name",
#             "location_name",
#             "custom_flat_number",
#         ],
#     )

#     flats = []
#     for flat in flat_docs:
#         flat_name = flat["name"]  # e.g. "adc"

#         # ── Rooms from custom_room_equipment child table ──────────
#         rooms_raw = frappe.get_all(
#             "Room Equipment",
#             filters={"parent": flat_name, "parenttype": "Location"},
#             fields=["name", "room_name"],
#             order_by="idx asc",
#         )

#         rooms = []
#         for room in rooms_raw:
#             # ── Assets for this flat + room ───────────────────────
#             assets_raw = frappe.get_all(
#                 "Asset",
#                 filters={
#                     "location": flat_name,
#                     "custom_room_name": room["room_name"],
#                 },
#                 fields=[
#                     "name",
#                     "asset_name",
#                     "item_code",
#                     "custom_room_name",
#                 ],
#             )

#             rooms.append(
#                 {
#                     "roomId": room["name"],
#                     "roomName": room["room_name"],
#                     "assets": [
#                         {
#                             "assetId": a["name"],
#                             "assetName": a["asset_name"],
#                             "itemCode": a["item_code"],
#                         }
#                         for a in assets_raw
#                     ],
#                 }
#             )

#         flats.append(
#             {
#                 "flatId": flat_name,
#                 "locationName": flat["location_name"],
#                 "flatNumber": flat["custom_flat_number"],
#                 "rooms": rooms,
#             }
#         )

#     # ─────────────────────────────────────────────────────────────
#     # 2.  MAINTENANCE REQUESTS  (with attachments)
#     # ─────────────────────────────────────────────────────────────

#     mr_list = frappe.get_all(
#         "Maintenance Request",
#         filters={"customer": customer_id},
#         fields=[
#             "name",
#             "priority",
#             "maintenance_type",
#             "flat",
#             "room",
#             "asset",
#             "location",
#             "creation",
#             "modified",
#         ],
#         order_by="creation desc",
#     )

#     maintenance_requests = []
#     for req in mr_list:
#         # File attachments
#         attachments = frappe.get_all(
#             "File",
#             filters={
#                 "attached_to_doctype": "Maintenance Request",
#                 "attached_to_name": req["name"],
#             },
#             fields=["name", "file_name", "file_url", "file_size", "is_private"],
#         )

#         maintenance_requests.append(
#             {
#                 "name": req["name"],
#                 "priority": req.get("priority"),
#                 "maintenanceType": req.get("maintenance_type"),
#                 "flatId": req.get("flat"),
#                 "roomId": req.get("room"),
#                 "assetId": req.get("asset"),
#                 "location": req.get("location"),
#                 "createdAt": str(req["creation"]) if req.get("creation") else None,
#                 "updatedAt": str(req["modified"]) if req.get("modified") else None,
#                 "attachmentIds": [att["name"] for att in attachments],
#                 "attachments": [
#                     {
#                         "id": att["name"],
#                         "fileName": att["file_name"],
#                         "fileUrl": att["file_url"],
#                         "fileSize": att["file_size"],
#                         "isPrivate": bool(att["is_private"]),
#                     }
#                     for att in attachments
#                 ],
#             }
#         )

#     # ─────────────────────────────────────────────────────────────
#     # 3.  PRIORITY OPTIONS  (from Maintenance Request meta)
#     # ─────────────────────────────────────────────────────────────

#     priority_options = []
#     try:
#         meta = frappe.get_meta("Maintenance Request")
#         pf = meta.get_field("priority")
#         if pf and pf.fieldtype == "Select" and pf.options:
#             priority_options = [o.strip() for o in pf.options.split("\n") if o.strip()]
#     except Exception:
#         pass

#     # ─────────────────────────────────────────────────────────────
#     # 4.  MAINTENANCE TYPES  (Maintenance Type doctype)
#     # ─────────────────────────────────────────────────────────────

#     maintenance_types = []
#     try:
#         mt_list = frappe.get_all(
#             "Maintenance Type",
#             fields=["name", "maintenance_type_name", "description"],
#             order_by="name asc",
#         )
#         maintenance_types = [
#             {
#                 "id": mt["name"],
#                 "name": mt.get("maintenance_type_name") or mt["name"],
#                 "description": mt.get("description"),
#             }
#             for mt in mt_list
#         ]
#     except Exception:
#         pass

#     # ─────────────────────────────────────────────────────────────
#     # 5.  RESPONSE
#     # ─────────────────────────────────────────────────────────────

#     return {
#         "success": True,
#         "customerId": customer_id,
#         "flats": flats,
#         "maintenanceRequests": maintenance_requests,
#         "priorityOptions": priority_options,
#         "maintenanceTypes": maintenance_types,
#     }

import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def get_customer_maintenance_data(customer_id):

    if not customer_id:
        frappe.throw(_("customer_id is required"), frappe.MandatoryError)

    # ─────────────────────────────────────────────────────────────
    # 1.  FLATS → ROOMS → ASSETS
    # ─────────────────────────────────────────────────────────────

    flat_docs = frappe.get_all(
        "Location",
        filters={"custom_customer": customer_id},
        fields=["name", "location_name", "custom_flat_number"],
    )

    flats = []
    for flat in flat_docs:
        flat_name = flat["name"]

        rooms_raw = frappe.get_all(
            "Room Equipment",
            filters={"parent": flat_name, "parenttype": "Location"},
            fields=["name", "room_name"],
            order_by="idx asc",
        )

        rooms = []
        for room in rooms_raw:
            assets_raw = frappe.get_all(
                "Asset",
                filters={
                    "location": flat_name,
                    "custom_room_name": room["room_name"],
                },
                fields=["name", "asset_name", "item_code"],
            )

            rooms.append(
                {
                    "roomId": room["name"],
                    "roomName": room["room_name"],
                    "assets": [
                        {
                            "assetId": a["name"],
                            "assetName": a["asset_name"],
                            "itemCode": a["item_code"],
                        }
                        for a in assets_raw
                    ],
                }
            )

        flats.append(
            {
                "flatId": flat_name,
                "locationName": flat["location_name"],
                "flatNumber": flat["custom_flat_number"],
                "rooms": rooms,
            }
        )

    # ─────────────────────────────────────────────────────────────
    # 2.  ALL ATTACHMENTS — flat array of every file across all MRs
    # ─────────────────────────────────────────────────────────────

    # mr_list = frappe.get_all(
    #     "Maintenance Request",
    #     filters={"customer": customer_id},
    #     fields=["name"],
    # )

    # mr_names = [r["name"] for r in mr_list]

    # all_attachments = []
    # if mr_names:
    #     all_attachments_raw = frappe.get_all(
    #         "File",
    #         filters={
    #             "attached_to_doctype": "Maintenance Request",
    #             "attached_to_name": ["in", mr_names],
    #         },
    #         fields=[
    #             "name",
    #             "file_name",
    #             "file_url",
    #         ],
    #         order_by="creation desc",
    #     )

    #     all_attachments = [
    #         {
    #             "id": att["name"],
    #             "fileName": att["file_name"],
    #             "fileUrl": att["file_url"],
                
    #         }
    #         for att in all_attachments_raw
    #     ]

    # ─────────────────────────────────────────────────────────────
    # 3.  PRIORITY OPTIONS — from Maintenance Request Select field
    # ─────────────────────────────────────────────────────────────

    priority_options = []
    try:
        meta = frappe.get_meta("Maintenance Request")
        pf = meta.get_field("priority")
        if pf and pf.fieldtype == "Select" and pf.options:
            priority_options = [o.strip() for o in pf.options.split("\n") if o.strip()]
    except Exception:
        pass

    # ─────────────────────────────────────────────────────────────
    # 4.  MAINTENANCE TYPES — from Maintenance Type doctype
    # ─────────────────────────────────────────────────────────────

    maintenance_types = []
    try:
        mt_list = frappe.get_all(
            "Maintenance Type",
            fields=["name"],
            order_by="name asc",
        )
        maintenance_types = [mt["name"] for mt in mt_list]
    except Exception:
        pass

    # ─────────────────────────────────────────────────────────────
    # 5.  RESPONSE
    # ─────────────────────────────────────────────────────────────

    return {
        "success": True,
        "customerId": customer_id,
        "flats": flats,
        "priorityOptions": priority_options,
        "maintenanceTypes": maintenance_types,
    }
import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def create_maintenance_request(
    customer,
    priority,
    maintenance_type,
    flat,
    room,
    asset,
    location,
    description,
    phone_number,
):
    """
    POST API to create a Maintenance Request with multiple file uploads.

    Send as form-data:
      customer          → test customer
      priority          → High
      maintenance_type  → Preventive Maintenance
      flat              → 203
      room              → Master Bed Room
      asset             → ACC-ASS-2026-00003
      location          → adc
      description       → abc
      phone_number      → 8281693215
      attachment_ids    → file1.jpg   (File type — select multiple files)
      attachment_ids    → file2.jpg   (add same key again for multiple)
    """

    # ── Validate required fields ──────────────────────────────────
    required = {
        "customer":         customer,
        "priority":         priority,
        "maintenance_type": maintenance_type,
        "flat":             flat,
        "room":             room,
        "asset":            asset,
        "location":         location,
        "description":      description,
        "phone_number":     phone_number,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        frappe.throw(
            _("Missing required fields: {0}").format(", ".join(missing)),
            frappe.MandatoryError,
        )

    # ── Create the Maintenance Request doc ────────────────────────
    doc = frappe.new_doc("Maintenance Request")
    doc.customer         = customer
    doc.priority         = priority
    doc.maintenance_type = maintenance_type
    doc.flat             = flat
    doc.room             = room
    doc.asset            = asset
    doc.location         = location
    doc.description      = description
    doc.phone_number     = phone_number

    doc.insert(ignore_permissions=False)
    frappe.db.commit()

    # ── Collect all uploaded files from multipart form-data ───────
    # Werkzeug (used by Frappe) stores multiple files with same key
    # in request.files.getlist(key) — handles both single and multiple
    all_file_objects = []

    raw_files = frappe.request.files
    if raw_files:
        # getlist returns all files for a given field name
        # Try common field names, then fall back to all keys
        for key in raw_files.keys():
            file_list = raw_files.getlist(key)
            for f in file_list:
                if f and f.filename:
                    all_file_objects.append(f)

    # ── Save each file and attach to the Maintenance Request ──────
    for file_obj in all_file_objects:
        file_content = file_obj.read()
        file_name    = file_obj.filename

        if not file_content:
            continue

        saved_file = frappe.get_doc(
            {
                "doctype":             "File",
                "file_name":           file_name,
                "attached_to_doctype": "Maintenance Request",
                "attached_to_name":    doc.name,
                "attached_to_field":   None,
                "is_private":          1,
                "content":             file_content,
            }
        )
        saved_file.insert(ignore_permissions=True)

    if all_file_objects:
        frappe.db.commit()

    # ── Fetch all attached files with full paths ──────────────────
    attachments_raw = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Maintenance Request",
            "attached_to_name":    doc.name,
        },
        fields=[
            "name",
            "file_name",
            "file_url",
            "file_size",
            "is_private",
            "creation",
        ],
        order_by="creation asc",
    )

    site_url = frappe.utils.get_url()

    attachments = []
    for att in attachments_raw:
        if att["file_url"]:
            full_url = (
                att["file_url"]
                if att["file_url"].startswith("http")
                else site_url + att["file_url"]
            )
        else:
            full_url = None

        attachments.append(
            {
                "id":         att["name"],
                "fileName":   att["file_name"],
                "fileUrl":    att["file_url"],
                "fullUrl":    full_url,
                "fileSize":   att["file_size"],
                "isPrivate":  bool(att["is_private"]),
                "uploadedAt": str(att["creation"]) if att.get("creation") else None,
            }
        )

    # ── Return full response ──────────────────────────────────────
    return {
        "success": True,
        "message": "Maintenance Request created successfully",
        "data": {
            "name":            doc.name,
            "customer":        doc.customer,
            "priority":        doc.priority,
            "maintenanceType": doc.maintenance_type,
            "flat":            doc.flat,
            "room":            doc.room,
            "asset":           doc.asset,
            "location":        doc.location,
            "description":     doc.description,
            "phoneNumber":     doc.phone_number,
            "status":          doc.docstatus,
            "createdAt":       str(doc.creation),
            "updatedAt":       str(doc.modified),
            "attachmentCount": len(attachments),
            "attachments":     attachments,
        },
    }

# import frappe
# from frappe import _


# @frappe.whitelist(allow_guest=False)
# def get_asset_maintenance_logs(customer_id, status="All"):

#     if not customer_id:
#         frappe.throw(_("customer_id is required"), frappe.MandatoryError)

#     # ── Step 1: Get all Location names for this customer ──────────
#     locations = frappe.get_all(
#         "Location",
#         filters={"custom_customer": customer_id},
#         fields=["name"],
#     )
#     location_names = [l["name"] for l in locations]

#     if not location_names:
#         return _empty_response(customer_id, status)

#     # ── Step 2: Get all Asset IDs in those locations ──────────────
#     all_assets = frappe.get_all(
#         "Asset",
#         filters={"location": ["in", location_names]},
#         fields=["name"],
#     )
#     asset_ids = [a["name"] for a in all_assets]

#     if not asset_ids:
#         return _empty_response(customer_id, status)

#     # ─────────────────────────────────────────────────────────────
#     # PATH A — Reactive
#     # assetId = custom_asset (directly available)
#     # ─────────────────────────────────────────────────────────────
#     reactive_filters = {
#         "docstatus": ["in", [0, 1]],
#         "custom_asset_maintenance_type": "Reactive",
#         "custom_asset": ["in", asset_ids],
#     }
#     if status.lower() == "open":
#         reactive_filters["maintenance_status"] = ["in", ["Planned", "Overdue"]]

#     reactive_logs = frappe.get_all(
#         "Asset Maintenance Log",
#         filters=reactive_filters,
#         fields=_log_fields(),
#         order_by="creation desc",
#     )

#     # ─────────────────────────────────────────────────────────────
#     # PATH B — Planned
#     # assetId = Asset Maintenance.asset_name (Asset ID stored there)
#     # Build a map: AM name → asset_name (Asset ID) for lookup later
#     # ─────────────────────────────────────────────────────────────
#     am_records = frappe.get_all(
#         "Asset Maintenance",
#         filters={"asset_name": ["in", asset_ids]},
#         fields=["name", "asset_name"],
#     )
#     # map: AM doc name → Asset ID
#     am_to_asset_id = {am["name"]: am["asset_name"] for am in am_records}
#     am_names = list(am_to_asset_id.keys())

#     planned_logs = []
#     if am_names:
#         planned_filters = {
#             "docstatus": ["in", [0, 1]],
#             "custom_asset_maintenance_type": "Planned",
#             "asset_name": ["in", am_names],
#         }
#         if status.lower() == "open":
#             planned_filters["maintenance_status"] = ["in", ["Planned", "Overdue"]]

#         planned_logs = frappe.get_all(
#             "Asset Maintenance Log",
#             filters=planned_filters,
#             fields=_log_fields(),
#             order_by="creation desc",
#         )

#     # ── Merge + deduplicate ───────────────────────────────────────
#     seen = set()
#     combined_logs = []
#     for log in reactive_logs + planned_logs:
#         if log["name"] not in seen:
#             seen.add(log["name"])
#             combined_logs.append(log)

#     combined_logs.sort(key=lambda x: str(x.get("creation") or ""), reverse=True)

#     # ── Build final response ──────────────────────────────────────
#     logs = []
#     for log in combined_logs:
#         # Reactive → assetId from custom_asset
#         # Planned  → assetId from Asset Maintenance.asset_name via am_to_asset_id map
#         if log.get("custom_asset_maintenance_type") == "Reactive":
#             asset_id = log.get("custom_asset")
#         else:
#             asset_id = am_to_asset_id.get(log.get("asset_name"))

#         items_raw = frappe.get_all(
#             "Stock Items For Asset",
#             filters={"parent": log["name"], "parenttype": "Asset Maintenance Log"},
#             fields=[
#                 "name",
#                 "item_code",
#                 "qty",
#                 "uom",
#                 "stock_uom",
#                 "conversion_factor",
#                 "s_warehouse",
#             ],
#             order_by="idx asc",
#         )

#         logs.append(
#             {
#                 "name":                  log["name"],
#                 "assetName":             log["asset_name"],
#                 "assetId":               asset_id,            # ← correct for both paths
#                 "itemCode":              log["item_code"],
#                 "itemName":              log["item_name"],
#                 "taskName":              log["task_name"],
#                 "maintenanceStatus":     log["maintenance_status"],
#                 "maintenanceType":       log["maintenance_type"],
#                 "customMaintenanceType": log["custom_maintenance_types"],
#                 "assetMaintenanceType":  log["custom_asset_maintenance_type"],
#                 "assignTo":              log["custom_assign_to"],
#                 "assignToName":          log["assign_to_name"],
#                 "periodicity":           log["periodicity"],
#                 "completionDate":        str(log["completion_date"]) if log.get("completion_date") else None,
#                 "hasCertificate":        bool(log["has_certificate"]),
#                 "description":           log["description"],
#                 "docStatus":             log["docstatus"],
#                 "createdAt":             str(log["creation"]) if log.get("creation") else None,
#                 "updatedAt":             str(log["modified"]) if log.get("modified") else None,
#                 "stockItems": [
#                     {
#                         "id":               item["name"],
#                         "itemCode":         item["item_code"],
#                         "qty":              item["qty"],
#                         "uom":              item["uom"],
#                         "stockUom":         item["stock_uom"],
#                         "conversionFactor": item["conversion_factor"],
#                         "warehouse":        item["s_warehouse"],
#                     }
#                     for item in items_raw
#                 ],
#             }
#         )

#     return {
#         "success":    True,
#         "customerId": customer_id,
#         "status":     status,
#         "count":      len(logs),
#         "logs":       logs,
#     }


# def _log_fields():
#     return [
#         "name",
#         "asset_name",
#         "item_code",
#         "item_name",
#         "task_name",
#         "maintenance_status",
#         "maintenance_type",
#         "custom_maintenance_types",
#         "custom_asset",
#         "custom_asset_maintenance_type",
#         "custom_assign_to",
#         "assign_to_name",
#         "periodicity",
#         "completion_date",
#         "has_certificate",
#         "description",
#         "docstatus",
#         "creation",
#         "modified",
#     ]


# def _empty_response(customer_id, status):
#     return {
#         "success":    True,
#         "customerId": customer_id,
#         "status":     status,
#         "count":      0,
#         "logs":       [],
#     }


import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def get_asset_maintenance_logs(
    customer_id,
    status      = "All",
    limit_start : int = 0,
    limit_end   : int = 20,
):
    """
    Returns paginated Asset Maintenance Logs for a given customer.

    Args:
        customer_id  : Customer ID (required)
        status       : "All" | "Open"  (default "All")
        limit_start  : Zero-based offset — first record to return (default 0)
        limit_end    : Last record index (exclusive), i.e. page size = limit_end - limit_start
                       e.g. limit_start=0, limit_end=20  → page 1 (records 1-20)
                            limit_start=20, limit_end=40 → page 2 (records 21-40)

    Response includes:
        pagination.totalCount   : total matching records (before slicing)
        pagination.limit_start  : echoed back
        pagination.limit_end    : echoed back
        pagination.pageSize     : limit_end - limit_start
        pagination.totalPages   : ceil(totalCount / pageSize)
        pagination.currentPage  : 1-based current page number
        pagination.hasNextPage  : bool
        pagination.hasPrevPage  : bool
    """

    # ── Cast to int (whitelist passes everything as string) ───────
    limit_start = int(limit_start)
    limit_end   = int(limit_end)
    page_size   = limit_end - limit_start

    if page_size <= 0:
        frappe.throw(_("limit_end must be greater than limit_start"), frappe.ValidationError)

    if not customer_id:
        frappe.throw(_("customer_id is required"), frappe.MandatoryError)

    # ── Step 1: Get all Location names for this customer ──────────
    locations = frappe.get_all(
        "Location",
        filters={"custom_customer": customer_id},
        fields=["name"],
    )
    location_names = [l["name"] for l in locations]

    if not location_names:
        return _empty_response(customer_id, status, limit_start, limit_end)

    # ── Step 2: Get all Asset IDs in those locations ──────────────
    all_assets = frappe.get_all(
        "Asset",
        filters={"location": ["in", location_names]},
        fields=["name"],
    )
    asset_ids = [a["name"] for a in all_assets]

    if not asset_ids:
        return _empty_response(customer_id, status, limit_start, limit_end)

    # ─────────────────────────────────────────────────────────────
    # PATH A — Reactive
    # assetId = custom_asset (directly available)
    # ─────────────────────────────────────────────────────────────
    reactive_filters = {
        "docstatus": ["in", [0, 1]],
        "custom_asset_maintenance_type": "Reactive",
        "custom_asset": ["in", asset_ids],
    }
    if status.lower() == "open":
        reactive_filters["maintenance_status"] = ["in", ["Planned", "Overdue"]]

    reactive_logs = frappe.get_all(
        "Asset Maintenance Log",
        filters=reactive_filters,
        fields=_log_fields(),
        order_by="creation desc",
    )

    # ─────────────────────────────────────────────────────────────
    # PATH B — Planned
    # assetId = Asset Maintenance.asset_name (Asset ID stored there)
    # ─────────────────────────────────────────────────────────────
    am_records = frappe.get_all(
        "Asset Maintenance",
        filters={"asset_name": ["in", asset_ids]},
        fields=["name", "asset_name"],
    )
    am_to_asset_id = {am["name"]: am["asset_name"] for am in am_records}
    am_names = list(am_to_asset_id.keys())

    planned_logs = []
    if am_names:
        planned_filters = {
            "docstatus": ["in", [0, 1]],
            "custom_asset_maintenance_type": "Planned",
            "asset_name": ["in", am_names],
        }
        if status.lower() == "open":
            planned_filters["maintenance_status"] = ["in", ["Planned", "Overdue"]]

        planned_logs = frappe.get_all(
            "Asset Maintenance Log",
            filters=planned_filters,
            fields=_log_fields(),
            order_by="creation desc",
        )

    # ── Merge + deduplicate ───────────────────────────────────────
    seen = set()
    combined_logs = []
    for log in reactive_logs + planned_logs:
        if log["name"] not in seen:
            seen.add(log["name"])
            combined_logs.append(log)

    combined_logs.sort(key=lambda x: str(x.get("creation") or ""), reverse=True)

    # ── Pagination ────────────────────────────────────────────────
    total_count   = len(combined_logs)
    paged_logs    = combined_logs[limit_start:limit_end]   # slice the full list

    import math
    total_pages   = math.ceil(total_count / page_size) if page_size else 1
    current_page  = (limit_start // page_size) + 1 if page_size else 1

    # ── Build final response ──────────────────────────────────────
    logs = []
    for log in paged_logs:
        if log.get("custom_asset_maintenance_type") == "Reactive":
            asset_id = log.get("custom_asset")
        else:
            asset_id = am_to_asset_id.get(log.get("asset_name"))

        items_raw = frappe.get_all(
            "Stock Items For Asset",
            filters={"parent": log["name"], "parenttype": "Asset Maintenance Log"},
            fields=[
                "name",
                "item_code",
                "qty",
                "uom",
                "stock_uom",
                "conversion_factor",
                "s_warehouse",
            ],
            order_by="idx asc",
        )

        logs.append(
            {
                "name":                  log["name"],
                "assetName":             log["asset_name"],
                "assetId":               asset_id,
                "itemCode":              log["item_code"],
                "itemName":              log["item_name"],
                "taskName":              log["task_name"],
                "maintenanceStatus":     log["maintenance_status"],
                "maintenanceType":       log["maintenance_type"],
                "customMaintenanceType": log["custom_maintenance_types"],
                "assetMaintenanceType":  log["custom_asset_maintenance_type"],
                "assignTo":              log["custom_assign_to"],
                "assignToName":          log["assign_to_name"],
                "periodicity":           log["periodicity"],
                "completionDate":        str(log["completion_date"]) if log.get("completion_date") else None,
                "hasCertificate":        bool(log["has_certificate"]),
                "description":           log["description"],
                "docStatus":             log["docstatus"],
                "createdAt":             str(log["creation"]) if log.get("creation") else None,
                "updatedAt":             str(log["modified"]) if log.get("modified") else None,
                "stockItems": [
                    {
                        "id":               item["name"],
                        "itemCode":         item["item_code"],
                        "qty":              item["qty"],
                        "uom":              item["uom"],
                        "stockUom":         item["stock_uom"],
                        "conversionFactor": item["conversion_factor"],
                        "warehouse":        item["s_warehouse"],
                    }
                    for item in items_raw
                ],
            }
        )

    return {
        "success":    True,
        "customerId": customer_id,
        "status":     status,
        "count":      len(logs),           # records returned in THIS page
        "logs":       logs,
        "pagination": {
            "totalCount":  total_count,    # all matching records across all pages
            "limit_start": limit_start,
            "limit_end":   limit_end,
            "pageSize":    page_size,
            "totalPages":  total_pages,
            "currentPage": current_page,
            "hasNextPage": limit_end < total_count,
            "hasPrevPage": limit_start > 0,
        },
    }


def _log_fields():
    return [
        "name",
        "asset_name",
        "item_code",
        "item_name",
        "task_name",
        "maintenance_status",
        "maintenance_type",
        "custom_maintenance_types",
        "custom_asset",
        "custom_asset_maintenance_type",
        "custom_assign_to",
        "assign_to_name",
        "periodicity",
        "completion_date",
        "has_certificate",
        "description",
        "docstatus",
        "creation",
        "modified",
    ]


def _empty_response(customer_id, status, limit_start, limit_end):
    return {
        "success":    True,
        "customerId": customer_id,
        "status":     status,
        "count":      0,
        "logs":       [],
        "pagination": {
            "totalCount":  0,
            "limit_start": limit_start,
            "limit_end":   limit_end,
            "pageSize":    limit_end - limit_start,
            "totalPages":  0,
            "currentPage": 1,
            "hasNextPage": False,
            "hasPrevPage": False,
        },
    }