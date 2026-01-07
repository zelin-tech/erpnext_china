# Copyright (c) 2023, Vnimy and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

import os

class ProfitandLossStatementSettings(Document):
	@frappe.whitelist()
	def get_example_data(self):
		return frappe.get_file_json(os.path.join(os.path.dirname(__file__), "example_data.json"))

	def validate(self):
		self.check_duplicate_account_number()

	def check_duplicate_account_number(self):

		def check_one_row(row, check_row):
			if row.name == check_row.name:
				return
			if row.calc_type == "Closing Balance" and row.calc_sources:
				for account_number in row.calc_sources.split(','):
					check_account_number(account_number, check_row)			

		def check_account_number(account_number, check_row):
			if (account_number and check_row.calc_type == "Closing Balance" 
				and check_row.calc_sources
				and account_number in check_row.account_numbers
			):
				frappe.msgprint(_("row {0} account number {1} already in row {2}").format(
					row.idx, account_number, check_row.idx
				))
			
		all_rows = []
		for row in self.items:
			if (row.calc_type == "Closing Balance" and row.calc_sources):
				row.account_numbers = set(row.calc_sources.split(','))
			all_rows.append(row)	
		for row in self.items:
			for check_row in all_rows:
				check_one_row(row, check_row)				