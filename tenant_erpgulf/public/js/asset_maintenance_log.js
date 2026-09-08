frappe.ui.form.on('Asset Maintenance Log', {

    refresh: function(frm) {
        set_maintenance_stock_filter(frm);
        apply_reactive_logic(frm);
        set_quotation_filter(frm);

        if (
            !frm.is_new() &&
            frm.doc.docstatus === 0 &&
            !frm.doc.custom_quotation &&
            frm.doc.custom_quotation_status !== 'Quotation not reqd'
        ) {
            frm.add_custom_button(__('Quotation'), function() {
                create_quotation_from_maintenance(frm);
            }, __('Create'));
        }

        // --- NEW: Create Material Request, pulling items from custom_items ---
        if (
            !frm.is_new() &&
            frm.doc.docstatus !== 2 &&
            (frm.doc.custom_items || []).some(row => row.item_code)
        ) {
            frm.add_custom_button(__('Material Request'), function() {
                create_material_request_from_maintenance(frm);
            }, __('Create'));
        }
        // --- end new block ---

        if (frm.doc.docstatus === 1) {

            frappe.db.get_value(
                'Stock Entry',
                {
                    custom_asset_maintenance_log: frm.doc.name,
                    docstatus: 1
                },
                'name',
                function(r) {
                    if (r && r.name) {
                        frm.add_custom_button(
                            __('Stock Entry'),
                            function() {
                                frappe.set_route('Form', 'Stock Entry', r.name);
                            },
                            __('View')
                        ).addClass('btn-primary');
                    }
                }
            );
        }
    },

    onload: function(frm) {
        set_maintenance_stock_filter(frm);
        set_quotation_filter(frm);
    },

    custom_asset_maintenance_type: function(frm) {
        frm.set_value('asset_maintenance', null);
        frm.set_value('asset_name', '');
        frm.set_value('item_name', '');
        frm.set_value('item_code', '');
        frm.set_value('task', '');
        frm.set_value('task_name', '');
        frm.set_value('maintenance_type', '');
        frm.set_value('custom_maintenance_types', '');
        frm.set_value('periodicity', '');
        frm.set_value('custom_assign_to', '');

        if (frm.fields_dict['custom_quotation']) {
            frm.set_value('custom_quotation', '');
        }
        if (frm.fields_dict['custom_customer']) {
            frm.set_value('custom_customer', '');
        }
        if (frm.fields_dict['custom_maintenance_team']) {
            frm.set_value('custom_maintenance_team', '');
        }
        if (frm.fields_dict['custom_name_of_task']) {
            frm.set_value('custom_name_of_task', '');
        }

        apply_reactive_logic(frm);
    },

    custom_maintenance_scope: function(frm) {
        apply_reactive_logic(frm);
    },

    asset_maintenance: function(frm) {
        if (frm.doc.asset_maintenance) {
            frappe.db.get_value('Asset Maintenance', frm.doc.asset_maintenance,
                ['asset_name'], function(value) {
                if (value) {
                    frm.set_value('asset_name', value.asset_name);

                    frappe.db.get_value('Asset', value.asset_name, 'location', function(asset_val) {
                        if (asset_val && asset_val.location) {
                            fetch_customer_from_location(frm, asset_val.location);
                        }
                    });
                }
            });
        }
    },

    custom_asset: function(frm) {
        if (frm.doc.custom_asset_maintenance_type === 'Reactive' && frm.doc.custom_asset) {
            frappe.db.get_value('Asset', frm.doc.custom_asset,
                ['asset_name', 'item_name', 'item_code', 'location'], function(value) {
                if (value) {
                    frm.set_value('asset_name', value.asset_name);
                    frm.set_value('item_name', value.item_name);
                    frm.set_value('item_code', value.item_code);
                    frm.refresh_fields(['asset_name', 'item_name', 'item_code']);

                    if (value.location) {
                        fetch_customer_from_location(frm, value.location);
                    }
                }
            });
        }

        toggle_scope_reference(frm);
    },

    custom_quotation: function(frm) {
        if (frm.doc.custom_quotation) {
            frm.set_value('custom_quotation_status', 'Quotation issued');
        }
    },

    custom_default_warehouse: function(frm) {
        if (!frm.doc.custom_default_warehouse) return;

        (frm.doc.custom_items || []).forEach(function(row) {
            frappe.model.set_value(
                row.doctype,
                row.name,
                's_warehouse',
                frm.doc.custom_default_warehouse
            );
        });

        frm.refresh_field('custom_items');
    },

    after_save: function(frm) {
        if (frm.doc.custom_asset_maintenance_type === 'Reactive') {
            create_todo_for_reactive(frm);
        }
    }

});


