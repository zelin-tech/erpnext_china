# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import json
import os

import frappe
from erpnext.setup.setup_wizard.operations import taxes_setup
from erpnext.setup.setup_wizard.operations.taxes_setup import setup_taxes_and_charges


def erpnext_china_setup_taxes_and_charges(company_name: str, country: str):
	chart_of_accounts = frappe.db.get_value("Company", company_name, "chart_of_accounts")
	china_coa = ["一般企业会计准则(2024)", "小企业会计准则(2024)", "小企业会计准则", "民间非营利组织会计制度(2025)"]
	if chart_of_accounts and chart_of_accounts in china_coa and country == 'China':
		return

	setup_taxes_and_charges(company_name, country)

taxes_setup.setup_taxes_and_charges = erpnext_china_setup_taxes_and_charges