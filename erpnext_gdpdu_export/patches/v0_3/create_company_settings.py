"""0.3.0: one *GDPdU Company Settings* record per company.

Before 0.3.0 the only company-related setting was the global default company;
the data supplier of the index.xml was derived from the Company record at run
time. This patch creates a settings record for every company from the same
master data, so an existing installation exports exactly as before, and each
company can be adjusted on its own from now on.
"""

import frappe


def execute():
	frappe.reload_doc("gdpdu_export", "doctype", "gdpdu_company_settings")

	from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_company_settings.gdpdu_company_settings import (
		ensure_company_settings,
	)

	for company in frappe.get_all("Company", pluck="name"):
		ensure_company_settings(company)