frappe.ui.form.on('Stock Items For Asset', {

    custom_items_add: function(frm, cdt, cdn) {
        if (!frm.doc.custom_default_warehouse) return;

        frappe.model.set_value(
            cdt,
            cdn,
            's_warehouse',
            frm.doc.custom_default_warehouse
        );
    },

    item_code: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item_code) return;

        frappe.db.get_value(
            'Item',
            row.item_code,
            ['stock_uom'],
            function(item) {
                if (!item || !item.stock_uom) return;

                const stock_uom = item.stock_uom;

                frappe.model.set_value(cdt, cdn, 'stock_uom', stock_uom);
                frappe.model.set_value(cdt, cdn, 'uom', stock_uom);

                frappe.db.get_value(
                    'UOM Conversion Detail',
                    { parent: row.item_code, uom: stock_uom },
                    'conversion_factor',
                    function(uom_row) {
                        frappe.model.set_value(
                            cdt, cdn,
                            'conversion_factor',
                            (uom_row && uom_row.conversion_factor) ? uom_row.conversion_factor : 1
                        );
                    }
                );
            }
        );
    },

    uom: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item_code || !row.uom) return;

        frappe.db.get_value(
            'UOM Conversion Detail',
            { parent: row.item_code, uom: row.uom },
            'conversion_factor',
            function(uom_row) {
                frappe.model.set_value(
                    cdt, cdn,
                    'conversion_factor',
                    (uom_row && uom_row.conversion_factor) ? uom_row.conversion_factor : 1
                );
            }
        );
    }

});


function set_maintenance_stock_filter(frm) {
    frm.set_query('item_code', 'custom_items', function() {
        return { filters: { 'is_stock_item': 1 } };
    });
}


function set_quotation_filter(frm) {
    if (!frm.fields_dict['custom_quotation']) return;

    frm.set_query('custom_quotation', function() {
        if (frm.fields_dict['custom_customer'] && frm.doc.custom_customer) {
            return {
                filters: {
                    'party_name': frm.doc.custom_customer,
                    'docstatus': ['!=', 2]
                }
            };
        }
        return { filters: { 'docstatus': ['!=', 2] } };
    });
}


function fetch_customer_from_location(frm, location) {
    if (!location) return;

    frappe.db.get_value('Location', location, 'custom_customer', function(loc_val) {
        if (loc_val && loc_val.custom_customer) {

            if (frm.fields_dict['custom_customer']) {
                frm.set_value('custom_customer', loc_val.custom_customer);
                set_quotation_filter(frm);
            }

            if (frm.fields_dict['custom_quotation']) {
                frm.refresh_field('custom_quotation');
            }

            frappe.show_alert({
                message: __('Customer set: {0}', [loc_val.custom_customer]),
                indicator: 'blue'
            }, 4);
        }
    });
}


function create_quotation_from_maintenance(frm) {
    const has_item = (frm.doc.custom_items || []).some(row => row.item_code);

    if (!has_item) {
        frappe.msgprint(__('Please select at least one item before creating a Quotation.'));
        return;
    }

    do_create_quotation(frm);
}

