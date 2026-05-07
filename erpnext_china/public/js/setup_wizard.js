frappe.setup.utils.load_prefilled_data = function (slide, callback) {
    frappe.db
        .get_value("System Settings", "System Settings", [
            "country",
            "timezone",
            "currency",
            "language",
        ])
        .then((r) => {
            if (r.message) {
                frappe.wizard.values.currency = r.message.currency;
                frappe.wizard.values.country = r.message.country;
                frappe.wizard.values.timezone = r.message.time_zone;
                // fisher 转成显示值
                const  language = frappe.setup.utils.get_language_name_from_code(r.message.language);
                frappe.wizard.values.language = language;

                frappe.db.get_value(
                    "User",
                    { name: ["not in", ["Administrator", "Guest"]] },
                    ["full_name", "email"],
                    (r) => {
                        if (r) {
                            frappe.wizard.values.full_name = r.full_name;
                            frappe.wizard.values.email = r.email;
                        }
                    }
                );
            }
            callback(slide);
        });
}