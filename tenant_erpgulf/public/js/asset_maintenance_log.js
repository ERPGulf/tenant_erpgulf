
// frappe.ui.form.on('Asset Maintenance Log', {

//     refresh: function(frm) {
//         set_maintenance_stock_filter(frm);
//         apply_reactive_logic(frm);
//         set_quotation_filter(frm);

//         // ── Create Quotation button ──
//         // Show only if: doc is saved (not new), not submitted, no quotation linked yet,
//         // and status is NOT 'Quotation not reqd'
//         if (
//             !frm.is_new() &&
//             frm.doc.docstatus === 0 &&
//             !frm.doc.custom_quotation &&
//             frm.doc.custom_quotation_status !== 'Quotation not reqd'
//         ) {
//             frm.add_custom_button(__('Quotation'), function() {
//                 create_quotation_from_maintenance(frm);
//             }, __('Create'));
//         }

//         // ── Only on submitted docs ──
//         if (frm.doc.docstatus === 1) {

//             // ── View Stock Entry button ──
//             frappe.db.get_value(
//                 'Stock Entry',
//                 {
//                     custom_asset_maintenance_log: frm.doc.name,
//                     docstatus: 1
//                 },
//                 'name',
//                 function(r) {
//                     if (r && r.name) {
//                         frm.add_custom_button(
//                             __('Stock Entry'),
//                             function() {
//                                 frappe.set_route('Form', 'Stock Entry', r.name);
//                             },
//                             __('View')
//                         ).addClass('btn-primary');
//                     }
//                 }
//             );
//         }
//     },

//     onload: function(frm) {
//         set_maintenance_stock_filter(frm);
//         set_quotation_filter(frm);
//     },

//     custom_asset_maintenance_type: function(frm) {
//         frm.set_value('asset_maintenance', null);
//         frm.set_value('asset_name', '');
//         frm.set_value('item_name', '');
//         frm.set_value('item_code', '');
//         frm.set_value('task', '');
//         frm.set_value('task_name', '');
//         frm.set_value('maintenance_type', '');
//         frm.set_value('custom_maintenance_types', '');
//         frm.set_value('periodicity', '');
//         frm.set_value('custom_assign_to', '');

//         if (frm.fields_dict['custom_quotation']) {
//             frm.set_value('custom_quotation', '');
//         }
//         if (frm.fields_dict['custom_customer']) {
//             frm.set_value('custom_customer', '');
//         }

//         apply_reactive_logic(frm);
//     },

//     asset_maintenance: function(frm) {
//         if (frm.doc.asset_maintenance) {
//             frappe.db.get_value('Asset Maintenance', frm.doc.asset_maintenance,
//                 ['asset_name'], function(value) {
//                 if (value) {
//                     frm.set_value('asset_name', value.asset_name);

//                     frappe.db.get_value('Asset', value.asset_name, 'location', function(asset_val) {
//                         if (asset_val && asset_val.location) {
//                             fetch_customer_from_location(frm, asset_val.location);
//                         }
//                     });
//                 }
//             });
//         }
//     },

//     custom_asset: function(frm) {
//         if (frm.doc.custom_asset_maintenance_type === 'Reactive' && frm.doc.custom_asset) {
//             frappe.db.get_value('Asset', frm.doc.custom_asset,
//                 ['asset_name', 'item_name', 'item_code', 'location'], function(value) {
//                 if (value) {
//                     frm.set_value('asset_name', value.asset_name);
//                     frm.set_value('item_name', value.item_name);
//                     frm.set_value('item_code', value.item_code);
//                     frm.refresh_fields(['asset_name', 'item_name', 'item_code']);

//                     if (value.location) {
//                         fetch_customer_from_location(frm, value.location);
//                     }
//                 }
//             });
//         }
//     },

//     // ── Auto-set status when Quotation is linked ─────────────────
//     custom_quotation: function(frm) {
//         if (frm.doc.custom_quotation) {
//             frm.set_value('custom_quotation_status', 'Quotation issued');
//         }
//     },

