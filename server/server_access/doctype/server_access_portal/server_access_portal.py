# -*- coding: utf-8 -*-
# Copyright (c) 2019, Indictrans and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, os, sys, subprocess, getpass, json, multiprocessing, shutil, platform
from distutils.spawn import find_executable
from datetime import datetime
import paramiko, random, string
from frappe.model.document import Document
import re, smtplib, json
from frappe.utils import encode, nowdate, cstr, flt, cint, now, getdate,add_days,random_string
from dateutil import parser


passpharse = frappe.utils.random_string(length=12)
count = 1

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
def remove_user(filters):
	count = 1 
	data = ssh_to_user(filters,  count)
	data.update({'user_removed': 1 })
	return data

@frappe.whitelist()
def sudo_access_grant(filters):
	count = 2
	data = ssh_to_user(filters, count)
	data.update({'sudo_access_granted': 1})
	return data

def ssh_to_user(filters, count):
	try:
		filters = json.loads(filters)
		command_list_string = ''
		host_ip = filters.get('server_ip')
		response = subprocess.call(['ping','-c','1',host_ip])
		if response == 0:
			cwd = os.getcwd()
			path = cwd.replace('sites','apps/server/pulluser_indictrans_server')
			hostname = host_ip
			username = 's-a-p'
			port = filters.get('port')
			pkey_file = path
			if count == 1:
				command_list = remove_user_from_server(filters)
				cmd =command_list.get('cmd') 
			elif count == 2:
				command_list = sudo_privilege_granting(filters)
				print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@",command_list.get('cmd'))
				cmd = command_list.get('cmd')
				
			print("-=-=-=-=-=-=", command_list.get('cmd'))
			key = paramiko.RSAKey.from_private_key_file(pkey_file)
			s = paramiko.SSHClient()
			s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			s.load_system_host_keys()
			s.connect(str(hostname), str(port), str(username),pkey=key)
			print ("**********************3 *************", command_list.get('cmd'))
			stdin, stdout, stderr = s.exec_command(str(cmd))
			output = stdout.read()
			print ("========><======",output)
			s.close()
			return filters
			
		else:
			frappe.throw("Server IP is not Reachable:",host_ip)

	except Exception as e:
		raise e

def remove_user_from_server(filters):
	try:
		username = filters.get('username').replace(' ','')
		add_current_expiry_date = nowdate()
		userdel_cmd = "sudo pkill -KILL -u "+username+" && sudo usermod -e '"+add_current_expiry_date+"' "+username
		return { 'cmd': userdel_cmd }

	except Exception as e:
		raise e

def sudo_privilege_granting(filters):
	try:
		username = filters.get('username').replace(' ','')
		file = open("customalias.sh","w+")
		file1 = open("customsource.sh","w+")
		profile_condition = "if [ `whoami` == "+username+" ]; then 	source /etc/customalias.sh; fi"

		usermod_sudo_cmd = "sudo usermod -aG sudo "+username
		command_restriuction = "alias rm='echo remove contenet is restricted' \n alias poweroff='echo Poweroff is restricted' \n \
alias chmod='echo Change Permission is restristed' \n alias mysql='echo Change Permission is restristed' \n \
alias mv='echo Change Permission is restristed'\n alias rmdir='echo Change Permission is restristed' \n alias cp='echo Change Permission is restristed' \n \
alias chown='echo Change Permission is restristed' \n alias chgrp='echo Change Permission is restristed' \n alias kill='echo Change Permission is restristed' \n \
alias passwd='echo Change Permission is restristed' \n alias su='echo Change Permission is restristed' \n alias reboot='echo Change Permission is restristed' \n \
alias curl='echo Change Permission is restristed' \n alias diff='echo Change Permission is restristed' \n alias history='echo Change Permission is restristed'"
	
		file.write(command_restriuction)
		file1.write(profile_condition)
		os.system("chmod +x *.sh")
		cwd = os.getcwd()
		path = cwd.replace('sites','apps/server/pulluser_indictrans_server')
		scp_syntax = "sudo scp -rpi "+path+" -P "+filters.get('port')+"  "+cwd+"/customalias.sh  s-a-p@"+filters.get('server_ip')+":/home/s-a-p/."
		scp_syntax1 = "sudo scp -rpi "+path+" -P "+filters.get('port')+"  "+cwd+"/customsource.sh  s-a-p@"+filters.get('server_ip')+":/home/s-a-p/."
		print ("----------------------->",scp_syntax,scp_syntax1)
		os.system(scp_syntax)
		os.system(scp_syntax1)
		copy_files1 = "sudo scp -r customalias.sh /etc/."
		copy_files2 = "sudo scp -r customsource.sh /etc/profile.d/."

		single_command = usermod_sudo_cmd+";"+copy_files1+";"+copy_files2
		command_details = { 'cmd':single_command }
		return command_details

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

def supper_user_permission(user):
	server_access = frappe.db.get_values('Server Access Portal', {'support_email_id': user}, ['name','owner','support_email_id'], as_dict=1)
	if user!= 'Administrator':
		if len(server_access):
			if user!= server_access[0].get('owner'):
				return """ `tabServer Access Portal`.owner='{0}' and `tabServer Access Portal`.support_email_id='{1}' """.format(server_access[0].get('owner'), user)
		else:
			return """ `tabServer Access Portal`.owner='{0}' """.format(user) 	




	




