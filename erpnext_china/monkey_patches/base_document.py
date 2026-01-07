import frappe
from frappe import _, _dict
from frappe.utils import cstr
from frappe.model.base_document import BaseDocument
import json

def get_owner_username(self):
    return frappe.db.get_value('User', self.owner, 'full_name')

def get_submit_username(self):
    """变更记录data字段数据格式
    changed:[[其它字段，旧值，新值]
        ['docstatus', 0, 1]
    ]"""
    try:
        if not self.meta.is_submittable:
            return
        filters={'ref_doctype': self.doctype, 'docname': self.name, 'data': ('like', '%docstatus%')}
        version_list = frappe.get_all('Version', filters = filters, fields=['owner','data'], order_by="creation desc")
        for version in version_list:
            data = json.loads(version.data)
            found = [f for f in data.get('changed') if f[0] =='docstatus' and f[-1] ==1]
            if found:
                return frappe.db.get_value('User', version.owner, 'full_name')
    except:
        pass

def _validate_selects(self):
    if frappe.flags.in_import:
        return

    for df in self.meta.get_select_fields():
        if df.fieldname=="naming_series" or not (self.get(df.fieldname) and df.options):
            continue

        options = (df.options or "").split("\n")
        
        #支持分号(;)分隔的值与标签，以解决下拉值一词多义问题
        options = [o.split(";")[0] for o in options if o]
        # if only empty options
        if not filter(None, options):
            continue

        # strip and set
        self.set(df.fieldname, cstr(self.get(df.fieldname)).strip())
        value = self.get(df.fieldname)

        if value not in options and not (frappe.flags.in_test and value.startswith("_T-")):
            # show an elaborate message
            prefix = _("Row #{0}:").format(self.idx) if self.get("parentfield") else ""
            label = _(self.meta.get_label(df.fieldname))
            comma_options = '", "'.join(_(each) for each in options)

            frappe.throw(_('{0} {1} cannot be "{2}". It should be one of "{3}"').format(prefix, label,
                value, comma_options))

def money_in_words(self, amount):
    return frappe.utils.money_in_words(amount)   

BaseDocument.get_owner_username = get_owner_username
BaseDocument.get_submit_username = get_submit_username
BaseDocument._validate_selects = _validate_selects
BaseDocument.money_in_words = money_in_words