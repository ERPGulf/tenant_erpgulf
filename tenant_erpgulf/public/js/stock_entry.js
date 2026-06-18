frappe.ui.form.on("Stock Entry", {
    refresh: function (frm) {
        // Only show on submitted Material Issue entries that have the link
        if (frm.doc.docstatus !== 1) return;
        if (!frm.doc.custom_asset_maintenance_log) return;

        frm.add_custom_button(
            __("View Asset Maintenance Log"),
            function () {
                frappe.set_route(
                    "Form",
                    "Asset Maintenance Log",
                    frm.doc.custom_asset_maintenance_log
                );
            },
            __("Actions") // optional group label
        ).addClass("btn-primary");
    }
});