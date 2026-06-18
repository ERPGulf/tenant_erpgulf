// frappe.ui.form.on('Asset', {

//     onload: function(frm) {
//         console.log('=== ONLOAD ===');
//         if (frm.doc.location) {
//             load_rooms(frm);
//         }
//     },

//     refresh: function(frm) {
//         console.log('=== REFRESH ===');
//         if (frm.doc.location) {
//             load_rooms(frm);
//         }
//     },

//     // When Location selected
//     location: function(frm) {
//         console.log('=== LOCATION CHANGED ===');
//         console.log('Selected Location:', frm.doc.location);

//         // Clear room field
//         frm.set_value('custom_room_name', '');
//         frm.set_df_property('custom_room_name', 'options', '');
//         frm.refresh_field('custom_room_name');

//         if (!frm.doc.location) return;

//         load_rooms(frm);
//     }

// });


// // ─────────────────────────────────────────────────────────────
// // Load Room Names into Select dropdown
// // ─────────────────────────────────────────────────────────────
// function load_rooms(frm) {
//     console.log('--- load_rooms() called ---');
//     console.log('Fetching Location:', frm.doc.location);

//     frappe.db.get_doc('Location', frm.doc.location)
//         .then(function(doc) {

//             console.log('Location Doc:', doc);
//             console.log('All Keys:', Object.keys(doc));

//             // ── Find child table key ──
//             Object.keys(doc).forEach(function(key) {
//                 if (Array.isArray(doc[key])) {
//                     console.log('Array field found → ', key, doc[key]);
//                 }
//             });

//             // ── Use correct fieldname ──
//             let rooms = doc.room_equipment 
//                      || doc.custom_room_equipment 
//                      || [];

//             console.log('Rooms array:', rooms);
//             console.log('Total rooms:', rooms.length);

//             if (!rooms || rooms.length === 0) {
//                 console.warn('No rooms found!');
//                 frappe.show_alert({
//                     message: 'No rooms found for this Location.',
//                     indicator: 'orange'
//                 }, 4);
//                 return;
//             }

//             // ── Log each room ──
//             rooms.forEach(function(row, i) {
//                 console.log('Room ' + i + ':', row.room_name);
//             });

//             // ── Build options ──
//             let options = [''].concat(
//                 rooms.map(function(row) { 
//                     return row.room_name; 
//                 })
//             );

//             console.log('Options:', options);

//             // ── Check field exists ──
//             if (!frm.fields_dict['custom_room_name']) {
//                 console.error('Field custom_room_name NOT FOUND!');
//                 console.log('Available fields:', 
//                              Object.keys(frm.fields_dict));
//                 return;
//             }

//             // ── Set options into Select field ──
//             frm.set_df_property(
//                 'custom_room_name',
//                 'options',
//                 options.join('\n')
//             );

//             frm.refresh_field('custom_room_name');

//             // ── Verify ──
//             console.log('Options set successfully:', 
//                 frm.fields_dict['custom_room_name'].df.options
//             );

//             frappe.show_alert({
//                 message: rooms.length + ' rooms loaded.',
//                 indicator: 'green'
//             }, 3);

//         })
//         .catch(function(err) {
//             console.error('ERROR fetching Location:', err);
//         });
// }
frappe.ui.form.on('Asset', {

    onload: function(frm) {
        if (frm.doc.location) {
            // Pre-set the current value as a placeholder option
            // so validation doesn't reject it before async load
            if (frm.doc.custom_room_name) {
                frm.set_df_property(
                    'custom_room_name',
                    'options',
                    '\n' + frm.doc.custom_room_name  // ← inject saved value immediately
                );
                frm.refresh_field('custom_room_name');
            }
            load_rooms(frm);
        }
    },

    refresh: function(frm) {
        if (frm.doc.location) {
            if (frm.doc.custom_room_name) {
                frm.set_df_property(
                    'custom_room_name',
                    'options',
                    '\n' + frm.doc.custom_room_name  // ← same fix here
                );
                frm.refresh_field('custom_room_name');
            }
            load_rooms(frm);
        }
    },

    location: function(frm) {
        frm.set_value('custom_room_name', '');
        frm.set_df_property('custom_room_name', 'options', '');
        frm.refresh_field('custom_room_name');

        if (!frm.doc.location) return;
        load_rooms(frm);
    }

});


function load_rooms(frm) {
    frappe.db.get_doc('Location', frm.doc.location)
        .then(function(doc) {

            let rooms = doc.room_equipment
                     || doc.custom_room_equipment
                     || [];

            if (!rooms || rooms.length === 0) {
                frappe.show_alert({
                    message: 'No rooms found for this Location.',
                    indicator: 'orange'
                }, 4);
                return;
            }

            let options = [''].concat(
                rooms.map(function(row) {
                    return row.room_name;
                })
            );

            if (!frm.fields_dict['custom_room_name']) {
                console.error('Field custom_room_name NOT FOUND!');
                return;
            }

            // ── Now set the FULL options list (replaces the placeholder) ──
            frm.set_df_property(
                'custom_room_name',
                'options',
                options.join('\n')
            );

            frm.refresh_field('custom_room_name');

            frappe.show_alert({
                message: rooms.length + ' rooms loaded.',
                indicator: 'green'
            }, 3);

        })
        .catch(function(err) {
            console.error('ERROR fetching Location:', err);
        });
}