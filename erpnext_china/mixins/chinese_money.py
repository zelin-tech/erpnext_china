from erpnext.selling.doctype.sales_order.sales_order import SalesOrder

import frappe
from decimal import Decimal

from erpnext_china.utils import cncurrency


class CustomSalesOrder(SalesOrder):

    def set_total_in_words(self):

        frappe.throw("CustomSalesOrder 生效了")