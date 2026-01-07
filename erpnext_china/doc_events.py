import frappe
from erpnext_china.chart_of_accounts.company_default.utils import set_company_default
from erpnext_china.chart_of_accounts.custom_accounts.custom_account import erpnext_china_create_charts


def company_after_insert(doc, method):
    doc.erpnext_china_in_insert = True    

def company_on_update(doc, method):
    if not frappe.db.sql(
        """select name from tabAccount
            where company=%s and docstatus<2 limit 1""",
        doc.name,
    ):
        if not frappe.local.flags.ignore_chart_of_accounts:
            frappe.flags.country_change = True
            frappe.local.flags.ignore_root_company_validation = True
            frappe.local.flags.ignore_chart_of_accounts = 1
            zelin_ac_create_charts(doc.name, doc.chart_of_accounts, doc.existing_company)

    if doc.get("erpnext_china_in_insert") and doc.chart_of_accounts and doc.country == "China":
        try:
            set_company_default(doc.name)
        except:            
            frappe.log_error("erpnext_china.doc_events.company_on_update set company default error")