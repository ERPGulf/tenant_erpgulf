frappe.listview_settings['Location'] = {
    onload: function (listview) {
        listview.page.add_actions_menu_item(__('Generate QR Code'), function () {
            let selected = listview.get_checked_items();

            if (!selected.length) {
                frappe.msgprint(__('Select at least one Location first.'));
                return;
            }

            let names = selected.map(d => d.name);

            frappe.call({
                method: "tenant_erpgulf.location_qr.generate_qr_for_selected",
                args: { locations: names },
                freeze: true,
                freeze_message: __('Generating QR codes...'),
                callback: function (r) {
                    let msg = r.message;
                    frappe.msgprint(
                        __('QR generated for {0} location(s). Failed: {1}', [msg.done.length, msg.failed.length])
                    );
                    listview.refresh();
                }
            });
        }, true);
    }
};