function do_create_quotation(frm) {

    const asset = frm.doc.custom_asset_maintenance_type === 'Reactive'
        ? frm.doc.custom_asset
        : frm.doc.asset_name;

    if (asset) {
        frappe.db.get_value('Asset', asset, 'location', function(asset_val) {
            if (!asset_val || !asset_val.location) {
                frappe.msgprint(__('No Location found on Asset. Cannot fetch Customer.'));
                return;
            }

            frappe.db.get_value('Location', asset_val.location, 'custom_customer', function(loc_val) {
                if (!loc_val || !loc_val.custom_customer) {
                    frappe.msgprint(__('No Customer found on Location. Cannot create Quotation.'));
                    return;
                }

                insert_quotation(frm, loc_val.custom_customer);
            });
        });
        return;
    }

    frappe.db.get_value(
        'Maintenance Request',
        { maintenance_log: frm.doc.name },
        'customer',
        function(mr_val) {
            if (mr_val && mr_val.customer) {
                insert_quotation(frm, mr_val.customer);
                return;
            }

            if (frm.doc.custom_customer) {
                insert_quotation(frm, frm.doc.custom_customer);
                return;
            }

            frappe.msgprint(__('No Asset or Customer found. Cannot create Quotation.'));
        }
    );
}

function insert_quotation(frm, customer) {
    const items = (frm.doc.custom_items || [])
        .filter(row => row.item_code)
        .map(row => ({
            item_code: row.item_code,
            qty: row.qty || 1,
            uom: row.uom || row.stock_uom
        }));

    const quotation_doc = {
        doctype: 'Quotation',
        quotation_to: 'Customer',
        party_name: customer,
        items: items.map(item => ({
            doctype: 'Quotation Item',
            item_code: item.item_code,
            qty: item.qty,
            uom: item.uom
        }))
    };

    frappe.call({
        method: 'frappe.client.insert',
        args: { doc: quotation_doc },
        freeze: true,
        freeze_message: __('Creating Quotation...'),
        callback: function(r) {
            if (r.exc || !r.message) return;

            const quotation_id = r.message.name;

            frappe.db.set_value(
                'Asset Maintenance Log',
                frm.doc.name,
                {
                    'custom_quotation':        quotation_id,
                    'custom_quotation_status': 'Quotation issued'
                },
                function() {
                    frm.reload_doc();

                    frappe.show_alert({
                        message: __('Quotation {0} created and linked', [quotation_id]),
                        indicator: 'green'
                    }, 5);

                    frappe.set_route('Form', 'Quotation', quotation_id);
                }
            );
        }
    });
}


// ============================================================================
// NEW: Create Material Request from the custom_items child table
// ----------------------------------------------------------------------------
// Adds a "Material Request" option under the "Create" button group (added in
// refresh() above). Mirrors the existing Quotation flow: validates at least
// one item row has an item_code, then inserts a Material Request with one
// Material Request Item row per custom_items row.
//
// ASSUMPTIONS — adjust to match your setup:
//   - material_request_type defaults to "Material Issue" (stock consumed for
//     the maintenance job). Change MATERIAL_REQUEST_TYPE below if you need
//     "Purchase", "Material Transfer", etc.
//   - warehouse on each Material Request Item is taken from the row's
//     s_warehouse (falls back to custom_default_warehouse if the row itself
//     has none set).
//   - schedule_date defaults to today.
//   - If your Asset Maintenance Log has custom_material_request /
//     custom_material_request_status fields (like custom_quotation /
//     custom_quotation_status), they get set back after creation; if those
//     fields don't exist yet, this block is skipped safely.
// ============================================================================

const MATERIAL_REQUEST_TYPE = 'Purchase';

function create_material_request_from_maintenance(frm) {
    const has_item = (frm.doc.custom_items || []).some(row => row.item_code);

    if (!has_item) {
        frappe.msgprint(__('Please select at least one item before creating a Material Request.'));
        return;
    }

    insert_material_request(frm);
}