//     custom_default_warehouse: function(frm) {
//         if (!frm.doc.custom_default_warehouse) return;

//         (frm.doc.custom_items || []).forEach(function(row) {
//             frappe.model.set_value(
//                 row.doctype,
//                 row.name,
//                 's_warehouse',
//                 frm.doc.custom_default_warehouse
//             );
//         });

//         frm.refresh_field('custom_items');
//     },

//     after_save: function(frm) {
//         if (frm.doc.custom_asset_maintenance_type === 'Reactive') {
//             create_todo_for_reactive(frm);
//         }
//     }

// });


// // ── Child table: Stock Items For Asset ──
// frappe.ui.form.on('Stock Items For Asset', {

//     custom_items_add: function(frm, cdt, cdn) {
//         if (!frm.doc.custom_default_warehouse) return;

//         frappe.model.set_value(
//             cdt,
//             cdn,
//             's_warehouse',
//             frm.doc.custom_default_warehouse
//         );
//     },

//     item_code: function(frm, cdt, cdn) {
//         const row = locals[cdt][cdn];
//         if (!row.item_code) return;

//         frappe.db.get_value(
//             'Item',
//             row.item_code,
//             ['stock_uom'],
//             function(item) {
//                 if (!item || !item.stock_uom) return;

//                 const stock_uom = item.stock_uom;

//                 frappe.model.set_value(cdt, cdn, 'stock_uom', stock_uom);
//                 frappe.model.set_value(cdt, cdn, 'uom', stock_uom);

//                 frappe.db.get_value(
//                     'UOM Conversion Detail',
//                     { parent: row.item_code, uom: stock_uom },
//                     'conversion_factor',
//                     function(uom_row) {
//                         frappe.model.set_value(
//                             cdt, cdn,
//                             'conversion_factor',
//                             (uom_row && uom_row.conversion_factor) ? uom_row.conversion_factor : 1
//                         );
//                     }
//                 );
//             }
//         );
//     },

//     uom: function(frm, cdt, cdn) {
//         const row = locals[cdt][cdn];
//         if (!row.item_code || !row.uom) return;

//         frappe.db.get_value(
//             'UOM Conversion Detail',
//             { parent: row.item_code, uom: row.uom },
//             'conversion_factor',
//             function(uom_row) {
//                 frappe.model.set_value(
//                     cdt, cdn,
//                     'conversion_factor',
//                     (uom_row && uom_row.conversion_factor) ? uom_row.conversion_factor : 1
//                 );
//             }
//         );
//     }

// });


// // ── Filter: only stock items in child table ──
// function set_maintenance_stock_filter(frm) {
//     frm.set_query('item_code', 'custom_items', function() {
//         return { filters: { 'is_stock_item': 1 } };
//     });
// }


// // ── Quotation filter by customer ──
// function set_quotation_filter(frm) {
//     if (!frm.fields_dict['custom_quotation']) return;

//     frm.set_query('custom_quotation', function() {
//         if (frm.fields_dict['custom_customer'] && frm.doc.custom_customer) {
//             return {
//                 filters: {
//                     'party_name': frm.doc.custom_customer,
//                     'docstatus': ['!=', 2]
//                 }
//             };
//         }
//         return { filters: { 'docstatus': ['!=', 2] } };
//     });
// }


// // ── Fetch customer from Location.custom_customer ──
// function fetch_customer_from_location(frm, location) {
//     if (!location) return;

//     frappe.db.get_value('Location', location, 'custom_customer', function(loc_val) {
//         if (loc_val && loc_val.custom_customer) {

//             if (frm.fields_dict['custom_customer']) {
//                 frm.set_value('custom_customer', loc_val.custom_customer);
//                 set_quotation_filter(frm);
//             }

//             if (frm.fields_dict['custom_quotation']) {
//                 frm.refresh_field('custom_quotation');
//             }

