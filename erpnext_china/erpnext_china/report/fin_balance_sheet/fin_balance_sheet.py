# Copyright (c) 2023, 杨嘉祥 and contributors
# For license information, please see license.txt

import inspect
import frappe
from frappe import _
from frappe.query_builder import DocType, Order
from frappe.query_builder.functions import Sum, Round
from frappe.utils import cint, cstr, flt, getdate, datetime, get_first_day, get_last_day, formatdate, add_days
from erpnext.accounts.utils import get_balance_on

def execute(filters):
  if filters.show_all_months:
    return BalanceSheetSingleColumn(filters).run()
  else:
    return BalanceSheetDoubleColumns(filters).run()

def get_accounts_data(company, root_types=None):
    """
    共用获取科目方法
    :param root_types: 列表类型，例如 ['Asset', 'Liability', 'Equity']。如果为 None 则查全部。
    """
    acc = DocType("Account")
    parent = DocType("Account").as_("parent")

    query = (
        frappe.qb.from_(acc)
        .left_join(parent).on(parent.name == acc.parent_account)
        .select(
            acc.name,
            acc.account_number,
            parent.account_number.as_("parent_number"),
            acc.parent_account,
            acc.account_name,
            acc.root_type,
            acc.report_type,
            acc.lft,
            acc.rgt
        )
        .where(acc.company == company)
    )

    # 动态添加过滤条件
    if root_types:
        query = query.where(acc.root_type.isin(root_types))

    return query.orderby(acc.lft).run(as_dict=True)

