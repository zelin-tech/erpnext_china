import frappe
from frappe import _


def execute(filters=None):
    columns = get_column()
    data = get_data(filters)
    return columns, data

def get_column():
    return [
        {
            "label": _("Account Number"),
            "fieldname": "account_number",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "label": _("Account"),
            "fieldname": "account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 360,
        }
    ]

def get_data(filters):
    accounts = frappe.get_all("Account", 
        filters = {
            "company": filters.company,
            "report_type": "Balance Sheet" if filters.report == "BS" else "Profit and Loss",
            "disabled": 0
        },
        fields = ["account_number", "name as account", "is_group", "lft", "rgt"]
    )
    account_number_set = set()
    doctype = "Balance Sheet Settings Item" if filters.report == "BS" else "Profit and Loss Statement Settings Item"
    if doctype == "Balance Sheet Settings Item":
        account_number_in_report = frappe.get_all(doctype,
            or_filters = {
                "lft_calc_type": "Closing Balance",
                "rgt_calc_type": "Closing Balance",
            },
            fields=[
                "lft_calc_sources",          
                "rgt_calc_sources"
            ]
        )
        for row in account_number_in_report:
            for value in [row.lft_calc_sources, row.rgt_calc_sources]:
                if value:
                    for num in value.split(','):
                        num = num.strip().lstrip('-')  
                        account_number_set.add(num)
    else:
        account_number_in_report = frappe.get_all(doctype,
            filters = {
                "calc_type": "Closing Balance"
            },
            fields=["calc_sources"]
        )        
        for row in account_number_in_report:
            value = row.calc_sources
            if value:
                for num in value.split(','):   
                    num = num.strip().lstrip('-')         
                    account_number_set.add(num)
    group_accts_in_report = [row for row in accounts if row.is_group and row.account_number in account_number_set]

    def is_group_account_in_report(row):
        for group_acct in group_accts_in_report:
            if row.lft > group_acct.lft and row.rgt < group_acct.rgt:
                return True

    missing_accounts = []
    for row in accounts:
        if (
            not row.is_group and 
            not row.account_number in account_number_set and 
            not is_group_account_in_report(row)
        ):
            missing_accounts.append(row)

    return missing_accounts