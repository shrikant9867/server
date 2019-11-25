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
		if (frm.doc.__islocal) {
			frm.set_df_property('sudo_request_to_support', 'hidden', 1);
		}

	},
	onload: function(frm) {
		if (frm.doc.__islocal) {
				frm.set_value("username", frappe.session.user_fullname);
		 		frm.set_value("user_email", frappe.session.user);
		 		frm.set_value("sudo_request_to_support", "");
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
	},
	sudo_request_to_support: function(frm) {
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Employee",
				filters: {"name": frm.doc.sudo_request_to_support, "designation": "Technical Support Engineer"},
				fieldname: "user_id"
			},
			async: false,
			callback: function(r) {
				frm.set_value("support_email_id", r.message.user_id);
			}
		});
		
	},
	sudo_user_access: function(frm) {
		if(cur_frm.doc.sudo_user_access == 1){
			frm.set_df_property('sudo_request_to_support', 'hidden', 0);
			// frm.set_df_property('sudo_request_to_support', 'reqd', 1);
		}
		else{
			frm.set_df_property('sudo_request_to_support', 'hidden', 1);
			// frm.set_df_property('sudo_request_to_support', 'reqd', 0);
		}
	}
});
cur_frm.fields_dict['sudo_request_to_support'].get_query = function(doc) {
	var query = "";
	query = "server.server_access.doctype.server_access_portal.server_access_portal.get_support_member"
	return {
		"query": query,
		filters: {'Designation': "Technical Support Engineer" }
	}
}