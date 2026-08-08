import frappe, csv, os, json
from frappe import _
    

uom_list = [
    '个',
    '支',
    '台',
    '只',
    '批',
    '次',
    '件',
	'张',
    '套',
    '卷',
    '片',
    '条',
    '打',
    '箱',
    '包',
    '千米',
    '米',
    '分米',
    '厘米',
    '毫米',
    '毫克',
    '克',
    '千克',
    '吨',
    '立方厘米',
    '立方分米',
    '立方米',
    '平方米',
    '平方厘米',
    '平方分米',
    '平方毫米',
    '升',
    '毫升',
    '年',
    '月',
    '周',
    '日',
    '小时',
    '分钟',
    '秒',
    '两',
    '斤',
    '公斤',
    '摄氏度',
    '华氏度'
]


def after_install():
    if not frappe.is_setup_complete():
        set_china_default()
        set_v16_icon()

def set_china_default():    
    try:
        existing_uom_list = frappe.get_all('UOM', pluck ='name')
        existing_uom_set = {uom for uom in existing_uom_list}
        new_uom_list = [uom for uom in uom_list if uom not in existing_uom_set]
        for uom in new_uom_list:            
            frappe.get_doc({
                'doctype': 'UOM',
                'uom_name': uom,
                'enabled': 1}).insert(ignore_permissions = 1, ignore_if_duplicate=1)
        frappe.db.set_value('UOM',{'name': ('not in', uom_list)}, 'enabled', 0)
        frappe.db.set_value('Language',{'name': 'zh'}, 'enabled', 1)
        set_global_defaults()
        set_system_settings()
        change_field_property()        
    except:
        frappe.log_error("erpnext_china set_china_default failed")

def set_global_defaults():
        frappe.db.set_single_value('Global Defaults',
            {
				'disable_rounded_total':1,
				'disable_in_words':1
            }
        )

def set_system_settings():
    system_settings = frappe.get_doc('System Settings')
    system_settings.enable_onboarding = 0
    system_settings.country = 'China'
    system_settings.language = 'zh'
    system_settings.currency = 'CNY'
    system_settings.time_zone = 'Asia/Chongqing' 
    system_settings.rounding_method = 'Commercial Rounding'
    system_settings.allow_login_using_user_name = 1
    system_settings.allow_login_using_mobile_number = 1
    system_settings.currency_precision = 2
    system_settings.float_precision = 5
    system_settings.date_format = 'yyyy-mm-dd'
    system_settings.save(ignore_permissions=True) 

def change_field_property():
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'field_property.csv')
        # nosemgrep: frappe-security-file-traversal -- static file bundled with the app, no user input in path
        with open(file_path, 'r', encoding='utf-8') as in_file:
                data = list(csv.reader(in_file))
        for (doctype, field_name, prop, value) in data:
                frappe.get_doc({
                        'doctype': 'Property Setter',
                        'doctype_or_field': 'DocField',
                        'doc_type': doctype,
                        'field_name': field_name,
                        'property': prop,
                        'value': value
                }).insert(ignore_permissions=1, ignore_if_duplicate=1)
    except:
        frappe.log_error("erpnext_china change_field_property failed")

def set_v16_icon():
    """安装后更新桌面图标和工作流侧边栏的图标配置"""

    try:    
        # 1. 更新 Desktop Icon：中国财务报表
        desktop_icon_name = "中国财务报表"
        if frappe.db.table_exists("Desktop Icon"):
            frappe.db.set_value(
                "Desktop Icon",
                desktop_icon_name,
                "logo_url",
                "/assets/erpnext_china/icons/account_report.svg"
            )
        
        # 2. 更新 Workflow Sidebar：中国财务报表
        workflow_sidebar_name = "中国财务报表"
        if frappe.db.table_exists("Workspace Sidebar"):
            frappe.db.set_value(
                "Workspace Sidebar",
                workflow_sidebar_name,
                "header_icon",
                "cn-account-reporting"
            )
    except:
        pass