# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import json
import os

import frappe
from frappe import _
from frappe.utils import cstr
from frappe.utils.nestedset import rebuild_tree
from unidecode import unidecode
from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import (
    get_chart as original_get_chart,
    add_suffix_if_duplicate, 
    identify_is_group, 
    get_account_tree_from_existing_company
)


def erpnext_china_create_charts(
    company, chart_template=None, existing_company=None, custom_chart=None, from_coa_importer=None
):
    chart = custom_chart or get_chart(chart_template, existing_company)
    if chart:
        accounts = []

        def _import_accounts(children, parent, root_type, root_account=False):
            for account_name, child in children.items():
                if root_account:
                    root_type = child.get("root_type")

                if account_name not in [
                    "account_name",
                    "account_number",
                    "account_type",
                    "root_type",
                    "is_group",
                    "tax_rate",
                    "account_currency",
                ]:
                    account_number = cstr(child.get("account_number")).strip()
                    account_name, account_name_in_db = add_suffix_if_duplicate(
                        account_name, account_number, accounts
                    )

                    is_group = identify_is_group(child)
                    report_type = (
                        "Balance Sheet"
                        if root_type in ["Asset", "Liability", "Equity"]
                        else "Profit and Loss"
                    )

                    account = frappe.get_doc(
                        {
                            "doctype": "Account",
                            "account_name": child.get("account_name") if from_coa_importer else account_name,
                            "company": company,
                            "parent_account": parent,
                            "is_group": is_group,
                            "root_type": root_type,
                            "report_type": report_type,
                            "account_number": account_number,
                            "account_type": child.get("account_type"),
                            "account_currency": child.get("account_currency")
                            or frappe.get_cached_value("Company", company, "default_currency"),
                            "tax_rate": child.get("tax_rate"),
                        }
                    )

                    if root_account or frappe.local.flags.allow_unverified_charts:
                        account.flags.ignore_mandatory = True

                    account.flags.ignore_permissions = True

                    account.insert()

                    accounts.append(account_name_in_db)

                    _import_accounts(child, account.name, root_type)

        frappe.local.flags.ignore_update_nsm = True
        try:
            _import_accounts(chart, None, None, root_account=True)
            rebuild_tree("Account")
        except Exception as e:
            frappe.log_error(f"Error rebuilding tree in create_charts2: {e}", title="Tree Rebuild Error")
        frappe.local.flags.ignore_update_nsm = False


def add_suffix_if_duplicate(account_name, account_number, accounts):
    if account_number:
        account_name_in_db = unidecode(" - ".join([account_number, account_name.strip().lower()]))
    else:
        account_name_in_db = unidecode(account_name.strip().lower())

    if account_name_in_db in accounts:
        count = accounts.count(account_name_in_db)
        account_name = account_name + " " + cstr(count)

    return account_name, account_name_in_db


def identify_is_group(child):
    if child.get("is_group"):
        is_group = child.get("is_group")
    elif len(
        set(child.keys())
        - set(
            [
                "account_name",
                "account_type",
                "root_type",
                "is_group",
                "tax_rate",
                "account_number",
                "account_currency",
            ]
        )
    ):
        is_group = 1
    else:
        is_group = 0

    return is_group

@frappe.whitelist()
def get_coa(doctype, parent, is_root=None, chart=None):
    from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import (
        build_tree_from_json,
    )

    # add chart to flags to retrieve when called from expand all function
    chart = chart if chart else frappe.flags.chart
    frappe.flags.chart = chart
    # 获取科目表数据
    chart_data = get_chart(chart)
    #传获取的科目表数据
    parent = None if parent == _("All Accounts") else parent
    accounts = build_tree_from_json(chart, chart_data)  # returns alist of dict in a tree render-able form

    # filter out to show data for the selected node only
    accounts = [d for d in accounts if d["parent_account"] == parent]

    return accounts

