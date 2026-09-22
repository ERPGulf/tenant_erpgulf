
# import datetime
# import re

# import frappe
# from frappe import _
# from frappe.utils import getdate, now_datetime


# def _normalize_date(value):
#     """
#     Maintenance dates are stored in the DB as ISO (YYYY-MM-DD), but
#     clients often send whatever the site's display format is
#     (e.g. DD-MM-YYYY). Normalize to a date object before filtering,
#     otherwise "20-07-2026" will never match the stored "2026-07-20"
#     and every slot will look free even when it isn't.
#     """
#     if not value:
#         return value
#     value = str(value).strip()
#     for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
#         try:
#             return datetime.datetime.strptime(value, fmt).date()
#         except ValueError:
#             continue
#     # fall back to Frappe's own parser (respects System Settings date format)
#     return getdate(value)


# # Matches labels like "9-10 AM", "11-12 PM", "9:30-10:30 AM" -- a single
# # meridiem written once, after the END hour, covering the whole slot.
# _RANGE_RE = re.compile(
#     r"^\s*(\d{1,2})(?::(\d{2}))?\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\s*$",
#     re.IGNORECASE,
# )


# def _to_24h(hour, meridiem):
#     """Convert a 12-hour (hour, AM/PM) pair to a 24-hour hour number."""
#     hour = hour % 12
#     if meridiem.upper() == "PM":
#         hour += 12
#     return hour


# def _parse_slot_start(time_slot):
#     """
#     Pull just the start clock-time out of a time_slot label.

#     Handles two label styles:
#       - "9-10 AM", "11-12 PM", "9:30-10:30 AM" -- one meridiem, written
#         after the end hour, for the whole slot (this is the style
#         actually used by the time_slot Select options in this app).
#       - "09:00 AM - 10:00 AM", "09:00 - 10:00", "9 AM - 10 AM" -- an
#         explicit start time, kept for backwards compatibility.

#     Returns a datetime.time, or None if the label doesn't match either
#     style.
#     """
#     if not time_slot:
#         return None
#     text = str(time_slot).strip()

#     match = _RANGE_RE.match(text)
#     if match:
#         start_hour = int(match.group(1))
#         start_minute = int(match.group(2) or 0)
#         end_hour = int(match.group(3))
#         end_meridiem = match.group(5).upper()

#         # The written meridiem applies to the whole slot EXCEPT across the
#         # 11 -> 12 boundary, which is the one point a 12-hour clock flips
#         # AM/PM without saying so: "11-12 PM" is 11 AM - 12 PM (noon), not
#         # 11 PM - 12 PM. Every other pair in this schedule (9-10 AM,
#         # 12-1 PM, 2-3 PM, ...) shares one meridiem for both ends.
#         if start_hour == 11 and end_hour == 12:
#             start_meridiem = "AM" if end_meridiem == "PM" else "PM"
#         else:
#             start_meridiem = end_meridiem

#         return datetime.time(_to_24h(start_hour, start_meridiem), start_minute)

#     # fall back to an explicit "09:00 AM - 10:00 AM" / "09:00 - 10:00" start
#     start_part = re.split(r"-|–|\bto\b", text, maxsplit=1)[0].strip()
#     for fmt in ("%I:%M %p", "%I %p", "%H:%M:%S", "%H:%M"):
#         try:
#             return datetime.datetime.strptime(start_part, fmt).time()
#         except ValueError:
#             continue
#     return None


# def _filter_slots_after_now(slots, maintenance_date):
#     """
#     Keep only the slots that start strictly after the current moment.

#       - future maintenance_date -> every slot passes through unchanged
#       - today's maintenance_date -> only slots later than the current
#         time survive
#       - a maintenance_date already in the past -> every slot is dropped

#     A slot whose label can't be parsed into a start time is kept rather
#     than silently hidden, so a mis-typed/mis-configured Select option
#     doesn't just vanish from the response.
#     """
#     now = now_datetime()
#     kept = []
#     for slot in slots:
#         start_time = _parse_slot_start(slot)
#         if start_time is None:
#             kept.append(slot)
#             continue
#         slot_datetime = datetime.datetime.combine(maintenance_date, start_time)
#         if slot_datetime > now:
#             kept.append(slot)
#     return kept


# @frappe.whitelist(allow_guest=False)
# def get_available_time_slots(maintenance_type, maintenance_date):
#     """
#     API to return the time slots still open for a given
#     maintenance_type + maintenance_date combination.

