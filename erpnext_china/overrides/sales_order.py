from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
from erpnext_china.overrides.base import ChineseMoneyMixin


class CustomSalesOrder(ChineseMoneyMixin, SalesOrder):
    pass