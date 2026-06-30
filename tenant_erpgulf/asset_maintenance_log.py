
# import frappe
# from frappe import _
# from frappe.utils import getdate, nowdate
# from erpnext.assets.doctype.asset_maintenance_log.asset_maintenance_log import AssetMaintenanceLog
# from erpnext.assets.doctype.asset_maintenance.asset_maintenance import calculate_next_due_date


# class CustomAssetMaintenanceLog(AssetMaintenanceLog):

#     def validate(self):
#         frappe.log_error(
#             title="[Reactive] validate CALLED",
#             message=f"doc={self.name} | type={self.custom_asset_maintenance_type} | "
#                     f"company={self.get('company')} | asset_maintenance={self.get('asset_maintenance')} | "
#                     f"task={self.get('task')} | custom_asset={self.get('custom_asset')}"
#         )
#         try:
#             if self.custom_asset_maintenance_type == "Reactive":
#                 self.validate_reactive()
#             else:
#                 super().validate()
#         except Exception:
#             frappe.log_error(
#                 title="[Reactive] validate FAILED",
#                 message=frappe.get_traceback()
#             )
#             raise

#     def before_save(self):
#         frappe.log_error(
#             title="[Reactive] before_save CALLED",
#             message=f"doc={self.name} | type={self.custom_asset_maintenance_type} | "
#                     f"company={self.get('company')} | custom_asset={self.get('custom_asset')} | "
#                     f"asset_maintenance={self.get('asset_maintenance')} | task={self.get('task')}"
#         )
#         try:
#             if self.custom_asset_maintenance_type == "Reactive":
#                 self._patch_reactive_fields()
#         except Exception:
#             frappe.log_error(
#                 title="[Reactive] before_save FAILED",
#                 message=frappe.get_traceback()
#             )
#             raise

#     def before_submit(self):
#         frappe.log_error(
#             title="[Reactive] before_submit CALLED",
#             message=f"doc={self.name} | type={self.custom_asset_maintenance_type} | "
#                     f"company={self.get('company')} | custom_asset={self.get('custom_asset')} | "
#                     f"asset_maintenance={self.get('asset_maintenance')} | task={self.get('task')}"
#         )
#         try:
#             if self.custom_asset_maintenance_type == "Reactive":
#                 if not getattr(self, "_reactive_patched", False):
#                     self._patch_reactive_fields()
#             # Planned — no override, ERPNext default before_submit runs via super()
#         except Exception:
#             frappe.log_error(
#                 title="[Reactive] before_submit FAILED",
#                 message=frappe.get_traceback()
#             )
#             raise

#     def on_update(self):
#         """
#         Reactive → create ToDo on save (docstatus=0) only.
#         Planned  → do nothing here, ERPNext handles ToDo on submit.
#         """
#         try:
#             if self.custom_asset_maintenance_type != "Reactive":
#                 # Planned: let ERPNext default behaviour handle everything
#                 return

#             # Reactive: only create ToDo when draft (docstatus=0)
#             if self.docstatus != 0:
#                 return

#             if not self.get("custom_assign_to"):
#                 return

#             # ── Avoid duplicate: delete existing open ToDo for this log ────────
#             existing = frappe.db.get_value(
#                 "ToDo",
#                 {
#                     "reference_type": "Asset Maintenance Log",
#                     "reference_name": self.name,
#                     "status":         "Open",
#                 },
#                 "name",
#             )
#             if existing:
#                 frappe.delete_doc("ToDo", existing, ignore_permissions=True)
#                 frappe.log_error(
#                     title="[Reactive] on_update — old ToDo deleted",
#                     message=f"deleted={existing} | doc={self.name}"
#                 )