#     Call as GET:
#       /api/method/<your_app>.<module>.get_available_time_slots
#           ?maintenance_type=Electrical&maintenance_date=2026-07-20

#     Rules implemented:
#       - A slot is "taken" only when another Maintenance Request already
#         exists with the SAME maintenance_type AND the SAME maintenance_date
#         booked in that slot.
#       - Cancelled requests (docstatus 2) do NOT block a slot.
#       - Same date but a DIFFERENT maintenance_type -> slot still shown.
#       - Same maintenance_type but a DIFFERENT date -> slot still shown.
#       - Slots that have already started/passed are excluded: for today's
#         date only slots later than the current time are returned; for a
#         date already in the past, none are returned; future dates are
#         unaffected.
#     """

#     if not maintenance_type or not maintenance_date:
#         frappe.throw(
#             _("Both maintenance_type and maintenance_date are required"),
#             frappe.MandatoryError,
#         )

#     # ── All possible slots, read from the time_slot Select field itself ──
#     # (so if you edit the Select options later, this API stays in sync)
#     meta = frappe.get_meta("Maintenance Request")
#     time_slot_field = meta.get_field("time_slot")

#     if not time_slot_field or not time_slot_field.options:
#         frappe.throw(
#             _("time_slot Select options are not configured on Maintenance Request")
#         )

#     all_slots = [d.strip() for d in time_slot_field.options.split("\n") if d.strip()]

#     normalized_date = _normalize_date(maintenance_date)

#     # ── Slots already booked for this exact maintenance_type + date ──────
#     booked = frappe.get_all(
#         "Maintenance Request",
#         filters={
#             "maintenance_type": maintenance_type,
#             "maintenance_date": normalized_date,
#             "docstatus": ["!=", 2],  # ignore cancelled requests
#         },
#         pluck="time_slot",
#     )
#     booked_slots = {b for b in booked if b}

#     available_slots = [slot for slot in all_slots if slot not in booked_slots]

#     # ── Drop slots that have already started relative to right now ──────
#     available_slots = _filter_slots_after_now(available_slots, normalized_date)

#     return {
#         "success": True,
#         "maintenanceType": maintenance_type,
#         "maintenanceDate": str(normalized_date),
#         "allSlots": all_slots,
#         "bookedSlots": sorted(booked_slots),
#         "availableSlots": available_slots,
#     }
import datetime
import re

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime


# Maintenance types that are allowed to book the evening slots (5 PM onward).
# Every other maintenance_type only ever sees slots up to "4-5 PM" -- the
# evening slots are dropped from allSlots/availableSlots entirely for them,
# rather than being shown and marked unavailable.
EXTENDED_HOURS_MAINTENANCE_TYPES = {"AC Repair", "Electrical", "Plumbing"}
EVENING_CUTOFF_HOUR = 17  # 5 PM, 24-hour clock

# Paste this into the time_slot Select field's Options (DocType/Customize
# Form) on Maintenance Request -- one slot per line, running from 9 AM
# straight through to 11 PM with the existing 1-2 PM lunch gap kept as-is:
#
#   9-10 AM
#   10-11 AM
#   11-12 PM
#   12-1 PM
#   2-3 PM
#   3-4 PM
#   4-5 PM
#   5-6 PM
#   6-7 PM
#   7-8 PM
#   8-9 PM
#   9-10 PM
#   10-11 PM
#
# The API below reads whatever is actually configured on that field, so
# once you update the Select options there, nothing else needs touching.


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


# Matches labels like "9-10 AM", "11-12 PM", "9:30-10:30 AM" -- a single
# meridiem written once, after the END hour, covering the whole slot.
_RANGE_RE = re.compile(
    r"^\s*(\d{1,2})(?::(\d{2}))?\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\s*$",
    re.IGNORECASE,
)


def _to_24h(hour, meridiem):
    """Convert a 12-hour (hour, AM/PM) pair to a 24-hour hour number."""
    hour = hour % 12
    if meridiem.upper() == "PM":
        hour += 12
    return hour


