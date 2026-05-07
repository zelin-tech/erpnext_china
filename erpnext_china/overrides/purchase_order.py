from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder
from erpnext_china.overrides.base import ChineseMoneyMixin


class CustomPurchaseOrder(ChineseMoneyMixin, PurchaseOrder):
    pass