#             # ── Build description ──────────────────────────────────────────────
#             description = """
#                 <b>Reactive Maintenance Task</b><br>
#                 <b>Asset:</b> {asset}<br>
#                 <b>Item Code:</b> {item_code}<br>
#                 <b>Item Name:</b> {item_name}<br>
#                 <b>Task:</b> {task}<br>
#                 <b>Maintenance Type:</b> {mtype}<br>
#                 <b>Periodicity:</b> {periodicity}<br>
#                 <b>Customer:</b> {customer}<br>
#                 <b>Quotation:</b> {quotation}
#             """.format(
#                 asset       = self.get("asset_name") or "",
#                 item_code   = self.get("item_code") or "",
#                 item_name   = self.get("item_name") or "",
#                 task        = self.get("task_name") or "",
#                 mtype       = self.get("custom_maintenance_types") or "",
#                 periodicity = self.get("periodicity") or "",
#                 customer    = self.get("custom_customer") or "",
#                 quotation   = self.get("custom_quotation") or "",
#             )

#             todo = frappe.get_doc({
#                 "doctype":        "ToDo",
#                 "reference_type": "Asset Maintenance Log",
#                 "reference_name": self.name,
#                 "description":    description,
#                 "priority":       "Medium",
#                 "status":         "Open",
#                 "date":           self.get("due_date") or frappe.utils.nowdate(),
#                 "allocated_to":   self.get("custom_assign_to"),
#             })
#             todo.insert(ignore_permissions=True)

#             frappe.log_error(
#                 title="[Reactive] on_update — ToDo CREATED",
#                 message=f"todo={todo.name} | assigned_to={self.get('custom_assign_to')} | doc={self.name}"
#             )

#         except Exception:
#             frappe.log_error(
#                 title="[Reactive] on_update — ToDo creation FAILED",
#                 message=frappe.get_traceback()
#             )
#             raise

#     def on_submit(self):
#         frappe.log_error(
#             title="[Reactive] on_submit CALLED",
#             message=f"doc={self.name} | type={self.custom_asset_maintenance_type} | "
#                     f"company={self.get('company')} | status={self.maintenance_status} | "
#                     f"asset_maintenance={self.get('asset_maintenance')} | task={self.get('task')}"
#         )
#         try:
#             if self.maintenance_status not in ["Completed", "Cancelled"]:
#                 frappe.throw(_("Maintenance Status has to be Cancelled or Completed to Submit"))

#             if self.custom_asset_maintenance_type == "Reactive":
#                 # ── Reactive: close existing ToDo, no new one created ──────────
#                 frappe.log_error(
#                     title="[Reactive] on_submit → closing ToDo + update_reactive_maintenance",
#                     message=f"doc={self.name}"
#                 )
#                 self._close_reactive_todo()
#                 self.update_reactive_maintenance()

#             else:
#                 # ── Planned: ERPNext default on_submit behaviour ───────────────
#                 # super().on_submit() creates ToDo + updates maintenance task
#                 frappe.log_error(
#                     title="[Planned] on_submit → calling super().on_submit()",
#                     message=f"doc={self.name}"
#                 )
#                 super().on_submit()

#         except Exception:
#             frappe.log_error(
#                 title="[Reactive] on_submit FAILED",
#                 message=frappe.get_traceback()
#             )
#             raise

#     def validate_reactive(self):
#         frappe.log_error(
#             title="[Reactive] validate_reactive CALLED",
#             message=f"doc={self.name} | due_date={self.get('due_date')} | "
#                     f"status={self.get('maintenance_status')} | "
#                     f"completion_date={self.get('completion_date')}"
#         )
#         try:
#             if self.due_date and getdate(self.due_date) < getdate(nowdate()) and \
#                     self.maintenance_status not in ["Completed", "Cancelled"]:
#                 self.maintenance_status = "Overdue"

#             if self.maintenance_status == "Completed" and not self.completion_date:
#                 frappe.throw(
#                     _("Please select Completion Date for Completed Asset Maintenance Log")
#                 )

#             if self.maintenance_status != "Completed" and self.completion_date:
#                 frappe.throw(
#                     _("Please select Maintenance Status as Completed or remove Completion Date")
#                 )

#             frappe.log_error(
#                 title="[Reactive] validate_reactive PASSED",
#                 message=f"doc={self.name} | final_status={self.maintenance_status}"
#             )
#         except Exception:
#             frappe.log_error(
#                 title="[Reactive] validate_reactive FAILED",
#                 message=frappe.get_traceback()
#             )
#             raise