class BalanceSheetDoubleColumns():
  def __init__(self, filters=None):
    self.filters = frappe._dict(filters)
    self.validate_filters()

  def run(self):
    self.get_columns()

    settings = frappe.get_single("Balance Sheet Settings")
    if not settings.items:
      form_link = frappe.utils.get_link_to_form("Balance Sheet Settings",'')
      frappe.msgprint(_("请先进行资产负债表（两栏式）{0}设置").format(form_link))
      return    

    self.data = list(map(lambda d: frappe._dict({
        "idx": d.idx,
        "lft_empty": d.lft_empty,
        "lft_bold": d.lft_bold,
        "lft_name": d.lft_name,
        "lft_indent": d.lft_indent,
        "lft_calc_type": d.lft_calc_type,
        "lft_calc_sources": d.lft_calc_sources,
        "rgt_empty": d.rgt_empty,
        "rgt_bold": d.rgt_bold,
        "rgt_name": d.rgt_name,
        "rgt_indent": d.rgt_indent,
        "rgt_calc_type": d.rgt_calc_type,
        "rgt_calc_sources": d.rgt_calc_sources,
    }), settings.items))

    self.get_data()

    currency = self.filters.presentation_currency or frappe.get_cached_value(
        "Company", self.filters.company, "default_currency"
    )

    report_summary = self.get_report_summary(
        asset_row=settings.asset_row,
        liability_row=settings.liability_row,
        equity_row=settings.equity_row,
        currency=currency,
    )

    return self.columns, self.data, None, None, report_summary


  def validate_filters(self):
    self.company = self.filters.company
    if not self.filters.fiscal_year:
      frappe.throw(_("Fiscal Year {0} is required").format(self.filters.fiscal_year))
    self.fiscal_year = self.filters.fiscal_year

    fiscal_year = frappe.db.get_value(
      "Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
    )
    if not fiscal_year:
      frappe.throw(_("Fiscal Year {0} does not exist").format(self.fiscal_year))
    else:
      self.year_start_date = getdate(fiscal_year.year_start_date)
      self.year_end_date = getdate(fiscal_year.year_end_date)


    if self.filters.month:
      year = frappe.db.get_value('Fiscal Year', self.fiscal_year,'year_start_date').year
      self.filters.from_date = get_first_day(datetime.date(year=year, month=cint(self.filters.month), day=1))
      self.filters.to_date = get_last_day(datetime.date(year=year, month=cint(self.filters.month), day=1))
    else:
      self.filters.from_date = self.year_start_date
      self.filters.to_date = self.year_end_date

    self.filters.from_date = getdate(self.filters.from_date)
    self.filters.to_date = getdate(self.filters.to_date)

    if self.filters.from_date > self.filters.to_date:
      frappe.throw(_("From Date cannot be greater than To Date"))

    if (self.filters.from_date < self.year_start_date) or (self.filters.from_date > self.year_end_date):
      frappe.msgprint(
        _("From Date should be within the Fiscal Year. Assuming From Date = {0}").format(
          formatdate(self.year_start_date)
        )
      )

      self.filters.from_date = self.year_start_date

    if (self.filters.to_date < self.year_start_date) or (self.filters.to_date > self.year_end_date):
      frappe.msgprint(
        _("To Date should be within the Fiscal Year. Assuming To Date = {0}").format(
          formatdate(self.year_end_date)
        )
      )
      self.filters.to_date = self.year_end_date


  def get_report_summary(
      self,
      asset_row,
      liability_row,
      equity_row,
      currency,
  ):
    if not self.data:
      return None

    row_map = {}
    for d in self.data:
      row_map[d.idx] = d

    net_asset = row_map.get(asset_row, {}).get("lft_closing_balance", 0.0)
    net_liability = row_map.get(liability_row, {}).get(
        "rgt_closing_balance", 0.0)
    net_equity = row_map.get(equity_row, {}).get("rgt_closing_balance", 0.0)
    net_provisional_profit_loss = net_asset - net_liability - net_equity

    return [
        {
            "value": net_asset,
            "label": _("Total Asset"),
            "datatype": "Currency",
            "currency": currency,
        },
        {
            "value": net_liability,
            "label": _("Total Liability"),
            "datatype": "Currency",
            "currency": currency,
        },
        {
            "value": net_equity,
            "label": _("Total Equity"),
            "datatype": "Currency",
            "currency": currency,
        },
        {
            "value": net_provisional_profit_loss,
            "label": _("Provisional Profit / Loss (Credit)"),
            "indicator": "Green" if net_provisional_profit_loss > 0 else "Red",
            "datatype": "Currency",
            "currency": currency,
        },
    ]


  def filter_accounts(self, accounts):
    parent_children_map = {}
    accounts_by_num = {}
    for d in accounts:
      accounts_by_num[d.account_number] = d
      parent_children_map.setdefault(d.parent_number or None, []).append(d)

    return accounts, accounts_by_num, parent_children_map


  def get_data(self):
    accounts = get_accounts_data(self.company)

    if not accounts:
      return None

    accounts, accounts_by_num, parent_children_map = self.filter_accounts(accounts)

    opening_balances = get_opening_balances(self.filters.company, add_days(self.year_start_date, -1))

    for d in accounts:
      # fisher 2025-04-03 外币科目需取本币余额，所以加in_account_currency=False参数
      closing_balance = get_balance_on(d.name, self.filters.to_date, in_account_currency=False)
      if d.root_type == 'Asset':
        d.opening_balance = opening_balances.get(d.name, {}).get(
            "opening_debit", 0) - opening_balances.get(d.name, {}).get("opening_credit", 0)
        d.closing_balance = closing_balance
      else:
        d.opening_balance = opening_balances.get(d.name, {}).get(
            "opening_credit", 0) - opening_balances.get(d.name, {}).get("opening_debit", 0)
        d.closing_balance = 0 - closing_balance
      accounts_by_num[d.account_number].update({
          "opening_balance": d.opening_balance,
          "closing_balance": d.closing_balance,
      })

    for d in reversed(accounts):
      if d.parent_number:
        accounts_by_num[d.parent_number]["opening_balance"] += d["opening_balance"]

    rows_map = {}
    for d in self.data:
      for prefix in ["lft_", "rgt_"]:
        rows_map[prefix + cstr(d.idx)] = {
            "name": d[prefix + "name"],
            "opening_balance": 0.0,
            "closing_balance": 0.0,
        }
        if not d[prefix + "empty"] and d[prefix + "calc_type"] and d[prefix + "calc_sources"] and d[prefix + "calc_type"] == "Closing Balance":
          d[prefix + "opening_balance"] = d[prefix + "closing_balance"] = 0.0
          d[prefix + "calc_sources"] = list(filter(None,
                                            d[prefix + "calc_sources"].split(",")))
          d[prefix + "accounts"] = []
          for account_number in d[prefix + "calc_sources"]:
            minus = False
            if account_number.startswith("-"):
              account_number = account_number[1:]
              minus = True
            account = accounts_by_num.get(account_number)
            if account:
              d[prefix + "accounts"].append({
                  "direction": (-1 if minus else 1),
                  "name": account.name,
                  "account_number": account.account_number,
                  "account_name": account.account_name,
                  "opening_balance": account.opening_balance,
                  "closing_balance": account.closing_balance,
              })
            d[prefix + "opening_balance"] += (-1 if minus else 1) * accounts_by_num.get(
                account_number, {}).get("opening_balance", 0.0)
            d[prefix + "closing_balance"] += (-1 if minus else 1) * accounts_by_num.get(
                account_number, {}).get("closing_balance", 0.0)
          rows_map[prefix + cstr(d.idx)].update({
              "opening_balance": d[prefix + "opening_balance"],
              "closing_balance": d[prefix + "closing_balance"],
          })

    for d in self.data:
      for prefix in ["lft_", "rgt_"]:
        if not d[prefix + "empty"] and d[prefix + "calc_type"] and d[prefix + "calc_sources"] and d[prefix + "calc_type"] == "Calculate Rows":
          d[prefix + "opening_balance"] = d[prefix + "closing_balance"] = 0.0
          d[prefix + "calc_sources"] = list(filter(None,
                                            d[prefix + "calc_sources"].split(",")))
          d[prefix + "rows"] = []
          for idx in d[prefix + "calc_sources"]:
            minus = False
            if idx.startswith("-"):
              idx = idx[1:]
              minus = True
            idx = cint(idx)
            row = rows_map.get(prefix + cstr(idx), {})
            d[prefix + "opening_balance"] += (-1 if minus else 1) * row.get("opening_balance", 0.0)
            d[prefix + "closing_balance"] += (-1 if minus else 1) * \
                row.get("closing_balance", 0.0)
            d[prefix + "rows"].append({
                "direction": (-1 if minus else 1),
                "idx": idx,
                "name": row.get("name"),
                "opening_balance": row.get("opening_balance"),
                "closing_balance": row.get("closing_balance"),
            })
          rows_map[prefix + cstr(d.idx)].update({
              "opening_balance": d[prefix + "opening_balance"],
              "closing_balance": d[prefix + "closing_balance"],
          })

    return self.data


  def get_columns(self):
    self.columns = [
        {
            "label": "资产",
            "fieldname": "lft_name",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": "行次",
            "fieldname": "idx",
            "fieldtype": "Int",
            "width": 60,
        },
        {
            "label": "期初数",
            "fieldname": "lft_opening_balance",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "期末数",
            "fieldname": "lft_closing_balance",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "负债和权益",
            "fieldname": "rgt_name",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": "行次",
            "fieldname": "idx",
            "fieldtype": "Int",
            "width": 60,
        },
        {
            "label": "期初数",
            "fieldname": "rgt_opening_balance",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "期末数",
            "fieldname": "rgt_closing_balance",
            "fieldtype": "Currency",
            "width": 140,
        },
    ]

    return self.columns

