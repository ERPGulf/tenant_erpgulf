import frappe
from frappe.model.document import Document


class MaintenanceRequest(Document):

    def on_update_after_submit(self):
        if (
            self.status != "Under Review"
            and not self.custom_status_changed_date
        ):
            self.custom_status_changed_date = frappe.utils.now()
            self.db_update()