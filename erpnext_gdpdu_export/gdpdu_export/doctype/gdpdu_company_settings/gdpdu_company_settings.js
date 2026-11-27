// Form script of the per-company settings: a shortcut to the exports of this company.

frappe.ui.form.on("GDPdU Company Settings", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		frm.add_custom_button(__("Exporte dieses Unternehmens"), () => {
			frappe.set_route("List", "GDPdU Export", { company: frm.doc.company });
		});
	},
});
