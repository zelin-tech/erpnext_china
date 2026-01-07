from erpnext.accounts.doctype.account.chart_of_accounts import chart_of_accounts
from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import (
    get_chart as original_get_chart
)
from erpnext_china.chart_of_accounts.custom_accounts.custom_account import get_chart

def erpnext_china_get_chart(chart_template, existing_company=None):
    # 标准科目表直接调用源方法
    if chart_template in ["Standard", "Standard with Numbers"]:
        return original_get_chart(chart_template, existing_company)
    
    return get_chart(chart_template, existing_company)

chart_of_accounts.get_chart = erpnext_china_get_chart