//             frappe.show_alert({
//                 message: __('Customer set: {0}', [loc_val.custom_customer]),
//                 indicator: 'blue'
//             }, 4);
//         }
//     });
// }


// // ── Create Quotation from Asset Maintenance Log ──
// function create_quotation_from_maintenance(frm) {
//     do_create_quotation(frm);
// }

// function do_create_quotation(frm) {

//     const asset = frm.doc.custom_asset_maintenance_type === 'Reactive'
//         ? frm.doc.custom_asset
//         : frm.doc.asset_name;

//     if (!asset) {
//         frappe.msgprint(__('No Asset found. Cannot create Quotation.'));
//         return;
//     }

//     frappe.db.get_value('Asset', asset, 'location', function(asset_val) {
//         if (!asset_val || !asset_val.location) {
//             frappe.msgprint(__('No Location found on Asset. Cannot fetch Customer.'));
//             return;
//         }

//         frappe.db.get_value('Location', asset_val.location, 'custom_customer', function(loc_val) {
//             if (!loc_val || !loc_val.custom_customer) {
//                 frappe.msgprint(__('No Customer found on Location. Cannot create Quotation.'));
//                 return;
//             }

//             const customer = loc_val.custom_customer;

//             const items = (frm.doc.custom_items || [])
//                 .filter(row => row.item_code)
//                 .map(row => ({
//                     item_code: row.item_code,
//                     qty: row.qty || 1,
//                     uom: row.uom || row.stock_uom
//                 }));

//             // ── Build the Quotation doc object ──────────────────────────
//             const quotation_doc = {
//                 doctype: 'Quotation',
//                 quotation_to: 'Customer',
//                 party_name: customer,
//                 items: items.map(item => ({
//                     doctype: 'Quotation Item',
//                     item_code: item.item_code,
//                     qty: item.qty,
//                     uom: item.uom
//                 }))
//             };

//             // ── Save the Quotation via API ───────────────────────────────
//             frappe.call({
//                 method: 'frappe.client.insert',
//                 args: { doc: quotation_doc },
//                 freeze: true,
//                 freeze_message: __('Creating Quotation...'),
//                 callback: function(r) {
//                     if (r.exc || !r.message) return;

//                     const quotation_id = r.message.name;

//                     // ── Store Quotation ID + status back in Asset Maintenance Log ──
//                     frappe.db.set_value(
//                         'Asset Maintenance Log',
//                         frm.doc.name,
//                         {
//                             'custom_quotation':        quotation_id,
//                             'custom_quotation_status': 'Quotation issued'
//                         },
//                         function() {
//                             frm.reload_doc();

//                             frappe.show_alert({
//                                 message: __('Quotation {0} created and linked', [quotation_id]),
//                                 indicator: 'green'
//                             }, 5);

//                             // ── Open the new Quotation form ──
//                             frappe.set_route('Form', 'Quotation', quotation_id);
//                         }
//                     );
//                 }
//             });
//         });
//     });
// }


// // ── Reactive: show/hide fields logic ──
// function apply_reactive_logic(frm) {
//     const is_reactive = frm.doc.custom_asset_maintenance_type === 'Reactive';

//     const reactive_editable_fields = ['task_name'];

//     if (is_reactive) {
//         frm.set_df_property('asset_maintenance', 'hidden', 1);
//         frm.set_df_property('asset_maintenance', 'reqd', 0);
//         frm.set_df_property('task', 'hidden', 1);
//         frm.set_df_property('task', 'reqd', 0);
//         frm.set_df_property('custom_asset', 'hidden', 0);
//         frm.set_df_property('custom_asset', 'reqd', 1);
//         frm.set_df_property('asset_name', 'hidden', 0);
//         frm.set_df_property('item_name', 'hidden', 0);
//         frm.set_df_property('item_code', 'hidden', 0);

