
# import frappe
# from frappe import _


# def before_save(doc, method):
#     if not doc.custom_room_name:
#         return

#     if not doc.location:
#         frappe.throw(_("Please select a Location before assigning a Room."))
#         return

#     try:
#         location_doc = frappe.get_doc("Location", doc.location)
#     except frappe.DoesNotExistError:
#         frappe.throw(_("Location '{0}' does not exist.").format(doc.location))
#         return

#     valid_rooms = get_valid_rooms(location_doc)

#     if valid_rooms is None:
#         frappe.log_error(
#             "Could not find a child table with 'room_name' on Location doctype",
#             "Asset Room Validation"
#         )
#         return

#     if not valid_rooms:
#         frappe.throw(
#             _("No rooms are defined for Location '{0}'. "
#               "Please add rooms before assigning.").format(doc.location)
#         )
#         return

#     if doc.custom_room_name not in valid_rooms:
#         frappe.throw(
#             _("Room Name '{0}' is not valid for Location '{1}'. "
#               "Valid rooms are: {2}").format(
#                 doc.custom_room_name,
#                 doc.location,
#                 ", ".join(valid_rooms)
#             )
#         )


# def get_valid_rooms(location_doc):
#     for fieldname in location_doc.as_dict():
#         value = getattr(location_doc, fieldname, None)

#         if not isinstance(value, list) or not value:
#             continue

#         first_row = value[0]
#         if hasattr(first_row, 'room_name') or \
#            (isinstance(first_row, dict) and 'room_name' in first_row):
#             return [
#                 (row.room_name if hasattr(row, 'room_name') else row['room_name'])
#                 for row in value
#                 if (row.room_name if hasattr(row, 'room_name') else row.get('room_name'))
#             ]

#     return None


# def on_submit(doc, method):
#     """
#     On submitting Asset Maintenance Log,
#     auto-create a Material Issue Stock Entry
#     from custom_items child table.
#     """

#     frappe.log_error(
#         title="[asset.py] on_submit CALLED",
#         message=f"doc={doc.name} | type={doc.get('custom_asset_maintenance_type')} | "
#                 f"asset_maintenance={doc.get('asset_maintenance')} | "
#                 f"custom_asset={doc.get('custom_asset')} | "
#                 f"company={doc.get('company')}"
#     )

#     # ── Validate Task exists ──
#     if doc.task:
#         if not frappe.db.exists("Task", doc.task):
#             frappe.db.set_value("Asset Maintenance Log", doc.name, "task", None)
#             doc.task = None

#     # ── Skip if no items ──
#     if not doc.custom_items:
#         frappe.log_error(
#             title="[asset.py] on_submit SKIPPED — no custom_items",
#             message=f"doc={doc.name}"
#         )
#         return

#     # ── Get company differently for Reactive vs Normal ──
#     is_reactive = doc.get("custom_asset_maintenance_type") == "Reactive"

#     if is_reactive:
#         # For Reactive: fetch company from custom_asset
#         custom_asset = doc.get("custom_asset")
#         frappe.log_error(
#             title="[asset.py] on_submit Reactive — fetching company from custom_asset",
#             message=f"custom_asset={custom_asset}"
#         )
#         company = frappe.db.get_value("Asset", custom_asset, "company")
#     else:
#         # For Normal: fetch company from asset_maintenance
#         company = frappe.db.get_value("Asset", doc.asset_maintenance, "company")

#     frappe.log_error(
#         title="[asset.py] on_submit company FETCHED",
#         message=f"doc={doc.name} | is_reactive={is_reactive} | company={company}"
#     )

#     if not company:
#         frappe.throw(
#             _("Could not find Company from Asset '{0}'.").format(
#                 doc.get("custom_asset") if is_reactive else doc.asset_maintenance
#             )
#         )

#     # ── Build Stock Entry ──
#     stock_entry = frappe.new_doc("Stock Entry")
#     stock_entry.stock_entry_type = "Material Issue"
#     stock_entry.purpose          = "Material Issue"
#     stock_entry.company          = company
#     stock_entry.posting_date     = frappe.utils.today()

