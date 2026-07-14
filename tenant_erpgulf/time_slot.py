import datetime

import frappe
from frappe import _
from frappe.utils import getdate


def _normalize_date(value):
    """
    Maintenance dates are stored in the DB as ISO (YYYY-MM-DD), but
    clients often send whatever the site's display format is
    (e.g. DD-MM-YYYY). Normalize to a date object before filtering,
    otherwise "20-07-2026" will never match the stored "2026-07-20"
    and every slot will look free even when it isn't.
    """
    if not value:
        return value
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    # fall back to Frappe's own parser (respects System Settings date format)
    return getdate(value)


@frappe.whitelist(allow_guest=False)
def get_available_time_slots(maintenance_type, maintenance_date):
    """
    API to return the time slots still open for a given
    maintenance_type + maintenance_date combination.

    Call as GET:
      /api/method/<your_app>.<module>.get_available_time_slots
          ?maintenance_type=Electrical&maintenance_date=2026-07-20

    Rules implemented:
      - A slot is "taken" only when another Maintenance Request already
        exists with the SAME maintenance_type AND the SAME maintenance_date
        booked in that slot.
      - Cancelled requests (docstatus 2) do NOT block a slot.
      - Same date but a DIFFERENT maintenance_type -> slot still shown.
      - Same maintenance_type but a DIFFERENT date -> slot still shown.
    """

    if not maintenance_type or not maintenance_date:
        frappe.throw(
            _("Both maintenance_type and maintenance_date are required"),
            frappe.MandatoryError,
        )

    # ── All possible slots, read from the time_slot Select field itself ──
    # (so if you edit the Select options later, this API stays in sync)
    meta = frappe.get_meta("Maintenance Request")
    time_slot_field = meta.get_field("time_slot")

    if not time_slot_field or not time_slot_field.options:
        frappe.throw(
            _("time_slot Select options are not configured on Maintenance Request")
        )

    all_slots = [d.strip() for d in time_slot_field.options.split("\n") if d.strip()]

    normalized_date = _normalize_date(maintenance_date)

    # ── Slots already booked for this exact maintenance_type + date ──────
    booked = frappe.get_all(
        "Maintenance Request",
        filters={
            "maintenance_type": maintenance_type,
            "maintenance_date": normalized_date,
            "docstatus": ["!=", 2],  # ignore cancelled requests
        },
        pluck="time_slot",
    )
    booked_slots = {b for b in booked if b}

    available_slots = [slot for slot in all_slots if slot not in booked_slots]

    return {
        "success": True,
        "maintenanceType": maintenance_type,
        "maintenanceDate": str(normalized_date),
        "allSlots": all_slots,
        "bookedSlots": sorted(booked_slots),
        "availableSlots": available_slots,
    }