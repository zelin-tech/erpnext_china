from . import __version__ as app_version

app_name = "erpnext_china"
app_title = "ERPNext China"
app_publisher = "yuxinyong"
app_description = "ERPNext China"
app_email = "yuxinyong@163.com"
app_license = "MIT"

after_install = "erpnext_china.setup.install.after_install"

setup_wizard_requires = "assets/erpnext_china/js/setup_wizard.js"

doctype_js = {
     "Purchase Order" : "public/js/purchase_order.js",
     "Sales Order" : "public/js/sales_order.js",
	"Sales Invoice" : "public/js/sales_invoice.js",
}

override_whitelisted_methods = {
    "erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts.get_charts_for_country": 
         "erpnext_china.chart_of_accounts.custom_accounts.custom_account.get_charts_for_country",
    "erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts.get_chart": 
         "erpnext_china.chart_of_accounts.custom_accounts.custom_account.get_chart",
	"erpnext.accounts.utils.get_coa": "erpnext_china.chart_of_accounts.custom_accounts.custom_account.get_coa",
	"frappe.desk.treeview.get_all_nodes": "erpnext_china.chart_of_accounts.custom_accounts.custom_account.get_all_nodes",
}

doc_events = {
    "Company": {
 		"on_update": "erpnext_china.doc_events.company_on_update",
		"after_insert": "erpnext_china.doc_events.company_after_insert"
	}
}