class BalanceSheetSingleColumn(BalanceSheetDoubleColumns):
  def run(self):
    self.get_columns()

    settings = frappe.get_single("Balance Sheet Settings")

    self.data = list(map(lambda d: frappe._dict({
        "idx": d.idx,
        "lft_empty": d.lft_empty,
        "lft_bold": d.lft_bold,
        "lft_name": d.lft_name,
        "lft_indent": d.lft_indent,
        "lft_calc_type": d.lft_calc_type,
        "lft_calc_sources": d.lft_calc_sources,
        "rgt_empty": d.rgt_empty,
        "rgt_bold": d.rgt_bold,
        "rgt_name": d.rgt_name,
        "rgt_indent": d.rgt_indent,
        "rgt_calc_type": d.rgt_calc_type,
        "rgt_calc_sources": d.rgt_calc_sources,
    }), settings.items))

    self.get_data()

    currency = self.filters.presentation_currency or frappe.db.get_value(
        "Company", self.filters.company, "default_currency"
    )

    report_summary = self.get_report_summary(
        asset_row=settings.asset_row,
        liability_row=settings.liability_row,
        equity_row=settings.equity_row,
        currency=currency,
    )

    chart = self.get_chart_data(
        asset_row=settings.asset_row,
        liability_row=settings.liability_row,
        equity_row=settings.equity_row,
    )

    self.data = self.to_single_column()

    return self.columns, self.data, None, chart, report_summary


  def get_data(self):
    accounts = get_accounts_data(self.company, root_types=['Asset', 'Liability', 'Equity'])
    if not accounts:
      return None

    accounts, accounts_by_num, parent_children_map = self.filter_accounts(accounts)

    for i in range(13):
      key = "balance_" + cstr(i)
      # 当月期末为下一个月的期初
      year = frappe.db.get_value('Fiscal Year', self.fiscal_year,'year_start_date').year
      from_date = get_first_day(datetime.date(year=year, month=1, day=1))
      if i > 0 and i < 12:
        from_date = get_first_day(datetime.date(year=year, month=cint(i + 1), day=1))
      elif i == 12:
        from_date = get_first_day(datetime.date(year=year + 1, month=1, day=1))
      opening_balances = get_opening_balances(self.filters.company, add_days(self.year_start_date, -1))

      for d in accounts:
        if d.root_type == 'Asset':
          d[key] = opening_balances.get(d.name, {}).get(
              "opening_debit", 0) - opening_balances.get(d.name, {}).get("opening_credit", 0)
        else:
          d[key] = opening_balances.get(d.name, {}).get(
              "opening_credit", 0) - opening_balances.get(d.name, {}).get("opening_debit", 0)

      for d in reversed(accounts):
        if d.parent_number and accounts_by_num[d.parent_number]:
          accounts_by_num[d.parent_number][key] += d[key]

      rows_map = {}
      for d in self.data:
        for prefix in ["lft_", "rgt_"]:
          rows_map[prefix + cstr(d.idx)] = {
              "name": d[prefix + "name"],
              key: 0.0,
          }
          if not d[prefix + "empty"] and d[prefix + "calc_type"] and d[prefix + "calc_sources"] and d[prefix + "calc_type"] == "Closing Balance":
            d[prefix + key] = 0.0
            if not isinstance(d[prefix + "calc_sources"], list):
              d[prefix + "calc_sources"] = list(filter(None,
                                                d[prefix + "calc_sources"].split(",")))
            d[prefix + "accounts"] = []
            for account_number in d[prefix + "calc_sources"]:
              minus = False
              if account_number.startswith("-"):
                account_number = account_number[1:]
                minus = True
              account = accounts_by_num.get(account_number)
              if account:
                d[prefix + "accounts"].append({
                    "direction": (-1 if minus else 1),
                    "name": account.name,
                    "account_number": account.account_number,
                    "account_name": account.account_name,
                    key: account[key],
                })
              d[prefix + key] += (-1 if minus else 1) * accounts_by_num.get(
                  account_number, {}).get(key, 0.0)
            rows_map[prefix + cstr(d.idx)].update({
                key: d[prefix + key],
            })

      for d in self.data:
        for prefix in ["lft_", "rgt_"]:
          if not d[prefix + "empty"] and d[prefix + "calc_type"] and d[prefix + "calc_sources"] and d[prefix + "calc_type"] == "Calculate Rows":
            d[prefix + key] = d[prefix + key] = 0.0
            if not isinstance(d[prefix + "calc_sources"], list):
              d[prefix + "calc_sources"] = list(filter(None,
                                                d[prefix + "calc_sources"].split(",")))
            d[prefix + "rows"] = []
            for idx in d[prefix + "calc_sources"]:
              minus = False
              if idx.startswith("-"):
                idx = idx[1:]
                minus = True
              idx = cint(idx)
              row = rows_map.get(prefix + cstr(idx))
              d[prefix + key] += (-1 if minus else 1) * row.get(key, 0.0)
              d[prefix + "rows"].append({
                  "direction": (-1 if minus else 1),
                  "idx": idx,
                  "name": row.get("name"),
                  key: row.get(key),
              })
            rows_map[prefix + cstr(d.idx)].update({
                key: d[prefix + key],
            })


    return self.data
  
  def to_single_column(self):
    lft_data = []
    rgt_data = []
    for d in self.data:
      for prefix in ["lft_", "rgt_"]:
        r = frappe._dict({
          "name": d.get(prefix + "name"),
          "idx": d.get("idx"),
          "empty": d.get(prefix + "empty"),
          "bold": d.get(prefix + "bold"),
          "indent": d.get(prefix + "indent"),
          "calc_type": d.get(prefix + "calc_type"),
          "calc_sources": d.get(prefix + "calc_sources"),
          "rows": d.get(prefix + "rows"),
        })
        r.update({
          "balance_" + cstr(i): d.get(prefix + "balance_" + cstr(i)) for i in range(13)
        })
        if prefix == "lft_":
          lft_data.append(r)
        else:
          rgt_data.append(r)


    self.data = lft_data
    self.data.extend(
      [
        {
          "name": None,
          "empty": 1,
          "indent": 0,
        }
      ]
    )
    self.data.extend(rgt_data)

    return self.data

  def get_report_summary(
      self,
      asset_row,
      liability_row,
      equity_row,
      currency,
  ):
    if not self.data:
      return None

    row_map = {}
    for d in self.data:
      row_map[d.idx] = d

    net_asset = row_map.get(asset_row, {}).get("lft_balance_12", 0.0)
    net_liability = row_map.get(liability_row, {}).get("rgt_balance_12", 0.0)
    net_equity = row_map.get(equity_row, {}).get("rgt_balance_12", 0.0)
    net_provisional_profit_loss = net_asset - net_liability - net_equity

    return [
        {
            "value": net_asset,
            "label": _("Total Asset"),
            "datatype": "Currency",
            "currency": currency,
        },
        {
            "value": net_liability,
            "label": _("Total Liability"),
            "datatype": "Currency",
            "currency": currency,
        },
        {
            "value": net_equity,
            "label": _("Total Equity"),
            "datatype": "Currency",
            "currency": currency,
        },
        {
            "value": net_provisional_profit_loss,
            "label": _("Provisional Profit / Loss (Credit)"),
            "indicator": "Green" if net_provisional_profit_loss > 0 else "Red",
            "datatype": "Currency",
            "currency": currency,
        },
    ]

  def get_chart_data(
      self,
      asset_row,
      liability_row,
      equity_row,
    ):
    labels = [d.get("label") for d in self.columns[2:]]

    row_map = {}
    for d in self.data:
      if d.get("idx"):
        row_map[d.get("idx")] = d

    asset_data, liability_data, equity_data = [], [], []

    for p in self.columns[2:]:
      if asset_row:
        asset_data.append(row_map.get(asset_row, {}).get("lft_" + p.get("fieldname"), 0.0))
      if liability_row:
        liability_data.append(row_map.get(liability_row, {}).get("rgt_" + p.get("fieldname"), 0.0))
      if equity_row:
        equity_data.append(row_map.get(equity_row, {}).get("rgt_" + p.get("fieldname"), 0.0))

    datasets = []
    if asset_data:
      datasets.append({"name": _("Assets"), "values": asset_data})
    if liability_data:
      datasets.append({"name": _("Liabilities"), "values": liability_data})
    if equity_data:
      datasets.append({"name": _("Equity"), "values": equity_data})

    chart = {"data": {"labels": labels, "datasets": datasets}}

    if not self.filters.accumulated_values:
      chart["type"] = "bar"
    else:
      chart["type"] = "line"

    return chart


  def get_columns(self):
    self.columns = [
        {
            "label": "科目",
            "fieldname": "name",
            "fieldtype": "Data",
            "width": 160,
        },
    ]

    for i in range(13):
      self.columns.append({
            "label": "期初数" if i == 0 else cstr(i) + "月",
            "fieldname": "balance_" + cstr(i),
            "fieldtype": "Currency",
            "width": 140,
      })

    return self.columns

