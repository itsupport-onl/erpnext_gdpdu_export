frappe.listview_settings["GDPdU Export"] = {
	add_fields: ["status"],

	get_indicator(doc) {
		const colours = {
			Entwurf: "gray",
			"In Warteschlange": "orange",
			Läuft: "blue",
			Fertig: "green",
			Fehlgeschlagen: "red",
		};
		return [__(doc.status), colours[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
