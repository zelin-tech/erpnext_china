# Copyright (c) 2023, 杨嘉祥 and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import DocType, Criterion
from frappe.query_builder.functions import Sum, Round
from frappe.utils import cint, cstr, flt, getdate, datetime, get_first_day, get_last_day, formatdate, nowdate
from erpnext.accounts.utils import FiscalYearError,get_fiscal_year,get_currency_precision


def execute(filters=None):
  validate_filters(filters)
  columns = get_columns(filters)

  settings = frappe.get_single("Profit and Loss Statement Settings")
  fields = ['idx','label','indent','calc_type','calc_sources','amount_from']
  #globals().update(locals())
  if not settings.items:
    form_link = frappe.utils.get_link_to_form("Profit and Loss Statement Settings",'')
    frappe.msgprint(_("请先进行利润表{0}设置").format(form_link))
    return
  data = [frappe._dict({f:d.get(f) for f in fields}) for d in settings.items]      
  data = get_data(data, filters)

  return columns, data

def validate_filters(filters):
  if not filters.fiscal_year:
    frappe.throw(_("Fiscal Year {0} is required").format(filters.fiscal_year))

  fiscal_year = frappe.db.get_value(
      "Fiscal Year", filters.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
  )
  if not fiscal_year:
    frappe.throw(
        _("Fiscal Year {0} does not exist").format(filters.fiscal_year))
  else:
    filters.year_start_date = getdate(fiscal_year.year_start_date)
    filters.year_end_date = getdate(fiscal_year.year_end_date)

  if filters.month:
    year = frappe.db.get_value('Fiscal Year', fiscal_year,'year_start_date').year
    filters.from_date = get_first_day(datetime.date(
        year=year, month=cint(filters.month), day=1))
    filters.to_date = get_last_day(datetime.date(
        year=year, month=cint(filters.month), day=1))
  else:
    filters.from_date = filters.year_start_date
    filters.to_date = filters.year_end_date

  filters.from_date = getdate(filters.from_date)
  filters.to_date = getdate(filters.to_date)

  if filters.from_date > filters.to_date:
    frappe.throw(_("From Date cannot be greater than To Date"))

  if (filters.from_date < filters.year_start_date) or (filters.from_date > filters.year_end_date):
    frappe.msgprint(
        _("From Date should be within the Fiscal Year. Assuming From Date = {0}").format(
            formatdate(filters.year_start_date)
        )
    )

    filters.from_date = filters.year_start_date

  if (filters.to_date < filters.year_start_date) or (filters.to_date > filters.year_end_date):
    frappe.msgprint(
        _("To Date should be within the Fiscal Year. Assuming To Date = {0}").format(
            formatdate(filters.year_end_date)
        )
    )
    filters.to_date = filters.year_end_date

def get_acc_nums(filters, data):
  """
    # source: -5001,5051=>  {acc_nums:[5001,5051], minus_factor:[-1,1]}
  """
  accounts = frappe.get_all('Account', 
    fields = ['account_number','lft','rgt','is_group','parent_account', 'root_type'],
    filters = {
      'company': filters.company
      #'root_type': ('in',('Income', 'Expense'))
    }
  )
  account_number_map = {acc.account_number:acc for acc in accounts}

  acc_nums = []
  for d in data:
    if d.calc_type and d.calc_sources and d.calc_type == "Closing Balance":       
      splitted_nums = list(filter(None, d.calc_sources.split(",")))
      #globals().update(locals())
      d.acc_nums = [f[1:] if f and f[0] == '-' else f for f in splitted_nums]
      d.minus_factor = [-1 if f and f[0] == '-' else 1 for f in splitted_nums]
      acc_nums.extend(d.acc_nums)
      d.accounts = [account_number_map.get(acc_num) for acc_num in d.acc_nums]

  parent_children_map = {}
  non_group_acc_nums = []
  for acc_num in acc_nums:
    account = account_number_map.get(acc_num)
    if account and account.is_group:
      child_account_nums = [acc.account_number for acc in accounts
         if acc.is_group == 0 and acc.lft > account.lft and acc.rgt < account.rgt]
      parent_children_map[acc_num] = child_account_nums
      non_group_acc_nums.extend(child_account_nums)
    else:
      non_group_acc_nums.append(acc_num)

  return non_group_acc_nums, parent_children_map