#     def _patch_reactive_fields(self):
#         frappe.log_error(
#             title="[Reactive] _patch_reactive_fields START",
#             message=f"doc={self.name} | custom_asset={self.get('custom_asset')} | "
#                     f"company={self.get('company')} | asset_name={self.get('asset_name')} | "
#                     f"asset_maintenance={self.get('asset_maintenance')} | task={self.get('task')}"
#         )
#         try:
#             custom_asset = self.get("custom_asset")

#             if not custom_asset:
#                 frappe.log_error(
#                     title="[Reactive] _patch_reactive_fields ABORT",
#                     message="custom_asset is empty — cannot fetch company"
#                 )
#                 frappe.throw(_("Please select an Asset before submitting."))

#             # ── Fetch company from Asset ───────────────────────────────────────
#             company = frappe.db.get_value("Asset", custom_asset, "company")

#             frappe.log_error(
#                 title="[Reactive] _patch_reactive_fields company FETCHED",
#                 message=f"custom_asset={custom_asset} | company={company}"
#             )

#             if not company:
#                 frappe.log_error(
#                     title="[Reactive] _patch_reactive_fields company NOT FOUND",
#                     message=f"Asset '{custom_asset}' has no company value"
#                 )
#                 frappe.throw(
#                     _("Could not find Company from Asset '{0}'. "
#                       "Please ensure the Asset has a Company set.").format(custom_asset)
#                 )

#             # ── Set ONLY in memory ─────────────────────────────────────────────
#             object.__setattr__(self, "company", company)

#             frappe.log_error(
#                 title="[Reactive] _patch_reactive_fields company SET in memory",
#                 message=f"doc={self.name} | company={company}"
#             )

#             # ── Also ensure asset_name is set in memory ────────────────────────
#             if not self.get("asset_name"):
#                 asset_name = frappe.db.get_value("Asset", custom_asset, "asset_name")
#                 if asset_name:
#                     object.__setattr__(self, "asset_name", asset_name)
#                     frappe.log_error(
#                         title="[Reactive] _patch_reactive_fields asset_name SET",
#                         message=f"asset_name={asset_name}"
#                     )

#             # ── Nullify fields that trigger ERPNext company lookup chain ───────
#             self.asset_maintenance = None
#             self.task = None

#             # ── Mark as patched to avoid re-running in before_submit ───────────
#             self._reactive_patched = True

#             frappe.log_error(
#                 title="[Reactive] _patch_reactive_fields END SUCCESS",
#                 message=f"doc={self.name} | company={self.get('company')} | "
#                         f"asset_name={self.get('asset_name')} | "
#                         f"asset_maintenance={self.get('asset_maintenance')} | "
#                         f"task={self.get('task')}"
#             )

#         except Exception:
#             frappe.log_error(
#                 title="[Reactive] _patch_reactive_fields FAILED",
#                 message=frappe.get_traceback()
#             )
#             raise

#     def _close_reactive_todo(self):
#         """On submit, close the open ToDo for Reactive — do NOT create a new one."""
#         try:
#             todo_name = frappe.db.get_value(
#                 "ToDo",
#                 {
#                     "reference_type": "Asset Maintenance Log",
#                     "reference_name": self.name,
#                     "status":         "Open",
#                 },
#                 "name",
#             )

#             if todo_name:
#                 new_status = "Closed" if self.maintenance_status == "Completed" else "Cancelled"
#                 frappe.db.set_value("ToDo", todo_name, "status", new_status)
#                 frappe.log_error(
#                     title="[Reactive] _close_reactive_todo — ToDo CLOSED",
#                     message=f"todo={todo_name} | new_status={new_status} | doc={self.name}"
#                 )
#             else:
#                 frappe.log_error(
#                     title="[Reactive] _close_reactive_todo — no open ToDo found",
#                     message=f"doc={self.name}"
#                 )