function insert_material_request(frm) {
    const items = (frm.doc.custom_items || [])
        .filter(row => row.item_code)
        .map(row => ({
            doctype: 'Material Request Item',
            item_code: row.item_code,
            qty: row.qty || 1,
            uom: row.uom || row.stock_uom,
            warehouse: row.s_warehouse || frm.doc.custom_default_warehouse,
            schedule_date: frappe.datetime.get_today()
        }));

    const material_request_doc = {
        doctype: 'Material Request',
        material_request_type: MATERIAL_REQUEST_TYPE,
        transaction_date: frappe.datetime.get_today(),
        items: items
    };

    frappe.call({
        method: 'frappe.client.insert',
        args: { doc: material_request_doc },
        freeze: true,
        freeze_message: __('Creating Material Request...'),
        callback: function(r) {
            if (r.exc || !r.message) return;

            const mr_id = r.message.name;

            const update_fields = {};
            if (frm.fields_dict['custom_material_request']) {
                update_fields['custom_material_request'] = mr_id;
            }
            if (frm.fields_dict['custom_material_request_status']) {
                update_fields['custom_material_request_status'] = 'Material Request issued';
            }

            function after_link() {
                frm.reload_doc();

                frappe.show_alert({
                    message: __('Material Request {0} created', [mr_id]),
                    indicator: 'green'
                }, 5);

                frappe.set_route('Form', 'Material Request', mr_id);
            }

            if (Object.keys(update_fields).length) {
                frappe.db.set_value('Asset Maintenance Log', frm.doc.name, update_fields, after_link);
            } else {
                after_link();
            }
        }
    });
}
// ============================================================================
// end new block
// ============================================================================


function apply_reactive_logic(frm) {
    const is_reactive = frm.doc.custom_asset_maintenance_type === 'Reactive';

    const reactive_editable_fields = ['task_name'];

    if (is_reactive) {
        frm.set_df_property('asset_maintenance', 'hidden', 1);
        frm.set_df_property('asset_maintenance', 'reqd', 0);
        frm.set_df_property('task', 'hidden', 1);
        frm.set_df_property('task', 'reqd', 0);
        frm.set_df_property('custom_asset', 'hidden', 0);
        frm.set_df_property('custom_asset', 'reqd', 0);
        frm.set_df_property('asset_name', 'hidden', 0);
        frm.set_df_property('item_name', 'hidden', 0);
        frm.set_df_property('item_code', 'hidden', 0);

        reactive_editable_fields.forEach(function(field) {
            frm.set_df_property(field, 'hidden', 0);
            frm.set_df_property(field, 'read_only', 0);
            frm.set_df_property(field, 'reqd', 0);
        });
        frm.set_df_property('periodicity', 'hidden', 1);
        frm.set_df_property('periodicity', 'reqd', 0);
        frm.set_df_property('maintenance_type', 'hidden', 1);
        frm.set_df_property('custom_maintenance_types', 'hidden', 0);
        frm.set_df_property('custom_maintenance_types', 'read_only', 0);
        frm.set_df_property('custom_maintenance_types', 'reqd', 1);
        frm.set_df_property('assign_to_name', 'hidden', 1);
        frm.set_df_property('custom_assign_to', 'hidden', 0);
        frm.set_df_property('custom_assign_to', 'reqd', 0);

        frm.set_df_property('custom_maintenance_team', 'hidden', 0);
        frm.set_df_property('custom_maintenance_team', 'reqd', 0);
        frm.set_df_property('custom_name_of_task', 'hidden', 0);
        frm.set_df_property('custom_name_of_task', 'reqd', 0);
        frm.set_df_property('task_name', 'hidden', 1);
        frm.set_df_property('task_name', 'reqd', 0);

    } else {
        frm.set_df_property('asset_maintenance', 'hidden', 0);
        frm.set_df_property('asset_maintenance', 'reqd', 1);
        frm.set_df_property('task', 'hidden', 0);
        frm.set_df_property('task', 'reqd', 0);
        frm.set_df_property('custom_asset', 'hidden', 1);
        frm.set_df_property('custom_asset', 'reqd', 0);
        frm.set_df_property('asset_name', 'hidden', 1);
        frm.set_df_property('item_name', 'hidden', 1);
        frm.set_df_property('item_code', 'hidden', 1);

        reactive_editable_fields.forEach(function(field) {
            frm.set_df_property(field, 'read_only', 1);
            frm.set_df_property(field, 'reqd', 0);
        });

        frm.set_df_property('maintenance_type', 'hidden', 0);
        frm.set_df_property('custom_maintenance_types', 'hidden', 1);
        frm.set_df_property('custom_maintenance_types', 'reqd', 0);
        frm.set_df_property('assign_to_name', 'hidden', 0);
        frm.set_df_property('custom_assign_to', 'hidden', 1);
        frm.set_df_property('custom_assign_to', 'reqd', 0);

        frm.set_df_property('custom_maintenance_team', 'hidden', 1);
        frm.set_df_property('custom_maintenance_team', 'reqd', 0);
        frm.set_df_property('custom_name_of_task', 'hidden', 1);
        frm.set_df_property('custom_name_of_task', 'reqd', 0);
        frm.set_df_property('task_name', 'hidden', 0);
    }

    toggle_scope_reference(frm);

    frm.refresh_fields();
}