def get_opening_balances(company, to_date):
    """
    高性能批量获取科目期初借贷。
    仅返回叶子节点或分录中存在的科目借贷，由后续逻辑统一处理汇总。

    如果启用了多会计准则折旧 多个finance book, 需要剔除主会计准则之外的finance book记录。
    """

    # 1. 批量从 GL Entry 中一次性查出所有科目的借贷合计
    precision = frappe.get_precision("GL Entry", "debit") or 2
    
    # 直接查询并返回字典格式
    # 注意：这里按 account (即科目 name) 分组
    gle = DocType("GL Entry")
    
    query = (
        frappe.qb.from_(gle)
        .select(
            gle.account.as_("name"),
            Sum(Round(gle.debit, precision)).as_("opening_debit"),
            Sum(Round(gle.credit, precision)).as_("opening_credit")
        )
        .where(gle.company == company)
        .where(gle.posting_date <= to_date)
        .where(gle.is_cancelled == 0)
        .groupby(gle.account)
    )    
    gle_balances = query.run(as_dict=True)

    # 2. 转换为以科目名称为 key 的 Map 格式
    # 格式示例: {"1001 现金": {"opening_debit": 100.0, "opening_credit": 0.0}, ...}
    opening_map = {}
    for g in gle_balances:
        opening_map[g.name] = frappe._dict({
            "opening_debit": frappe.utils.flt(g.opening_debit),
            "opening_credit": frappe.utils.flt(g.opening_credit)
        })

    return opening_map