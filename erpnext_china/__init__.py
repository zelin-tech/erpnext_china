# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import importlib

import frappe

patches_loaded = False

__version__ = '1.0.5'


def load_monkey_patches():
    global patches_loaded

    if (
        patches_loaded
        or not getattr(frappe, "conf", None)
        or not "erpnext_china" in frappe.get_installed_apps()
    ):
        return

    for app in frappe.get_installed_apps():
        if app in ['frappe', 'erpnext']: continue
        try:
            folder = frappe.get_app_path(app, "monkey_patches")
            if os.path.exists(folder):
                for module_name in os.listdir(folder):
                    if not module_name.endswith(".py") or module_name == "__init__.py":
                        continue
                    importlib.import_module(f"{app}.monkey_patches.{module_name[:-3]}")
        except:
            method = f"Failed load app {app} monkey patches"
            if not frappe.db.exists("Error Log", {"method": method, "seen":0}):
                frappe.log_error(method, frappe.get_traceback(with_context=True))            
                frappe.log(f'{app} load failed in erpnext_china.__init__.py, check whether you removed the app')        

    patches_loaded = True

connect = frappe.connect

def custom_connect(*args, **kwargs):
    out = connect(*args, **kwargs)
    load_monkey_patches()

    return out

frappe.connect = custom_connect