function toggle_scope_reference(frm) {
    if (!frm.fields_dict['custom_scope_reference']) return;

    const is_reactive = frm.doc.custom_asset_maintenance_type === 'Reactive';
    const has_asset = !!frm.doc.custom_asset;

    if (is_reactive && !has_asset) {
        frm.set_df_property('custom_scope_reference', 'hidden', 0);
        frm.set_df_property('custom_scope_reference', 'reqd', 1);
    } else {
        frm.set_df_property('custom_scope_reference', 'hidden', 1);
        frm.set_df_property('custom_scope_reference', 'reqd', 0);
    }

    frm.refresh_field('custom_scope_reference');
}


function create_todo_for_reactive(frm) {
    frappe.db.get_list('ToDo', {
        filters: {
            reference_type: 'Asset Maintenance Log',
            reference_name: frm.doc.name,
            allocated_to: frm.doc.custom_assign_to
        },
        fields: ['name'],
        limit: 1
    }).then(function(existing) {
        if (existing && existing.length > 0) return;

        const customer = frm.fields_dict['custom_customer']
            ? (frm.doc.custom_customer || '') : '';
        const quotation = frm.fields_dict['custom_quotation']
            ? (frm.doc.custom_quotation || '') : '';

        const description = `
            <b>Reactive Maintenance Task</b><br>
            <b>Asset:</b> ${frm.doc.asset_name || ''}<br>
            <b>Item Code:</b> ${frm.doc.item_code || ''}<br>
            <b>Item Name:</b> ${frm.doc.item_name || ''}<br>
            <b>Task:</b> ${frm.doc.custom_name_of_task || frm.doc.task_name || ''}<br>
            <b>Maintenance Type:</b> ${frm.doc.custom_maintenance_types || ''}<br>
            <b>Periodicity:</b> ${frm.doc.periodicity || ''}<br>
            <b>Maintenance Team:</b> ${frm.doc.custom_maintenance_team || ''}<br>
            <b>Customer:</b> ${customer}<br>
            <b>Quotation:</b> ${quotation}
        `;

        frappe.call({
            method: 'frappe.client.insert',
            args: {
                doc: {
                    doctype: 'ToDo',
                    status: 'Open',
                    priority: 'Medium',
                    allocated_to: frm.doc.custom_assign_to,
                    description: description,
                    reference_type: 'Asset Maintenance Log',
                    reference_name: frm.doc.name,
                    date: frappe.datetime.get_today()
                }
            },
            callback: function(response) {
                if (!response.exc) {
                    frappe.show_alert({
                        message: __('ToDo created for {0}', [frm.doc.custom_assign_to]),
                        indicator: 'green'
                    }, 5);
                }
            }
        });
    });
}