def _parse_slot_start(time_slot):
    """
    Pull just the start clock-time out of a time_slot label.

    Handles two label styles:
      - "9-10 AM", "11-12 PM", "5-6 PM", "9:30-10:30 AM" -- one meridiem,
        written after the end hour, for the whole slot (this is the style
        actually used by the time_slot Select options in this app).
      - "09:00 AM - 10:00 AM", "09:00 - 10:00", "9 AM - 10 AM" -- an
        explicit start time, kept for backwards compatibility.

    Returns a datetime.time, or None if the label doesn't match either
    style.
    """
    if not time_slot:
        return None
    text = str(time_slot).strip()

    match = _RANGE_RE.match(text)
    if match:
        start_hour = int(match.group(1))
        start_minute = int(match.group(2) or 0)
        end_hour = int(match.group(3))
        end_meridiem = match.group(5).upper()

        # The written meridiem applies to the whole slot EXCEPT across the
        # 11 -> 12 boundary, which is the one point a 12-hour clock flips
        # AM/PM without saying so: "11-12 PM" is 11 AM - 12 PM (noon), not
        # 11 PM - 12 PM. Every other pair in this schedule (9-10 AM,
        # 12-1 PM, 2-3 PM, ... 10-11 PM) shares one meridiem for both ends.
        if start_hour == 11 and end_hour == 12:
            start_meridiem = "AM" if end_meridiem == "PM" else "PM"
        else:
            start_meridiem = end_meridiem

        return datetime.time(_to_24h(start_hour, start_meridiem), start_minute)

    # fall back to an explicit "09:00 AM - 10:00 AM" / "09:00 - 10:00" start
    start_part = re.split(r"-|–|\bto\b", text, maxsplit=1)[0].strip()
    for fmt in ("%I:%M %p", "%I %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.datetime.strptime(start_part, fmt).time()
        except ValueError:
            continue
    return None


def _restrict_slots_by_maintenance_type(slots, maintenance_type):
    """
    Evening slots (5 PM onward) are only offered for the maintenance types
    listed in EXTENDED_HOURS_MAINTENANCE_TYPES ("AC Repair", "Electrical",
    "Plumbing"). Every other maintenance_type never sees those slots at
    all -- they're removed here, before booked/available is even worked
    out, so they don't show up as "unavailable" either.

    A slot label that can't be parsed is kept (same fail-open behaviour as
    _filter_slots_after_now), so a mis-typed Select option doesn't just
    silently vanish for everyone.
    """
    if maintenance_type in EXTENDED_HOURS_MAINTENANCE_TYPES:
        return slots
    kept = []
    for slot in slots:
        start_time = _parse_slot_start(slot)
        if start_time is not None and start_time.hour >= EVENING_CUTOFF_HOUR:
            continue
        kept.append(slot)
    return kept


def _filter_slots_after_now(slots, maintenance_date):
    """
    Keep only the slots that start strictly after the current moment.

      - future maintenance_date -> every slot passes through unchanged
      - today's maintenance_date -> only slots later than the current
        time survive
      - a maintenance_date already in the past -> every slot is dropped

    A slot whose label can't be parsed into a start time is kept rather
    than silently hidden, so a mis-typed/mis-configured Select option
    doesn't just vanish from the response.
    """
    now = now_datetime()
    kept = []
    for slot in slots:
        start_time = _parse_slot_start(slot)
        if start_time is None:
            kept.append(slot)
            continue
        slot_datetime = datetime.datetime.combine(maintenance_date, start_time)
        if slot_datetime > now:
            kept.append(slot)
    return kept


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
      - Slots that have already started/passed are excluded: for today's
        date only slots later than the current time are returned; for a
        date already in the past, none are returned; future dates are
        unaffected.
      - Evening slots (5 PM and later) are only offered for maintenance
        types in EXTENDED_HOURS_MAINTENANCE_TYPES ("AC Repair",
        "Electrical", "Plumbing"). Every other maintenance_type never
        sees a slot past "4-5 PM", regardless of date.
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

    # ── Drop evening slots entirely for maintenance types that aren't ────
    # allowed to book them (see EXTENDED_HOURS_MAINTENANCE_TYPES above).
    all_slots = _restrict_slots_by_maintenance_type(all_slots, maintenance_type)

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

    # ── Drop slots that have already started relative to right now ──────
    available_slots = _filter_slots_after_now(available_slots, normalized_date)

    return {
        "success": True,
        "maintenanceType": maintenance_type,
        "maintenanceDate": str(normalized_date),
        "allSlots": all_slots,
        "bookedSlots": sorted(booked_slots & set(all_slots)),
        "availableSlots": available_slots,
    }