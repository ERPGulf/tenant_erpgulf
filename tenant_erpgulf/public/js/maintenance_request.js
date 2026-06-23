frappe.ui.form.on("Maintenance Request", {
    refresh(frm) {

        // ── Already has a linked log → show "View" button ────────
        if (frm.doc.maintenance_log) {
            frm.add_custom_button(__("View Maintenance Log"), function () {
                frappe.set_route("Form", "Asset Maintenance Log", frm.doc.maintenance_log);
            }).addClass("btn-primary");
            return;
        }

        // ── Submitted + Under Process → show "Create" button ─────
        if (frm.doc.docstatus === 1 && frm.doc.status === "Under Process") {
            frm.add_custom_button(__("Create Maintenance Log"), function () {

                frappe.confirm(
                    __("Create a Maintenance Log for this request?"),
                    function () {
                        frappe.call({
                            method: "tenant_erpgulf.maintenance_re.create_maintenance_log_from_request",
                            args: { maintenance_request: frm.doc.name },
                            freeze: true,
                            freeze_message: __("Creating Maintenance Log..."),
                            callback(r) {
                                if (r.message && r.message.success) {
                                    frappe.show_alert({
                                        message: __("Maintenance Log created successfully"),
                                        indicator: "green",
                                    }, 4);

                                    // ── Reload first, then open the new log ──
                                    frm.reload_doc().then(() => {
                                        frappe.set_route(
                                            "Form",
                                            "Asset Maintenance Log",
                                            r.message.maintenance_log
                                        );
                                    });
                                }
                            },
                        });
                    }
                );

            }).addClass("btn-primary");
        }
    },
});