app_name = "erpnext_gdpdu_export"
app_title = "GDPdU Export"
app_publisher = "itsupport.online"
app_description = (
	"GoBD/GDPdU export (Datentraegerueberlassung, Audicon Beschreibungsstandard 1.6) "
	"for ERPNext accounting data, importable by the IDEA audit software."
)
app_email = "tickets@itsupport.onl"
app_license = "agpl-3.0"
# Shown on the desk home, in the app switcher and wherever Frappe needs a mark for the app
app_logo_url = "/assets/erpnext_gdpdu_export/images/logo.svg"
required_apps = ["erpnext"]

# Every company created after the installation gets its GDPdU Company Settings record
# right away (companies that already existed are covered by the patch of 0.3.0).
doc_events = {
	"Company": {
		"after_insert": (
			"erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_company_settings."
			"gdpdu_company_settings.create_for_new_company"
		),
	},
}