#     frappe.log_error(
#         title="[asset.py] on_submit Stock Entry building",
#         message=f"company={company} | items count={len(doc.custom_items)}"
#     )

#     # ── Link back to Maintenance Log ──
#     if hasattr(stock_entry, "custom_asset_maintenance_log"):
#         stock_entry.custom_asset_maintenance_log = doc.name

#     # ── Add items from custom_items ──
#     for row in doc.custom_items:
#         if not row.item_code:
#             continue

#         s_warehouse = row.s_warehouse
#         if not s_warehouse:
#             s_warehouse = frappe.db.get_value(
#                 "Item Default",
#                 {"parent": row.item_code, "company": company},
#                 "default_warehouse"
#             )

#         stock_entry.append("items", {
#             "item_code":         row.item_code,
#             "qty":               row.qty or 1,
#             "uom":               row.uom or row.stock_uom,
#             "stock_uom":         row.stock_uom,
#             "conversion_factor": row.conversion_factor or 1,
#             "s_warehouse":       s_warehouse,
#             "t_warehouse":       None,
#         })

#     if not stock_entry.items:
#         frappe.log_error(
#             title="[asset.py] on_submit no valid items in custom_items",
#             message=f"doc={doc.name}"
#         )
#         frappe.msgprint(
#             _("No valid items found in custom_items. Stock Entry not created.")
#         )
#         return

#     stock_entry.insert(ignore_permissions=True)
#     stock_entry.submit()

#     frappe.log_error(
#         title="[asset.py] on_submit Stock Entry CREATED",
#         message=f"doc={doc.name} | stock_entry={stock_entry.name}"
#     )

#     if hasattr(doc, "custom_stock_entry"):
#         frappe.db.set_value(
#             "Asset Maintenance Log",
#             doc.name,
#             "custom_stock_entry",
#             stock_entry.name
#         )

#     frappe.msgprint(
#         _("Stock Entry {0} created successfully.").format(
#             frappe.utils.bold(stock_entry.name)
#         ),
#         alert=True,
#         indicator="green"
#     )
import frappe
from frappe import _


def before_save(doc, method):
    if not doc.custom_room_name:
        return

    if not doc.location:
        frappe.throw(_("Please select a Location before assigning a Room."))
        return

    try:
        location_doc = frappe.get_doc("Location", doc.location)
    except frappe.DoesNotExistError:
        frappe.throw(_("Location '{0}' does not exist.").format(doc.location))
        return

    valid_rooms = get_valid_rooms(location_doc)

    if valid_rooms is None:
        frappe.log_error(
            "Could not find a child table with 'room_name' on Location doctype",
            "Asset Room Validation"
        )
        return

    if not valid_rooms:
        frappe.throw(
            _("No rooms are defined for Location '{0}'. "
              "Please add rooms before assigning.").format(doc.location)
        )
        return

    if doc.custom_room_name not in valid_rooms:
        frappe.throw(
            _("Room Name '{0}' is not valid for Location '{1}'. "
              "Valid rooms are: {2}").format(
                doc.custom_room_name,
                doc.location,
                ", ".join(valid_rooms)
            )
        )


def get_valid_rooms(location_doc):
    for fieldname in location_doc.as_dict():
        value = getattr(location_doc, fieldname, None)

        if not isinstance(value, list) or not value:
            continue

        first_row = value[0]
        if hasattr(first_row, 'room_name') or \
           (isinstance(first_row, dict) and 'room_name' in first_row):
            return [
                (row.room_name if hasattr(row, 'room_name') else row['room_name'])
                for row in value
                if (row.room_name if hasattr(row, 'room_name') else row.get('room_name'))
            ]

    return None


