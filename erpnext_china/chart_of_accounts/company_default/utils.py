import frappe, csv, os, json
from frappe import _
from erpnext.setup.setup_wizard.operations.taxes_setup import from_detailed_data


def set_company_default(company):    
    set_default_accounts(company)
    setup_tax_template(company)
    setup_tax_rule(company)
    set_item_group_account(company)
    set_warehouse_account(company)

def set_default_accounts(company_name):
    try:
        values = {}
        file_path = os.path.join(os.path.dirname(__file__), 'default_accounts.csv')
        with open(file_path, 'r', encoding='utf-8') as in_file:
            data = list(csv.reader(in_file))

        company_doc = frappe.get_doc('Company', company_name)
        account_map = frappe._dict(frappe.get_all("Account",
            filters = {
                "company": company_name,
                "account_name": ("in", [d[1] for d in data]),
                "is_group": 0
            },
            fields = ["account_name", "name"],
            as_list = 1
        ))
        if account_map:
            values = {d[0]:account_map.get(d[1]) for d in data if account_map.get(d[1])}    
            company_doc.update(values)
            frappe.local.flags.ignore_chart_of_accounts = 1
            company_doc.db_update() 

        return values
    except:
        frappe.log_error("china_company_default.utils.set_default_accounts")        

def setup_tax_template(company_name):
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'tax_template.json')
        with open(file_path, 'r', encoding='utf-8') as json_file:
            tax_data = json.load(json_file)    
    
        from_detailed_data(company_name, tax_data)
        #标准功能中未处理含税字段，这里单独处理
        for prefix in ('Purchase', 'Sales'):    
            header = frappe.qb.DocType(f"{prefix} Taxes and Charges Template")
            detail = frappe.qb.DocType(f"{prefix} Taxes and Charges")

            frappe.qb.update(detail
                ).join(header
                ).on(header.name == detail.parent
                ).where(header.title.like('%含税%')
                ).set(detail.included_in_print_rate, 1
                ).run()            
    except:
        frappe.log_error("china_company_default.utils.setup_tax_template")

def setup_tax_rule(company_name):
    try:
        abbr = frappe.db.get_value('Company', company_name, 'abbr')
        file_path = os.path.join(os.path.dirname(__file__), 'tax_rule.csv')
        with open(file_path, 'r', encoding='utf-8') as in_file:
            data = list(csv.reader(in_file))
        if data: data = data[1:]
        for (tax_category, tax_type, customer_group, item_group, billing_country,
            shipping_country, priority, tax_template) in data:
            template_field_name = 'purchase_tax_template' if tax_type =='Purchase' else 'sales_tax_template'
            tax_rule = frappe.get_doc({
                    'doctype':'Tax Rule',
                    'tax_category': tax_category,
                    'tax_type': tax_type,
                    'customer_group': customer_group,
                    'item_group': item_group,
                    'billing_country': billing_country,
                    'shipping_country': shipping_country,
                    'priority': priority,
                    template_field_name: f'{tax_template} - {abbr}',
                    'company': company_name})
            tax_rule.insert(ignore_permissions = 1)    
    except:
        frappe.log_error("china_company_default.utils.setup_tax_rule")

def set_warehouse_account(company):
    abbr = frappe.db.get_value('Company', company, 'abbr')
    try:
        wh_account_list =  [
            [_("Finished Goods"), '库存商品'],
            [_("Work In Progress"), '在产品']
        ]
        
        account_map = frappe._dict(frappe.get_all('Account',
            filters ={'account_name': ('in', [row[1] for row in wh_account_list]),
                     'company': company},
            fields = ['account_name', 'name'],
            as_list = True))
        for (wh, account_name) in wh_account_list:
            if account_id := account_map.get(account_name):
                frappe.db.set_value('Warehouse', f'{wh} - {abbr}', 'account', account_id)            
    except:
        frappe.log_error("china_company_default.utils.setup_warehouse_account")   

def set_item_group_account(company):
    try:
        # 按会计准则分组配置科目映射
        chart_of_accounts_config = {
            '小企业会计准则': [
                (_("Raw Material"), '生产成本-基本生产成本'),
                (_("Sub Assemblies"), '生产成本-基本生产成本'),
                (_("Consumable"), '生产成本-基本生产成本'),
                (_("Services"), '生产成本-辅助生产成本'),
                (_("Product"), '主营业务成本')
            ],
            '一般企业会计准则(2024)': [
                (_("Raw Material"), '制造企业成本-直接材料'),
                (_("Sub Assemblies"), '制造企业成本-直接材料'),
                (_("Consumable"), '制造企业成本-直接材料'),
                #(_("Services"), '生产成本-辅助生产成本'),
                (_("Product"), '销售商品成本')
            ]
        }
        
        # 获取公司的会计准则
        company_doc = frappe.get_doc('Company', company)
        chart_of_accounts = getattr(company_doc, 'chart_of_accounts', None)
        
        # 如果没有设置会计准则，使用默认配置（小企业会计准则）
        if not chart_of_accounts or chart_of_accounts not in chart_of_accounts_config:
            chart_of_accounts = '小企业会计准则'
        
        # 获取当前会计准则对应的科目配置
        item_group_account_list = chart_of_accounts_config[chart_of_accounts]
        
        # 获取科目映射
        account_names = [row[1] for row in item_group_account_list]
        account_map = frappe._dict(frappe.get_all('Account',
            filters={
                'account_name': ('in', account_names),
                'company': company, 
                'is_group': 0
            },
            fields=['account_name', 'name'],
            as_list=True
        ))
        
        item_group_account_assigned = set()    
        
        for (item_group, account_name) in item_group_account_list:
            if item_group in item_group_account_assigned: 
                continue
                
            account_id = account_map.get(account_name)
            if account_id and frappe.db.exists('Item Group', item_group):                
                item_group_doc = frappe.get_doc('Item Group', item_group)
                
                # 检查是否已存在该公司的配置
                existing_company_config = None
                for default in item_group_doc.get('item_group_defaults', []):
                    if default.company == company:
                        existing_company_config = default
                        break
                
                # 如果已存在配置，则更新；否则新增
                if existing_company_config:
                    existing_company_config.expense_account = account_id
                else:
                    item_group_doc.append('item_group_defaults', {
                        'company': company,
                        'expense_account': account_id
                    })
                
                item_group_doc.save()
                item_group_account_assigned.add(item_group)
                
    except Exception as e:
        frappe.log_error("china_company_default.utils.set_item_group_account")