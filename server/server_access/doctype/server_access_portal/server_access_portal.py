# -*- coding: utf-8 -*-
# Copyright (c) 2019, Indictrans and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, os, sys, subprocess, getpass, json, multiprocessing, shutil, platform
from distutils.spawn import find_executable
from datetime import datetime
import paramiko, random, string
from frappe.model.document import Document
import re, smtplib
from frappe.utils import encode, nowdate, cstr, flt, cint, now, getdate,add_days,random_string
from dateutil import parser


passpharse = frappe.utils.random_string(length=12)


class ServerAccessPortal(Document):
	def validate(self):
		days=5
		user_exp_date = parser.parse(self.time_period).date()
		expiry_date = add_days(nowdate(),days)
		expiry_date = parser.parse(expiry_date).date()

		
		if user_exp_date > expiry_date:
			frappe.throw("<b>Expiry Date</b> should not more than 5 Days")
		
		if user_exp_date == parser.parse(nowdate()).date():
			between_date = add_days(nowdate(),1)
			between_date = parser.parse(between_date).date()
			frappe.throw("<b>Expiry Date</b> should not Today's date,Please \
				Add Expiry Date between <b>'"+str(between_date)+"' to '"+str(expiry_date)+"'</b>")

		if not self.sudo_request_to_support and self.sudo_user_access:
			frappe.throw("Please Provide Support ID")

		if self.sudo_request_to_support:
			emp_details = frappe.db.get_values("Employee",{"name": self.sudo_request_to_support},["user_id","employee_name"], as_dict=1)
			if emp_details[0].get('employee_name') == self.username:
				frappe.throw("<b>You can't Send Sudo Access Request to Self, Send it to Other Support Member</b>")
	
	def create_user_command(self):
		username  = self.username.replace(' ','')
		password = frappe.utils.random_string(length=12)
		expiry_date  = self.time_period
		if self.duplicate_record:
			useradd_cmd = "sudo usermod -e '"+expiry_date+"' "+username
		else:
			useradd_cmd = "sudo useradd -me '"+expiry_date+"' "+username

		passwd_cmd = "echo "+username+":"+password+" > secrets.txt && sudo chpasswd < secrets.txt && sudo chsh -s /bin/bash "+username
		pem_cmd  = self.pem_file_creation(password, username)
		cmd_list = [useradd_cmd ,passwd_cmd, pem_cmd]
		user_details = { 'cmd': cmd_list , 'password': password }
		return user_details

	def before_insert(self):
		user  = frappe.db.get_values("Server Access Portal", {"username": self.username}, ["username"])
		if user:
			self.duplicate_record = 1
		else:
			self.duplicate_record = 0

	def pem_file_creation(self, password, username):
		if self.duplicate_record:
			cmd = "echo 'y' | sudo ssh-keygen -b 2048 -f "+username+" -t rsa -N "+passpharse
		else:
			cmd = "sudo ssh-keygen -b 2048 -f "+username+" -t rsa -N "+passpharse
		os.system(cmd)
		permission_public_key = username+".pub"
		os.system("sudo chmod -R 777 "+permission_public_key+" "+username)
		path_pem = os.getcwd()
		private_key_path = path_pem+"/"+username
		public_key_path = path_pem+"/"+username+".pub"
		pub_key_data = open(permission_public_key,"r+")
		publickeydata = pub_key_data.read()
		pem_file_cmd = "cd /home/"+username+" && [ -d .ssh ] || sudo mkdir .ssh && cd .ssh && sudo touch authorized_keys && sudo chmod -R 777 authorized_keys && sudo chown -R "+username+":"+username+" /home/"+username+"/.ssh/. && echo '"+publickeydata+"' > authorized_keys && sudo chmod -R 764 authorized_keys"
		return pem_file_cmd

	def sendMailtoUser(self, command_list_string, password):
		try:
			username  = self.username.replace(' ','')
			path = os.getcwd()
			publicfile = username+".pub" 
			publickeyfile = path+"/"+username+".pub"
			privatekeyfile = path+"/"+username
			with open(encode(publickeyfile), 'r') as f:
				    Publiccontent = f.read()

			with open(encode(privatekeyfile), 'r') as f:
				    Privatecontent = f.read()	    


			attachments = [{
						'fname': username,
						'fcontent': Privatecontent,
					},
					{
					'fname': publicfile,
					'fcontent':Publiccontent
					}]
			if len(command_list_string):
				frappe.sendmail(
						subject='Server Access Details',
						recipients= self.user_email,
						message=frappe.render_template(
							"templates/user-Details.html",{"data":self , "username": username, "passpharse": passpharse}),
						now=True,
						attachments= attachments
					)
			if self.sudo_user_access:
				if len(self.sudo_request_to_support):
					emp_email = frappe.db.get_values("Employee",{"name": self.sudo_request_to_support},["user_id","employee_name"], as_dict=1)
					frappe.sendmail(
							subject='Server Access Details',
							recipients= emp_email[0].get('user_id'),
							message=frappe.render_template(
								"templates/sudo_access_request.html",{"data":self , "username": username, "password": password, "support_name": emp_email[0].get('employee_name')}),
							now=True
						)

		except Exception as e:
			raise e
		
	def server_sshfunction(self):
		try:
			command_list_string = ''
			host_ip = self.server_ip
			response = subprocess.call(['ping','-c','1',host_ip])
			if response == 0:
				cwd = os.getcwd()
				path = cwd.replace('sites','apps/server/pulluser_indictrans_server')
				hostname = host_ip
				username = 's-a-p'
				port = self.port
				pkey_file = path
				command_list = self.create_user_command()
				for i in command_list.get('cmd'):
					command_list_string = command_list_string+";"+i
				key = paramiko.RSAKey.from_private_key_file(pkey_file)
				s = paramiko.SSHClient()
				s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
				s.load_system_host_keys()
				s.connect(str(hostname), str(port), str(username),pkey=key)
				print ("**********************2 *************", command_list_string[1:])
				stdin, stdout, stderr = s.exec_command(str(command_list_string[1:]))
				output = stdout.read()
				print ("========><======",output)
				s.close()
				self.sendMailtoUser(command_list_string, command_list.get('password') )						
				
			else:
				frappe.throw("Server IP is not Reachable:",host_ip)

		except Exception as e:
			raise e

	def after_insert(self):
		try:
			self.server_sshfunction()
		except Exception as e:
			raise e
					

    
@frappe.whitelist()
def get_support_member(doctype,text,searchfields,start,pagelen,filters):
	return frappe.db.sql(""" 
		select 
			name,employee_name
		from
			`tabEmployee`
		where
			designation='{designation}'		
		""".format( designation = filters.get('Designation')))

		

	