//         reactive_editable_fields.forEach(function(field) {
//             frm.set_df_property(field, 'hidden', 0);
//             frm.set_df_property(field, 'read_only', 0);
//             frm.set_df_property(field, 'reqd', 0);
//         });
//         frm.set_df_property('periodicity', 'hidden', 1);
//         frm.set_df_property('periodicity', 'reqd', 0);
//         frm.set_df_property('maintenance_type', 'hidden', 1);
//         frm.set_df_property('custom_maintenance_types', 'hidden', 0);
//         frm.set_df_property('custom_maintenance_types', 'read_only', 0);
//         frm.set_df_property('custom_maintenance_types', 'reqd', 1);
//         frm.set_df_property('assign_to_name', 'hidden', 1);
//         frm.set_df_property('custom_assign_to', 'hidden', 0);
//         frm.set_df_property('custom_assign_to', 'reqd', 0);

//     } else {
//         frm.set_df_property('asset_maintenance', 'hidden', 0);
//         frm.set_df_property('asset_maintenance', 'reqd', 1);
//         frm.set_df_property('task', 'hidden', 0);
//         frm.set_df_property('task', 'reqd', 0);
//         frm.set_df_property('custom_asset', 'hidden', 1);
//         frm.set_df_property('custom_asset', 'reqd', 0);
//         frm.set_df_property('asset_name', 'hidden', 1);
//         frm.set_df_property('item_name', 'hidden', 1);
//         frm.set_df_property('item_code', 'hidden', 1);

//         reactive_editable_fields.forEach(function(field) {
//             frm.set_df_property(field, 'read_only', 1);
//             frm.set_df_property(field, 'reqd', 0);
//         });

//         frm.set_df_property('maintenance_type', 'hidden', 0);
//         frm.set_df_property('custom_maintenance_types', 'hidden', 1);
//         frm.set_df_property('custom_maintenance_types', 'reqd', 0);
//         frm.set_df_property('assign_to_name', 'hidden', 0);
//         frm.set_df_property('custom_assign_to', 'hidden', 1);
//         frm.set_df_property('custom_assign_to', 'reqd', 0);
//     }

//     frm.refresh_fields();
// }


// // ── Reactive: create ToDo on save (no duplicates) ──
// function create_todo_for_reactive(frm) {
//     frappe.db.get_list('ToDo', {
//         filters: {
//             reference_type: 'Asset Maintenance Log',
//             reference_name: frm.doc.name,
//             allocated_to: frm.doc.custom_assign_to
//         },
//         fields: ['name'],
//         limit: 1
//     }).then(function(existing) {
//         if (existing && existing.length > 0) return;

//         const customer = frm.fields_dict['custom_customer']
//             ? (frm.doc.custom_customer || '') : '';
//         const quotation = frm.fields_dict['custom_quotation']
//             ? (frm.doc.custom_quotation || '') : '';

//         const description = `
//             <b>Reactive Maintenance Task</b><br>
//             <b>Asset:</b> ${frm.doc.asset_name || ''}<br>
//             <b>Item Code:</b> ${frm.doc.item_code || ''}<br>
//             <b>Item Name:</b> ${frm.doc.item_name || ''}<br>
//             <b>Task:</b> ${frm.doc.task_name || ''}<br>
//             <b>Maintenance Type:</b> ${frm.doc.custom_maintenance_types || ''}<br>
//             <b>Periodicity:</b> ${frm.doc.periodicity || ''}<br>
//             <b>Customer:</b> ${customer}<br>
//             <b>Quotation:</b> ${quotation}
//         `;

