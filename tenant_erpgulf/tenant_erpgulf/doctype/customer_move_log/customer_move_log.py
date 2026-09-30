# Copyright (c) 2026, ERPGulf and contributors
# For license information, please see license.txt

"""
Customer Move Log  ->  keeps Location.custom_customer in sync.

    Move In  (move_in_date <= today, no move out)  -> Location.custom_customer = customer
    Move Out (move_out_date <= today)              -> Location.custom_customer = empty
    New customer moves in to same location         -> Location.custom_customer = new customer

Future-dated Move In / Move Out are applied by the daily scheduler job
`sync_all_locations` (add to hooks.py):

    scheduler_events = {
        "daily": [
            "your_app.your_module.doctype.customer_move_log.customer_move_log.sync_all_locations",
        ],
    }
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

LOCATION_CUSTOMER_FIELD = "custom_customer"


class CustomerMoveLog(Document):
	def validate(self):
		self.validate_dates()
		self.validate_location_not_occupied()

	def on_update(self):
		sync_location_customer(self.location)

		# Location changed on an existing entry -> refresh the old one too
		before = self.get_doc_before_save()
		if before and before.location and before.location != self.location:
			sync_location_customer(before.location)

	def after_delete(self):
		sync_location_customer(self.location)

	# ------------------------------------------------------------------

	def validate_dates(self):
		if self.move_in_date and self.move_out_date:
			if getdate(self.move_out_date) < getdate(self.move_in_date):
				frappe.throw(_("Move Out Date cannot be before Move In Date"))

	def validate_location_not_occupied(self):
		"""Block a second customer in the same location for overlapping dates."""
		if not (self.location and self.move_in_date):
			return

		others = frappe.get_all(
			"Customer Move Log",
			filters={"location": self.location, "name": ["!=", self.name or ""]},
			fields=["name", "customer_name", "move_in_date", "move_out_date"],
		)

		my_in = getdate(self.move_in_date)
		my_out = getdate(self.move_out_date) if self.move_out_date else None

		for o in others:
			o_in = getdate(o.move_in_date)
			o_out = getdate(o.move_out_date) if o.move_out_date else None

			# Two periods overlap if each starts before the other ends
			# (an empty move out date = still staying)
			starts_before_other_ends = o_out is None or my_in < o_out
			other_starts_before_mine_ends = my_out is None or o_in < my_out

			if starts_before_other_ends and other_starts_before_mine_ends:
				frappe.throw(
					_(
						"Location {0} is already occupied by {1} ({2}). "
						"Set a Move Out Date on that entry first."
					).format(
						frappe.bold(self.location),
						frappe.bold(o.customer_name or o.name),
						frappe.get_desk_link("Customer Move Log", o.name),
					)
				)


# ----------------------------------------------------------------------
# Sync helpers
# ----------------------------------------------------------------------

def get_current_customer(location):
	"""Customer currently staying at the location as of today, else None."""
	current = frappe.db.sql(
		"""
		SELECT customer
		FROM `tabCustomer Move Log`
		WHERE location = %(location)s
		  AND move_in_date <= %(today)s
		  AND (move_out_date IS NULL OR move_out_date > %(today)s)
		ORDER BY move_in_date DESC, creation DESC
		LIMIT 1
		""",
		{"location": location, "today": today()},
		as_dict=True,
	)
	return current[0].customer if current else None


def sync_location_customer(location):
	"""Set Location.custom_customer to the current occupant (or empty)."""
	if not location or not frappe.db.exists("Location", location):
		return

	customer = get_current_customer(location)
	existing = frappe.db.get_value("Location", location, LOCATION_CUSTOMER_FIELD)

	if (existing or None) != (customer or None):
		frappe.db.set_value("Location", location, LOCATION_CUSTOMER_FIELD, customer)


def sync_all_locations():
	"""Daily job - applies future-dated move ins / move outs."""
	locations = frappe.get_all("Customer Move Log", pluck="location", distinct=True)
	occupied = frappe.get_all(
		"Location", filters={LOCATION_CUSTOMER_FIELD: ["is", "set"]}, pluck="name"
	)
	for location in set(locations) | set(occupied):
		sync_location_customer(location)