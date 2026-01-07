
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils.csvutils import build_csv_response
from frappe.utils.xlsxutils import build_xlsx_response
from frappe.core.doctype.data_import.exporter import Exporter

def build_response(self):
    from urllib.parse import quote

    filename = _(self.doctype)
    if self.file_type == "CSV":
        filename = f'{quote(filename)}'
        build_csv_response(self.get_csv_array_for_export(), filename)
    elif self.file_type == "Excel":
        build_xlsx_response(self.get_csv_array_for_export(), filename)

Exporter.build_response = build_response   #转到csvutils里去处理