#         except Exception:
#             frappe.log_error(
#                 title="[Reactive] _close_reactive_todo FAILED",
#                 message=frappe.get_traceback()
#             )
#             raise

#     def update_maintenance_task(self):
#         frappe.log_error(
#             title="[Reactive] update_maintenance_task CALLED",
#             message=f"doc={self.name} | task={self.get('task')} | "
#                     f"asset_maintenance={self.get('asset_maintenance')} | "
#                     f"status={self.maintenance_status}"
#         )
#         try:
#             if self.custom_asset_maintenance_type == "Reactive":
#                 frappe.log_error(
#                     title="[Reactive] update_maintenance_task SKIPPED (Reactive)",
#                     message=f"doc={self.name}"
#                 )
#                 return

#             if not self.get("task"):
#                 frappe.throw(_("No Maintenance Task linked. Cannot update."))

#             if not frappe.db.exists("Asset Maintenance Task", self.task):
#                 frappe.throw(
#                     _("Asset Maintenance Task {0} not found").format(self.task)
#                 )

#             asset_maintenance_doc = frappe.get_doc("Asset Maintenance Task", self.task)

#             if self.maintenance_status == "Completed":
#                 if asset_maintenance_doc.last_completion_date != self.completion_date:
#                     next_due_date = calculate_next_due_date(
#                         periodicity=self.periodicity,
#                         last_completion_date=self.completion_date
#                     )
#                     asset_maintenance_doc.last_completion_date = self.completion_date
#                     asset_maintenance_doc.next_due_date = next_due_date
#                     asset_maintenance_doc.maintenance_status = "Planned"
#                     asset_maintenance_doc.save()
#                     frappe.log_error(
#                         title="[Reactive] update_maintenance_task task UPDATED (Completed)",
#                         message=f"task={self.task} | next_due_date={next_due_date}"
#                     )

#             if self.maintenance_status == "Cancelled":
#                 asset_maintenance_doc.maintenance_status = "Cancelled"
#                 asset_maintenance_doc.save()
#                 frappe.log_error(
#                     title="[Reactive] update_maintenance_task task UPDATED (Cancelled)",
#                     message=f"task={self.task}"
#                 )

#             if self.get("asset_maintenance") and frappe.db.exists(
#                 "Asset Maintenance", self.asset_maintenance
#             ):
#                 frappe.get_doc("Asset Maintenance", self.asset_maintenance).save()
#                 frappe.log_error(
#                     title="[Reactive] update_maintenance_task asset_maintenance SAVED",
#                     message=f"asset_maintenance={self.asset_maintenance}"
#                 )

#         except Exception:
#             frappe.log_error(
#                 title="[Reactive] update_maintenance_task FAILED",
#                 message=frappe.get_traceback()
#             )
#             raise

#     def update_reactive_maintenance(self):
#         frappe.log_error(
#             title="[Reactive] update_reactive_maintenance CALLED",
#             message=f"doc={self.name} | status={self.maintenance_status} | "
#                     f"assign_to={self.get('custom_assign_to')} | "
#                     f"asset={self.get('asset_name')}"
#         )
#         try:
#             if self.maintenance_status == "Completed" and self.get("custom_assign_to"):
#                 try:
#                     frappe.sendmail(
#                         recipients=[self.custom_assign_to],
#                         subject=_("Reactive Maintenance Completed: {0}").format(
#                             self.get("asset_name")
#                         ),
#                         message="""
#                             <b>Asset:</b> {0}<br>
#                             <b>Item:</b> {1} - {2}<br>
#                             <b>Task:</b> {3}<br>
#                             <b>Maintenance Type:</b> {4}<br>
#                             <b>Completion Date:</b> {5}<br>
#                             <b>Status:</b> {6}
#                         """.format(
#                             self.get("asset_name"),
#                             self.get("item_code"),
#                             self.get("item_name"),
#                             self.get("task_name"),
#                             self.get("custom_maintenance_types"),
#                             self.get("completion_date"),
#                             self.maintenance_status,
#                         )
#                     )
#                     frappe.log_error(
#                         title="[Reactive] update_reactive_maintenance email SENT",
#                         message=f"to={self.custom_assign_to}"
#                     )
#                 except Exception:
#                     frappe.log_error(
#                         title="[Reactive] update_reactive_maintenance email FAILED",
#                         message=frappe.get_traceback()
#                     )