def on_submit(doc, method):
    frappe.log_error(
        title="[asset.py] on_submit CALLED",
        message=f"doc={doc.name} | type={doc.get('custom_asset_maintenance_type')} | "
                f"asset_maintenance={doc.get('asset_maintenance')} | "
                f"custom_asset={doc.get('custom_asset')} | "
                f"scope={doc.get('custom_maintenance_scope')} | "
                f"company={doc.get('company')}"
    )

    if doc.task:
        if not frappe.db.exists("Task", doc.task):
            frappe.db.set_value("Asset Maintenance Log", doc.name, "task", None)
            doc.task = None

    if not doc.custom_items:
        frappe.log_error(
            title="[asset.py] on_submit SKIPPED — no custom_items",
            message=f"doc={doc.name}"
        )
        return

    is_reactive = doc.get("custom_asset_maintenance_type") == "Reactive"

    if is_reactive:
        custom_asset = doc.get("custom_asset")

        if custom_asset:
            frappe.log_error(
                title="[asset.py] on_submit Reactive — fetching company from custom_asset",
                message=f"custom_asset={custom_asset}"
            )
            company = frappe.db.get_value("Asset", custom_asset, "company")

            if not company:
                frappe.throw(
                    _("Could not find Company from Asset '{0}'.").format(custom_asset)
                )
        else:
            frappe.log_error(
                title="[asset.py] on_submit Reactive no-asset — using default Company",
                message=f"doc={doc.name} | scope={doc.get('custom_maintenance_scope')}"
            )
            company = frappe.defaults.get_global_default("company")

            if not company:
                frappe.throw(
                    _("No Asset is linked for this scope ({0}) and no default Company is "
                      "configured. Please set a default Company or link an Asset.").format(
                        doc.get("custom_maintenance_scope")
                    )
                )
    else:
        company = frappe.db.get_value("Asset", doc.asset_maintenance, "company")

        if not company:
            frappe.throw(
                _("Could not find Company from Asset '{0}'.").format(doc.asset_maintenance)
            )

    frappe.log_error(
        title="[asset.py] on_submit company FETCHED",
        message=f"doc={doc.name} | is_reactive={is_reactive} | company={company}"
    )

    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.stock_entry_type = "Material Issue"
    stock_entry.purpose          = "Material Issue"
    stock_entry.company          = company
    stock_entry.posting_date     = frappe.utils.today()

    frappe.log_error(
        title="[asset.py] on_submit Stock Entry building",
        message=f"company={company} | items count={len(doc.custom_items)}"
    )

    if hasattr(stock_entry, "custom_asset_maintenance_log"):
        stock_entry.custom_asset_maintenance_log = doc.name

    for row in doc.custom_items:
        if not row.item_code:
            continue

        s_warehouse = row.s_warehouse
        if not s_warehouse:
            s_warehouse = frappe.db.get_value(
                "Item Default",
                {"parent": row.item_code, "company": company},
                "default_warehouse"
            )

        stock_entry.append("items", {
            "item_code":         row.item_code,
            "qty":               row.qty or 1,
            "uom":               row.uom or row.stock_uom,
            "stock_uom":         row.stock_uom,
            "conversion_factor": row.conversion_factor or 1,
            "s_warehouse":       s_warehouse,
            "t_warehouse":       None,
        })

    if not stock_entry.items:
        frappe.log_error(
            title="[asset.py] on_submit no valid items in custom_items",
            message=f"doc={doc.name}"
        )
        frappe.msgprint(
            _("No valid items found in custom_items. Stock Entry not created.")
        )
        return

    stock_entry.insert(ignore_permissions=True)
    stock_entry.submit()

    frappe.log_error(
        title="[asset.py] on_submit Stock Entry CREATED",
        message=f"doc={doc.name} | stock_entry={stock_entry.name}"
    )

    if hasattr(doc, "custom_stock_entry"):
        frappe.db.set_value(
            "Asset Maintenance Log",
            doc.name,
            "custom_stock_entry",
            stock_entry.name
        )

    frappe.msgprint(
        _("Stock Entry {0} created successfully.").format(
            frappe.utils.bold(stock_entry.name)
        ),
        alert=True,
        indicator="green"
    )