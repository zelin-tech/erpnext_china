frappe.query_reports["BS and PL Missing Account"] = {
	filters: [
        {
			fieldname: "report",
			label: __("Report"),
			fieldtype: "Select",
			width: "80",
			options: "BS\nPL",
			default: "BS",
		},
        {
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			width: "80",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_default("company"),
		}
    ]
}