@frappe.whitelist()
def get_chart(chart_template, existing_company=None):
    # 标准科目表直接调用源方法
    if chart_template in ["Standard", "Standard with Numbers"]:
        return original_get_chart(chart_template, existing_company)

    chart = {}
    if existing_company:
        return get_account_tree_from_existing_company(existing_company)
    else:
        bench_dir = frappe.utils.get_bench_path()
        erpnext_charts_path = os.path.join(bench_dir, "apps", "erpnext", "erpnext", "accounts", "doctype", "account", "chart_of_accounts")

        folders = ("verified",)
        if frappe.local.flags.allow_unverified_charts:
            folders = ("verified", "unverified")
        for folder in folders:
            path = os.path.join(erpnext_charts_path, folder)
            for fname in os.listdir(path):
                fname = frappe.as_unicode(fname)
                if fname.endswith(".json"):
                    try:
                        with open(os.path.join(path, fname)) as f:
                            chart = f.read()
                            if chart and json.loads(chart).get("name") == chart_template:
                                return json.loads(chart).get("tree")
                    except Exception as e:
                        frappe.log_error(f"Error reading chart file in get_chart: {e}", title="Chart File Read Error")

        custom_path = os.path.join(bench_dir, "apps", "erpnext_china", "erpnext_china", "chart_of_accounts", "custom_accounts")
        custom_folders = ("chart_of_accounts", "custom_of_accounts")
        for custom_folder in custom_folders:
            custom_charts_path = os.path.join(custom_path, custom_folder)
            if os.path.exists(custom_charts_path):
                for fname1 in os.listdir(custom_charts_path):
                    fname1 = frappe.as_unicode(fname1)
                    if fname1.endswith(".json"):
                        try:
                            with open(os.path.join(custom_charts_path, fname1)) as f1:
                                chart1 = f1.read()
                                if chart1 and json.loads(chart1).get("name") == chart_template:
                                    return json.loads(chart1).get("tree")
                        except Exception as e:
                            frappe.log_error(f"Error reading custom chart file in get_chart: {e}", title="Custom Chart File Read Error")

        return chart


@frappe.whitelist()
def get_charts_for_country(country, with_standard=False):
    charts = []
    bench_dir = frappe.utils.get_bench_path()

    def _get_chart_name(content):
        if content:
            try:
                content = json.loads(content)
                if (
                    content and content.get("disabled", "No") == "No"
                ) or frappe.local.flags.allow_unverified_charts:
                    charts.append(content["name"])
            except Exception as e:
                frappe.log_error(f"Error parsing chart content in get_charts_for_country: {e}", title="Chart Content Parse Error")

    country_code = frappe.get_cached_value("Country", country, "code")
    if country_code:
        folders = ("verified",)
        if frappe.local.flags.allow_unverified_charts:
            folders = ("verified", "unverified")

        erpnext_charts_path = os.path.join(bench_dir, "apps", "erpnext", "erpnext", "accounts", "doctype", "account", "chart_of_accounts")
        for folder in folders:
            path = os.path.join(erpnext_charts_path, folder)
            if os.path.exists(path):
                for fname in os.listdir(path):
                    fname = frappe.as_unicode(fname)
                    if (fname.startswith(country_code) or fname.startswith(country)) and fname.endswith(".json"):
                        try:
                            with open(os.path.join(path, fname)) as f:
                                _get_chart_name(f.read())
                        except Exception as e:
                            frappe.log_error(f"Error reading country chart file in get_charts_for_country: {e}", title="Country Chart File Read Error")

    # if more than one charts, returned then add the standard
    if len(charts) != 1 or with_standard:
        charts += ["Standard", "Standard with Numbers"]

    custom_path = os.path.join(bench_dir, "apps", "erpnext_china", "erpnext_china", "chart_of_accounts", "custom_accounts")
    custom_folders = ("chart_of_accounts", "custom_of_accounts")
    for custom_folder in custom_folders:
        custom_charts_path = os.path.join(custom_path, custom_folder)
        if os.path.exists(custom_charts_path):
            for fname1 in os.listdir(custom_charts_path):
                fname1 = frappe.as_unicode(fname1)
                if (fname1.startswith(country_code) or fname1.startswith(country)) and fname1.endswith(".json"):
                    try:
                        with open(os.path.join(custom_charts_path, fname1)) as f1:
                            _get_chart_name(f1.read())
                    except Exception as e:
                        frappe.log_error(f"Error reading custom country chart file in get_charts_for_country: {e}", title="Custom Country Chart File Read Error")

    return charts

@frappe.whitelist()
def get_all_nodes(doctype, label, parent, tree_method, **filters):
    from frappe.desk.treeview import get_all_nodes as original_get_all_nodes

    tree_method = frappe.override_whitelisted_method(tree_method)

    return original_get_all_nodes(doctype, label, parent, tree_method, **filters)