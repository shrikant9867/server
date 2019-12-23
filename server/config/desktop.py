# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"module_name": "The GateKeeper",
			"color": "grey",
			"icon": "octicon octicon-key",
			"type": "module",
			"label": _("Server-Access")
		}
	]
