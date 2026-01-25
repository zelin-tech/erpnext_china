# Copyright (c) 2023, Vnimy and contributors
# For license information, please see license.txt

import os
import frappe
from frappe import _
from frappe.model.document import Document
from erpnext_china.erpnext_china.doctype.profit_and_loss_statement_settings.profit_and_loss_statement_settings import (
	validate_report_settings
)


class BalanceSheetSettings(Document):
	@frappe.whitelist()
	def get_example_data(self):
		return frappe.get_file_json(os.path.join(os.path.dirname(__file__), "example_data.json"))

	def validate(self):
		validate_report_settings(self)