//         frappe.call({
//             method: 'frappe.client.insert',
//             args: {
//                 doc: {
//                     doctype: 'ToDo',
//                     status: 'Open',
//                     priority: 'Medium',
//                     allocated_to: frm.doc.custom_assign_to,
//                     description: description,
//                     reference_type: 'Asset Maintenance Log',
//                     reference_name: frm.doc.name,
//                     date: frappe.datetime.get_today()
//                 }
//             },
//             callback: function(response) {
//                 if (!response.exc) {
//                     frappe.show_alert({
//                         message: __('ToDo created for {0}', [frm.doc.custom_assign_to]),
//                         indicator: 'green'
//                     }, 5);
//                 }
//             }
//         });
//     });
// }
frappe.ui.form.on('Asset Maintenance Log', {

    refresh: function(frm) {
        set_maintenance_stock_filter(frm);
        apply_reactive_logic(frm);
        set_quotation_filter(frm);

        // ── Create Quotation button ──
        // Show only if: doc is saved (not new), not submitted, no quotation linked yet,
        // and status is NOT 'Quotation not reqd'
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

        // ── Only on submitted docs ──
        if (frm.doc.docstatus === 1) {

            // ── View Stock Entry button ──
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
    },

    // ── Auto-set status when Quotation is linked ─────────────────
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


// ── Child table: Stock Items For Asset ──
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


// ── Filter: only stock items in child table ──
function set_maintenance_stock_filter(frm) {
    frm.set_query('item_code', 'custom_items', function() {
        return { filters: { 'is_stock_item': 1 } };
    });
}


// ── Quotation filter by customer ──
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


// ── Fetch customer from Location.custom_customer ──
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


// ── Create Quotation from Asset Maintenance Log ──
function create_quotation_from_maintenance(frm) {
    do_create_quotation(frm);
}

function do_create_quotation(frm) {

    const asset = frm.doc.custom_asset_maintenance_type === 'Reactive'
        ? frm.doc.custom_asset
        : frm.doc.asset_name;

    if (!asset) {
        frappe.msgprint(__('No Asset found. Cannot create Quotation.'));
        return;
    }

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

            const customer = loc_val.custom_customer;

            const items = (frm.doc.custom_items || [])
                .filter(row => row.item_code)
                .map(row => ({
                    item_code: row.item_code,
                    qty: row.qty || 1,
                    uom: row.uom || row.stock_uom
                }));

            // ── Build the Quotation doc object ──────────────────────────
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

            // ── Save the Quotation via API ───────────────────────────────
            frappe.call({
                method: 'frappe.client.insert',
                args: { doc: quotation_doc },
                freeze: true,
                freeze_message: __('Creating Quotation...'),
                callback: function(r) {
                    if (r.exc || !r.message) return;

                    const quotation_id = r.message.name;

                    // ── Store Quotation ID + status back in Asset Maintenance Log ──
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

                            // ── Open the new Quotation form ──
                            frappe.set_route('Form', 'Quotation', quotation_id);
                        }
                    );
                }
            });
        });
    });
}


// ── Reactive: show/hide fields logic ──
function apply_reactive_logic(frm) {
    const is_reactive = frm.doc.custom_asset_maintenance_type === 'Reactive';

    const reactive_editable_fields = ['task_name'];

    if (is_reactive) {
        frm.set_df_property('asset_maintenance', 'hidden', 1);
        frm.set_df_property('asset_maintenance', 'reqd', 0);
        frm.set_df_property('task', 'hidden', 1);
        frm.set_df_property('task', 'reqd', 0);
        frm.set_df_property('custom_asset', 'hidden', 0);
        frm.set_df_property('custom_asset', 'reqd', 1);
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

        // ── Reactive: custom_maintenance_team & custom_name_of_task are shown,
        //              task_name is hidden ──
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

        // ── Planned (non-Reactive): custom_maintenance_team & custom_name_of_task
        //              are hidden, only task_name is shown ──
        frm.set_df_property('custom_maintenance_team', 'hidden', 1);
        frm.set_df_property('custom_maintenance_team', 'reqd', 0);
        frm.set_df_property('custom_name_of_task', 'hidden', 1);
        frm.set_df_property('custom_name_of_task', 'reqd', 0);
        frm.set_df_property('task_name', 'hidden', 0);
    }

    frm.refresh_fields();
}


// ── Reactive: create ToDo on save (no duplicates) ──
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