#             frappe.msgprint(
#                 _("Reactive Maintenance Log {0} submitted successfully.").format(self.name),
#                 indicator="green",
#                 alert=True,
#             )

#             frappe.log_error(
#                 title="[Reactive] update_reactive_maintenance END SUCCESS",
#                 message=f"doc={self.name}"
#             )

#         except Exception:
#             frappe.log_error(
#                 title="[Reactive] update_reactive_maintenance FAILED",
#                 message=frappe.get_traceback()
#             )
#             raise
import frappe
from frappe import _
from frappe.utils import getdate, nowdate
from erpnext.assets.doctype.asset_maintenance_log.asset_maintenance_log import AssetMaintenanceLog
from erpnext.assets.doctype.asset_maintenance.asset_maintenance import calculate_next_due_date


class CustomAssetMaintenanceLog(AssetMaintenanceLog):

    def validate(self):
        frappe.log_error(
            title="[Reactive] validate CALLED",
            message=f"doc={self.name} | type={self.custom_asset_maintenance_type} | "
                    f"company={self.get('company')} | asset_maintenance={self.get('asset_maintenance')} | "
                    f"task={self.get('task')} | custom_asset={self.get('custom_asset')}"
        )
        try:
            if self.custom_asset_maintenance_type == "Reactive":
                self.validate_reactive()
            else:
                super().validate()
        except Exception:
            frappe.log_error(
                title="[Reactive] validate FAILED",
                message=frappe.get_traceback()
            )
            raise

    def before_save(self):
        frappe.log_error(
            title="[Reactive] before_save CALLED",
            message=f"doc={self.name} | type={self.custom_asset_maintenance_type} | "
                    f"company={self.get('company')} | custom_asset={self.get('custom_asset')} | "
                    f"asset_maintenance={self.get('asset_maintenance')} | task={self.get('task')}"
        )
        try:
            if self.custom_asset_maintenance_type == "Reactive":
                self._patch_reactive_fields()
        except Exception:
            frappe.log_error(
                title="[Reactive] before_save FAILED",
                message=frappe.get_traceback()
            )
            raise

    def before_submit(self):
        frappe.log_error(
            title="[Reactive] before_submit CALLED",
            message=f"doc={self.name} | type={self.custom_asset_maintenance_type} | "
                    f"company={self.get('company')} | custom_asset={self.get('custom_asset')} | "
                    f"asset_maintenance={self.get('asset_maintenance')} | task={self.get('task')}"
        )
        try:
            if self.custom_asset_maintenance_type == "Reactive":
                if not getattr(self, "_reactive_patched", False):
                    self._patch_reactive_fields()
            # Planned — no override, ERPNext default before_submit runs via super()
        except Exception:
            frappe.log_error(
                title="[Reactive] before_submit FAILED",
                message=frappe.get_traceback()
            )
            raise

    def on_update(self):
        """
        Reactive → create ToDo on save (docstatus=0) only.
        Planned  → do nothing here, ERPNext handles ToDo on submit.
        """
        try:
            if self.custom_asset_maintenance_type != "Reactive":
                # Planned: let ERPNext default behaviour handle everything
                return

            # Reactive: only create ToDo when draft (docstatus=0)
            if self.docstatus != 0:
                return

            if not self.get("custom_assign_to"):
                return

            # ── Avoid duplicate: delete existing open ToDo for this log ────────
            existing = frappe.db.get_value(
                "ToDo",
                {
                    "reference_type": "Asset Maintenance Log",
                    "reference_name": self.name,
                    "status":         "Open",
                },
                "name",
            )
            if existing:
                frappe.delete_doc("ToDo", existing, ignore_permissions=True)
                frappe.log_error(
                    title="[Reactive] on_update — old ToDo deleted",
                    message=f"deleted={existing} | doc={self.name}"
                )

            # ── Determine task name based on maintenance type ───────────────────
            if self.custom_asset_maintenance_type == "Reactive":
                task_name = self.get("custom_name_of_task") or ""
            else:
                task_name = self.get("task_name") or ""

            # ── Build description ──────────────────────────────────────────────
            description = """
                <b>Reactive Maintenance Task</b><br>
                <b>Asset:</b> {asset}<br>
                <b>Task:</b> {task}<br>
                <b>Maintenance Type:</b> {mtype}<br>
                <b>Quotation:</b> {quotation}
            """.format(
                asset       = self.get("asset_name") or "",
                task        = task_name,
                mtype       = self.get("custom_maintenance_types") or "",
                quotation   = self.get("custom_quotation") or "",
            )

            todo = frappe.get_doc({
                "doctype":        "ToDo",
                "reference_type": "Asset Maintenance Log",
                "reference_name": self.name,
                "description":    description,
                "priority":       "Medium",
                "status":         "Open",
                "date":           self.get("due_date") or frappe.utils.nowdate(),
                "allocated_to":   self.get("custom_assign_to"),
            })
            todo.insert(ignore_permissions=True)

            frappe.log_error(
                title="[Reactive] on_update — ToDo CREATED",
                message=f"todo={todo.name} | assigned_to={self.get('custom_assign_to')} | doc={self.name}"
            )

        except Exception:
            frappe.log_error(
                title="[Reactive] on_update — ToDo creation FAILED",
                message=frappe.get_traceback()
            )
            raise

    def on_submit(self):
        frappe.log_error(
            title="[Reactive] on_submit CALLED",
            message=f"doc={self.name} | type={self.custom_asset_maintenance_type} | "
                    f"company={self.get('company')} | status={self.maintenance_status} | "
                    f"asset_maintenance={self.get('asset_maintenance')} | task={self.get('task')}"
        )
        try:
            if self.maintenance_status not in ["Completed", "Cancelled"]:
                frappe.throw(_("Maintenance Status has to be Cancelled or Completed to Submit"))

            if self.custom_asset_maintenance_type == "Reactive":
                # ── Reactive: close existing ToDo, no new one created ──────────
                frappe.log_error(
                    title="[Reactive] on_submit → closing ToDo + update_reactive_maintenance",
                    message=f"doc={self.name}"
                )
                self._close_reactive_todo()
                self.update_reactive_maintenance()

            else:
                # ── Planned: ERPNext default on_submit behaviour ───────────────
                # super().on_submit() creates ToDo + updates maintenance task
                frappe.log_error(
                    title="[Planned] on_submit → calling super().on_submit()",
                    message=f"doc={self.name}"
                )
                super().on_submit()

        except Exception:
            frappe.log_error(
                title="[Reactive] on_submit FAILED",
                message=frappe.get_traceback()
            )
            raise

    def validate_reactive(self):
        frappe.log_error(
            title="[Reactive] validate_reactive CALLED",
            message=f"doc={self.name} | due_date={self.get('due_date')} | "
                    f"status={self.get('maintenance_status')} | "
                    f"completion_date={self.get('completion_date')}"
        )
        try:
            if self.due_date and getdate(self.due_date) < getdate(nowdate()) and \
                    self.maintenance_status not in ["Completed", "Cancelled"]:
                self.maintenance_status = "Overdue"

            if self.maintenance_status == "Completed" and not self.completion_date:
                frappe.throw(
                    _("Please select Completion Date for Completed Asset Maintenance Log")
                )

            if self.maintenance_status != "Completed" and self.completion_date:
                frappe.throw(
                    _("Please select Maintenance Status as Completed or remove Completion Date")
                )

            frappe.log_error(
                title="[Reactive] validate_reactive PASSED",
                message=f"doc={self.name} | final_status={self.maintenance_status}"
            )
        except Exception:
            frappe.log_error(
                title="[Reactive] validate_reactive FAILED",
                message=frappe.get_traceback()
            )
            raise

    def _patch_reactive_fields(self):
        frappe.log_error(
            title="[Reactive] _patch_reactive_fields START",
            message=f"doc={self.name} | custom_asset={self.get('custom_asset')} | "
                    f"company={self.get('company')} | asset_name={self.get('asset_name')} | "
                    f"asset_maintenance={self.get('asset_maintenance')} | task={self.get('task')}"
        )
        try:
            custom_asset = self.get("custom_asset")

            if not custom_asset:
                frappe.log_error(
                    title="[Reactive] _patch_reactive_fields ABORT",
                    message="custom_asset is empty — cannot fetch company"
                )
                frappe.throw(_("Please select an Asset before submitting."))

            # ── Fetch company from Asset ───────────────────────────────────────
            company = frappe.db.get_value("Asset", custom_asset, "company")

            frappe.log_error(
                title="[Reactive] _patch_reactive_fields company FETCHED",
                message=f"custom_asset={custom_asset} | company={company}"
            )

            if not company:
                frappe.log_error(
                    title="[Reactive] _patch_reactive_fields company NOT FOUND",
                    message=f"Asset '{custom_asset}' has no company value"
                )
                frappe.throw(
                    _("Could not find Company from Asset '{0}'. "
                      "Please ensure the Asset has a Company set.").format(custom_asset)
                )

            # ── Set ONLY in memory ─────────────────────────────────────────────
            object.__setattr__(self, "company", company)

            frappe.log_error(
                title="[Reactive] _patch_reactive_fields company SET in memory",
                message=f"doc={self.name} | company={company}"
            )

            # ── Also ensure asset_name is set in memory ────────────────────────
            if not self.get("asset_name"):
                asset_name = frappe.db.get_value("Asset", custom_asset, "asset_name")
                if asset_name:
                    object.__setattr__(self, "asset_name", asset_name)
                    frappe.log_error(
                        title="[Reactive] _patch_reactive_fields asset_name SET",
                        message=f"asset_name={asset_name}"
                    )

            # ── Nullify fields that trigger ERPNext company lookup chain ───────
            self.asset_maintenance = None
            self.task = None

            # ── Mark as patched to avoid re-running in before_submit ───────────
            self._reactive_patched = True

            frappe.log_error(
                title="[Reactive] _patch_reactive_fields END SUCCESS",
                message=f"doc={self.name} | company={self.get('company')} | "
                        f"asset_name={self.get('asset_name')} | "
                        f"asset_maintenance={self.get('asset_maintenance')} | "
                        f"task={self.get('task')}"
            )

        except Exception:
            frappe.log_error(
                title="[Reactive] _patch_reactive_fields FAILED",
                message=frappe.get_traceback()
            )
            raise

    def _close_reactive_todo(self):
        """On submit, close the open ToDo for Reactive — do NOT create a new one."""
        try:
            todo_name = frappe.db.get_value(
                "ToDo",
                {
                    "reference_type": "Asset Maintenance Log",
                    "reference_name": self.name,
                    "status":         "Open",
                },
                "name",
            )

            if todo_name:
                new_status = "Closed" if self.maintenance_status == "Completed" else "Cancelled"
                frappe.db.set_value("ToDo", todo_name, "status", new_status)
                frappe.log_error(
                    title="[Reactive] _close_reactive_todo — ToDo CLOSED",
                    message=f"todo={todo_name} | new_status={new_status} | doc={self.name}"
                )
            else:
                frappe.log_error(
                    title="[Reactive] _close_reactive_todo — no open ToDo found",
                    message=f"doc={self.name}"
                )

        except Exception:
            frappe.log_error(
                title="[Reactive] _close_reactive_todo FAILED",
                message=frappe.get_traceback()
            )
            raise

    def update_maintenance_task(self):
        frappe.log_error(
            title="[Reactive] update_maintenance_task CALLED",
            message=f"doc={self.name} | task={self.get('task')} | "
                    f"asset_maintenance={self.get('asset_maintenance')} | "
                    f"status={self.maintenance_status}"
        )
        try:
            if self.custom_asset_maintenance_type == "Reactive":
                frappe.log_error(
                    title="[Reactive] update_maintenance_task SKIPPED (Reactive)",
                    message=f"doc={self.name}"
                )
                return

            if not self.get("task"):
                frappe.throw(_("No Maintenance Task linked. Cannot update."))

            if not frappe.db.exists("Asset Maintenance Task", self.task):
                frappe.throw(
                    _("Asset Maintenance Task {0} not found").format(self.task)
                )

            asset_maintenance_doc = frappe.get_doc("Asset Maintenance Task", self.task)

            if self.maintenance_status == "Completed":
                if asset_maintenance_doc.last_completion_date != self.completion_date:
                    next_due_date = calculate_next_due_date(
                        periodicity=self.periodicity,
                        last_completion_date=self.completion_date
                    )
                    asset_maintenance_doc.last_completion_date = self.completion_date
                    asset_maintenance_doc.next_due_date = next_due_date
                    asset_maintenance_doc.maintenance_status = "Planned"
                    asset_maintenance_doc.save()
                    frappe.log_error(
                        title="[Reactive] update_maintenance_task task UPDATED (Completed)",
                        message=f"task={self.task} | next_due_date={next_due_date}"
                    )

            if self.maintenance_status == "Cancelled":
                asset_maintenance_doc.maintenance_status = "Cancelled"
                asset_maintenance_doc.save()
                frappe.log_error(
                    title="[Reactive] update_maintenance_task task UPDATED (Cancelled)",
                    message=f"task={self.task}"
                )

            if self.get("asset_maintenance") and frappe.db.exists(
                "Asset Maintenance", self.asset_maintenance
            ):
                frappe.get_doc("Asset Maintenance", self.asset_maintenance).save()
                frappe.log_error(
                    title="[Reactive] update_maintenance_task asset_maintenance SAVED",
                    message=f"asset_maintenance={self.asset_maintenance}"
                )

        except Exception:
            frappe.log_error(
                title="[Reactive] update_maintenance_task FAILED",
                message=frappe.get_traceback()
            )
            raise

    def update_reactive_maintenance(self):
        frappe.log_error(
            title="[Reactive] update_reactive_maintenance CALLED",
            message=f"doc={self.name} | status={self.maintenance_status} | "
                    f"assign_to={self.get('custom_assign_to')} | "
                    f"asset={self.get('asset_name')}"
        )
        try:
            if self.maintenance_status == "Completed" and self.get("custom_assign_to"):
                try:
                    frappe.sendmail(
                        recipients=[self.custom_assign_to],
                        subject=_("Reactive Maintenance Completed: {0}").format(
                            self.get("asset_name")
                        ),
                        message="""
                            <b>Asset:</b> {0}<br>
                            <b>Item:</b> {1} - {2}<br>
                            <b>Task:</b> {3}<br>
                            <b>Maintenance Type:</b> {4}<br>
                            <b>Completion Date:</b> {5}<br>
                            <b>Status:</b> {6}
                        """.format(
                            self.get("asset_name"),
                            self.get("item_code"),
                            self.get("item_name"),
                            self.get("task_name"),
                            self.get("custom_maintenance_types"),
                            self.get("completion_date"),
                            self.maintenance_status,
                        )
                    )
                    frappe.log_error(
                        title="[Reactive] update_reactive_maintenance email SENT",
                        message=f"to={self.custom_assign_to}"
                    )
                except Exception:
                    frappe.log_error(
                        title="[Reactive] update_reactive_maintenance email FAILED",
                        message=frappe.get_traceback()
                    )

            frappe.msgprint(
                _("Reactive Maintenance Log {0} submitted successfully.").format(self.name),
                indicator="green",
                alert=True,
            )

            frappe.log_error(
                title="[Reactive] update_reactive_maintenance END SUCCESS",
                message=f"doc={self.name}"
            )

        except Exception:
            frappe.log_error(
                title="[Reactive] update_reactive_maintenance FAILED",
                message=frappe.get_traceback()
            )
            raise