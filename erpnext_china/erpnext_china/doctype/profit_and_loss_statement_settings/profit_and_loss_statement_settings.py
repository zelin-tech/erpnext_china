# Copyright (c) 2023, Vnimy and contributors
# For license information, please see license.txt

import os
import frappe
from frappe import _
from frappe.model.document import Document


class ProfitandLossStatementSettings(Document):
    @frappe.whitelist()
    def get_example_data(self):
        return frappe.get_file_json(os.path.join(os.path.dirname(__file__), "example_data.json"))

    def validate(self):
        validate_report_settings(self)

def validate_report_settings(doc):
    """通用报表设置校验入口：支持单列和双列(Balance Sheet)结构"""
    errors = []
    warnings = []
    
    # 1. 检查重复科目 (Warning)
    check_duplicate_account_numbers(doc, warnings)
    # 2. 检查计算行逻辑 (Error)
    check_calculation_row_logic(doc, errors)

    if warnings:
        frappe.msgprint(title=_("Configuration Warnings"), indicator="orange", msg="<br>".join(warnings))

    if errors:
        frappe.throw(title=_("Logic Errors"), msg="<br>".join(errors))

def check_duplicate_account_numbers(doc, warnings):
    """检查重复科目，兼容 lft_ 和 rgt_，支持完整汉化"""
    # 收集器：{科目号: (行号, 侧边名称)}
    all_accounts = {}
    
    # 定义方位翻译字典
    side_map = {
        "Left Column": _("Left Column"),
        "Right Column": _("Right Column")
    }
    
    for row in doc.items:
        # 定义需要检查的配置对 (内部标识, 类型字段, 来源字段)
        checks = [
            ("Single", "calc_type", "calc_sources"),
            ("Left Column", "lft_calc_type", "lft_calc_sources"),
            ("Right Column", "rgt_calc_type", "rgt_calc_sources")
        ]
        
        for side, type_field, source_field in checks:
            ctype = getattr(row, type_field, None)
            csource = getattr(row, source_field, None)
            
            if ctype == "Closing Balance" and csource:
                accounts = [s.strip() for s in csource.split(',') if s.strip()]
                for acc in accounts:
                    # 去掉负号进行科目匹配校验
                    clean_acc = acc.replace('-', '')
                    
                    if clean_acc in all_accounts:
                        prev_idx, prev_side = all_accounts[clean_acc]
                        
                        # 组装当前行描述：如 "(左栏)第 5 行"
                        curr_side_label = f"({side_map.get(side)})" if side != "Single" else ""
                        curr_desc = _("{0}Row {1}").format(curr_side_label, row.idx)
                        
                        # 组装之前出现的行描述：如 "(右栏)第 2 行"
                        prev_side_label = f"({side_map.get(prev_side)})" if prev_side != "Single" else ""
                        prev_desc = _("{0}Row {1}").format(prev_side_label, prev_idx)
                        
                        # 使用带占位符的完整翻译 Key
                        msg = _("{0}: Account {1} already in {2}").format(curr_desc, clean_acc, prev_desc)
                        
                        if msg not in warnings:
                            warnings.append(msg)
                    else:
                        all_accounts[clean_acc] = (row.idx, side)

def check_calculation_row_logic(doc, errors):
    existing_indices = [int(item.idx) for item in doc.items]
    # 定义方位翻译字典
    side_map = {
        "Left": _("Left Column"),
        "Right": _("Right Column")
    }

    for row in doc.items:
        checks = [
            ("Left", "lft_calc_type", "lft_calc_sources"),
            ("Right", "rgt_calc_type", "rgt_calc_sources"),
            ("Single", "calc_type", "calc_sources")
        ]
        
        for side, type_field, source_field in checks:
            ctype = getattr(row, type_field, None)
            csource = getattr(row, source_field, None)
            
            if ctype == "Calculate Rows" and csource:
                # 获取翻译后的方位标签，如 "(左侧)"
                side_label = f"({side_map.get(side)})" if side != "Single" else ""
                
                sources = [s.strip() for s in csource.split(',') if s.strip()]
                for s in sources:
                    clean_idx_str = s.replace('-', '')
                    if not clean_idx_str: continue
                    
                    try:
                        ref_idx = int(clean_idx_str)
                        if ref_idx not in existing_indices:
                            errors.append(_("{0}Row {1}: Referenced row {2} does not exist").format(side_label, row.idx, ref_idx))
                    except ValueError:
                        errors.append(_("{0}Row {1}: '{2}' is not a valid row number").format(side_label, row.idx, clean_idx_str))