def get_data(data, filters):
  """
  1. 获取利润表设置明细中计算方式为期末余额的科目号清单
    1.1 获取每个父科目号的下层记账科目号清单
    1.2 剔除科目号负号前缀
  2. 获取当月以及年初到当月底记帐科目会计凭证小计金额  
  3. 获取利润表设置明细行计算方式为期末余额的汇总金额
     3.1 获取记账科目小计
     3.2 获取父科目小计（下层记账科目汇总)
     3.3 处理科目号负号前缀
     3.4 收入科目自动*-1
  4. 获取利润表设置明细行计算方式为计算公式的汇总金额  
  """

  def get_amount(amount_map, acc_num, amount_from=None):
    return amount_map.get(acc_num, {}).get(amount_from or 'balance', 0)

  acc_nums, parent_children_map = get_acc_nums(filters, data)
  monthly_amount_map = get_balance_on(company=filters.company, date=filters.to_date, 
    start_date = filters.from_date,account_numbers = acc_nums)
  if filters.year_start_date == filters.from_date:
    month_end_amount_map = monthly_amount_map
  else:
    month_end_amount_map = get_balance_on(company=filters.company, date=filters.to_date,
      start_date = filters.year_start_date,account_numbers = acc_nums)
  rows_map = {}
  for d in data:
    d.amount, d.month_end_amount = 0, 0
    if d.calc_type and d.calc_sources and d.calc_type == "Closing Balance":
      row_monthly_amount, row_month_end_amount = 0, 0
      for (i,account) in enumerate(d.accounts):
        if not account: continue
        acc_num = account.account_number
        minus_factor = d.minus_factor[i]
        children = parent_children_map.get(acc_num)
        monthly_amount, month_end_amount = 0, 0
        if not account.is_group:        
          monthly_amount = get_amount(monthly_amount_map, acc_num, d.amount_from) * minus_factor
          month_end_amount = get_amount(month_end_amount_map, acc_num, d.amount_from) * minus_factor
        elif children:
          for child in children:
            monthly_amount += get_amount(monthly_amount_map,child, d.amount_from) * minus_factor
            month_end_amount += get_amount(month_end_amount_map, child, d.amount_from) * minus_factor
        if account.root_type == "Income":
          monthly_amount *= -1
          month_end_amount *= -1
        row_monthly_amount += monthly_amount
        row_month_end_amount += month_end_amount
      d.amount = row_monthly_amount
      d.month_end_amount = row_month_end_amount

    rows_map[cstr(d.idx)]= {          
        "amount": d.amount,
        "month_end_amount": d.month_end_amount
    }     

  for d in data:
    if d.calc_type and d.calc_sources and d.calc_type == "Calculate Rows":
      splitted_rows = list(filter(None, d.calc_sources.split(",")))
      #globals().update(locals())
      d.acc_nums = [f[1:] if f and f[0] == '-' else f for f in splitted_rows]
      d.minus_factor = [-1 if f and f[0] == '-' else 1 for f in splitted_rows]      
      monthly_amount, month_end_amount = 0, 0
      for (i, row_num) in enumerate(d.acc_nums):
        minus_factor = d.minus_factor[i]        
        row = rows_map.get(cstr(row_num))
        if row is None:
          # 如果找不到该行，打印一个日志或提示，跳过此数值
          frappe.throw(_("Row {0} refers to non-existent row {1}").format(d.idx, row_num))

        monthly_amount += row.get("amount", 0.0) * minus_factor
        print(i, row_num, monthly_amount)
        month_end_amount += row.get("month_end_amount", 0.0) * minus_factor
      d.amount = monthly_amount
      d.month_end_amount = month_end_amount  
      rows_map[cstr(d.idx)] = {          
          "amount": d.amount,
          "month_end_amount": d.month_end_amount
      }

  return data

def get_columns(filters):
  columns = [
      {
          "label": "项目",
          "fieldname": "label",
          "fieldtype": "Data",
          "width": 300,
      },
      {
          "label": "行次",
          "fieldname": "idx",
          "fieldtype": "Int",
          "width": 60,
      },
      {
          "label": "金额",
          "fieldname": "amount",
          "fieldtype": "Currency",
          "width": 140,
      }
  ]

  if filters.month:
    columns.extend([
        {
            "label": "月底累计数",
            "fieldname": "month_end_amount",
            "fieldtype": "Currency",
            "width": 140,
        }
    ])

  return columns

