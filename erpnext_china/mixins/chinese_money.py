import frappe
from decimal import Decimal

from erpnext_china.utils import cncurrency


class ChineseMoneyMixin:

    def set_total_in_words(self):

        if frappe.local.lang and frappe.local.lang.startswith("zh"):

            amount = self.rounded_total or self.grand_total
            base_amount = self.base_rounded_total or self.base_grand_total

            self.in_words = cncurrency(
                Decimal(str(amount)),
                prefix=True
            )

            self.base_in_words = cncurrency(
                Decimal(str(base_amount)),
                prefix=True
            )

        else:
            super().set_total_in_words()