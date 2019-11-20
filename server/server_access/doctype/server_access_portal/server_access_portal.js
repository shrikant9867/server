// Copyright (c) 2019, Indictrans and contributors
// For license information, please see license.txt

frappe.ui.form.on('Server Access Portal', {
	refresh: function(frm) {
		 if (!frm.doc.__islocal) {		
		 		frm.set_df_property('time_period', 'read_only', 1);
				frm.set_df_property('server_ip', 'read_only', 1);
				frm.set_df_property('purpose', 'read_only', 1);
				frm.set_df_property('sudo_user_access', 'read_only', 1);
		}

	},
	onload: function(frm) {
		if (frm.doc.__islocal) {
				frm.set_value("username", frappe.session.user_fullname);
		 		frm.set_value("user_email", frappe.session.user);
		 }
	},
	server_ip: function(frm) {
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Servers",
				filters: {"ip_address": frm.doc.server_ip},
				fieldname: ["port","super_user"]
			},
			callback: function(r){
				frm.set_value("port", r.message.port);
				frm.set_value("super_user_name", r.message.super_user);				
			}
	  });
	}
});