@frappe.whitelist()
def get_balance_on(
    account=None, date=None, party_type=None, party=None, company=None,
    in_account_currency=False, cost_center=None, ignore_account_permission=True,
    account_type=None, start_date=None, account_numbers=[], 
    with_period_closing_entry=None, debug=False
):
    # --- 1. 参数与基础定义 (严格对应) ---
    account = account or frappe.form_dict.get("account")
    date = date or frappe.form_dict.get("date") or nowdate()
    party_type = party_type or frappe.form_dict.get("party_type")
    party = party or frappe.form_dict.get("party")
    cost_center = cost_center or frappe.form_dict.get("cost_center")

    gle = DocType("GL Entry")
    acc_tab = DocType("Account")
    cc_tab = DocType("Cost Center")
    
    query = frappe.qb.from_(gle).where(gle.is_cancelled == 0)

    # --- 2. 条件构造 (严格对应 cond.append) ---
    if not with_period_closing_entry:
        query = query.where(gle.voucher_type != "Period Closing Voucher")
    
    if start_date:
        query = query.where(gle.posting_date >= start_date)
    
    if date:
        query = query.where(gle.posting_date <= date)

    if company:
        query = query.where(gle.company == company)

    # --- 3. 成本中心逻辑 ---
    report_type = ""
    if account:
        acc_doc = frappe.get_doc("Account", account)
        report_type = acc_doc.report_type

    if cost_center and report_type == "Profit and Loss":
        cc = frappe.get_doc("Cost Center", cost_center)
        if cc.is_group:
            subq = (frappe.qb.from_(cc_tab).select(1)
                    .where(cc_tab.name == gle.cost_center)
                    .where(cc_tab.lft >= cc.lft)
                    .where(cc_tab.rgt <= cc.rgt))
            query = query.where(Criterion.exists(subq))
        else:
            query = query.where(gle.cost_center == cost_center)

    # --- 4. 科目逻辑 ---
    if account:
        if not (frappe.flags.ignore_account_permission or ignore_account_permission):
            acc_doc.check_permission("read")
        
        if acc_doc.is_group:
            subq_acc = (frappe.qb.from_(acc_tab).select(acc_tab.name)
                        .where(acc_tab.name == gle.account)
                        .where(acc_tab.lft >= acc_doc.lft)
                        .where(acc_tab.rgt <= acc_doc.rgt))
            query = query.where(Criterion.exists(subq_acc))
            
            if acc_doc.account_currency == frappe.get_cached_value("Company", acc_doc.company, "default_currency"):
                in_account_currency = False
        else:
            query = query.where(gle.account == account)

    if account_type:
        accounts_list = frappe.db.get_all("Account", filters={"company": company, "account_type": account_type, "is_group": 0}, pluck="name")
        query = query.where(gle.account.isin(accounts_list))

    if party_type and party:
        query = query.where(gle.party_type == party_type).where(gle.party == party)

    # --- 5. 核心 Select 逻辑 (精确复制源码的字段切换) ---
    precision = get_currency_precision()
    
    # 定义基础借贷字段
    d_fld = gle.debit_in_account_currency if in_account_currency else gle.debit
    c_fld = gle.credit_in_account_currency if in_account_currency else gle.credit

    if account_numbers:
        # 对应源码: select_field = "acct.account_number, sum(round(debit, %s)), sum(round(credit, %s)) "
        query = query.inner_join(acc_tab).on(gle.account == acc_tab.name)
        query = query.where(acc_tab.account_number.isin(account_numbers))
        query = query.select(
            acc_tab.account_number,
            Sum(Round(d_fld, precision)),
            Sum(Round(c_fld, precision))
        )
        query = query.groupby(acc_tab.account_number)
    else:
        # 对应源码: select_field = "sum(round(debit, %s)) - sum(round(credit, %s))" 或 "sum(round(debit, %s)), sum(round(credit, %s))"
        # 源码中如果没有 account_numbers，它直接计算了差值返回单列
        # 为了适配最后的字典推导式 b[0], b[1], b[2]，这里必须严格按源码 sql 的 select 内容执行
        if account or (party_type and party) or account_type:
            # 源码逻辑：如果不带 account_numbers，select 只有一个表达式 (sum - sum)
            query = query.select(Sum(Round(d_fld, precision)) - Sum(Round(c_fld, precision)))
        else:
            # 兜底选择（原 SQL 默认行为）
            query = query.select(Sum(Round(d_fld, precision)) - Sum(Round(c_fld, precision)))

    # --- 6. 执行与结果处理 (1:1 复制源码推导式) ---
    bal = query.run(debug=debug)

    if bal:
        # 严格执行源码的 result 构造逻辑
        # 注意：源码中如果只有一列，b[1] 和 b[2] 会报错，这说明原函数在非 account_numbers 模式下
        # 走的是 get_balance_on 的原始单值返回路径。
        # 既然你要精确复制这个 whitelist 函数，逻辑如下：
        if account_numbers:
            result = frappe._dict({
                b[0]: {
                    'Debit': b[1],
                    'Credit': b[2],
                    'Balance': b[1] - b[2]
                }
                for b in bal
            })
        else:
            # 原源码在没有 account_numbers 时返回的是单值数字
            # 但你要求的是精确复制你给出的这段代码的行为：
            result = flt(bal[0][0]) if bal else 0.0
    else:
        result = {} if account_numbers else 0.0

    return result


"""
for testing
from erpnext_china.erpnext_chinacounting.report.fin_profit_and_loss_statement.fin_profit_and_loss_statement import *
filters = frappe._dict({"company":"则霖信息技术（深圳）有限公司","fiscal_year":"2024","month":"2"})
validate_filters(filters)
columns = get_columns(filters)
settings = frappe.get_single("Profit and Loss Statement Settings")
fields = ['idx','label','indent','calc_type','calc_sources','amount_from']
globals().update(locals())
data = [frappe._dict({f:d.get(f) for f in fields}) for d in settings.items]   
data = get_data(data, filters)
"""