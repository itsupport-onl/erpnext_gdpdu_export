// Form script of the GDPdU Export document.
//
// The target group are accountants without technical background: the form
// always states what happens next, offers exactly one obvious action and
// refreshes itself while the background job runs.

const STATUS_DRAFT = "Entwurf";
const STATUS_QUEUED = "In Warteschlange";
const STATUS_RUNNING = "Läuft";
const STATUS_COMPLETED = "Fertig";
const STATUS_FAILED = "Fehlgeschlagen";

const BUSY_STATES = [STATUS_QUEUED, STATUS_RUNNING];
const POLL_INTERVAL = 8000;

frappe.ui.form.on("GDPdU Export", {
	onload(frm) {
		if (frm.is_new()) {
			set_default_company(frm);
			set_default_period(frm);
		}
	},

	refresh(frm) {
		render_scope(frm);
		render_protocol(frm);
		render_intro(frm);
		render_actions(frm);
		watch_progress(frm);
	},

	period_type(frm) {
		if (frm.doc.period_type === "Geschäftsjahr") {
			apply_fiscal_year(frm);
		}
	},

	fiscal_year(frm) {
		apply_fiscal_year(frm);
	},
});

// ----------------------------------------------------------------- defaults

function set_default_company(frm) {
	// The Settings company wins, otherwise the user's default company.
	frappe.db.get_single_value("GDPdU Export Settings", "default_company").then((company) => {
		const fallback = frappe.defaults.get_user_default("Company");
		if (!frm.doc.company && (company || fallback)) {
			frm.set_value("company", company || fallback);
		}
	});
}

function set_default_period(frm) {
	// Suggest the last completed fiscal year — the usual subject of an audit.
	frappe.db
		.get_list("Fiscal Year", {
			filters: { year_end_date: ["<", frappe.datetime.get_today()], disabled: 0 },
			fields: ["name", "year_start_date", "year_end_date"],
			order_by: "year_end_date desc",
			limit: 1,
		})
		.then((years) => {
			if (!years || !years.length || frm.doc.fiscal_year) {
				return;
			}
			frm.set_value("fiscal_year", years[0].name);
			frm.set_value("from_date", years[0].year_start_date);
			frm.set_value("to_date", years[0].year_end_date);
		});
}

function apply_fiscal_year(frm) {
	if (frm.doc.period_type !== "Geschäftsjahr" || !frm.doc.fiscal_year) {
		return;
	}
	frappe.db
		.get_value("Fiscal Year", frm.doc.fiscal_year, ["year_start_date", "year_end_date"])
		.then((response) => {
			const year = response.message;
			if (!year) {
				return;
			}
			frm.set_value("from_date", year.year_start_date);
			frm.set_value("to_date", year.year_end_date);
		});
}

// ----------------------------------------------------------------- rendering

function render_scope(frm) {
	const wrapper = frm.get_field("scope_html").$wrapper;
	if (wrapper.data("rendered")) {
		return;
	}

	frappe
		.call("erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.gdpdu_export.get_export_scope")
		.then((response) => {
			const tables = response.message || [];
			const rows = tables
				.map(
					(table) =>
						`<tr><td><code>${frappe.utils.escape_html(table.filename)}</code></td>
						 <td>${frappe.utils.escape_html(table.hint || table.name)}</td></tr>`
				)
				.join("");

			wrapper.html(`
				<p style="color: var(--text-muted)">
					Das Paket enthält die vollständige Finanzbuchhaltung des gewählten Zeitraums —
					ohne Auswahl einzelner Konten, wie es die Betriebsprüfung erwartet.
				</p>
				<table class="table table-bordered" style="font-size: 12px">
					<thead><tr><th style="width: 30%">Datei</th><th>Inhalt</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>
				<p style="color: var(--text-muted); font-size: 11px">
					Nicht enthalten: Lohnabrechnungsdaten (dafür gibt es die Digitale
					LohnSchnittstelle). Personalkosten-Buchungen sind Teil des Journals.
				</p>
			`);
			wrapper.data("rendered", true);
		});
}

function render_protocol(frm) {
	const wrapper = frm.get_field("protocol_display").$wrapper;
	wrapper.html(frm.doc.protocol_html || "");
}

function render_intro(frm) {
	if (frm.is_new()) {
		frm.set_intro(
			"Wählen Sie Unternehmen und Zeitraum und speichern Sie mit Strg+S. " +
				"Danach erscheint oben rechts der Knopf „Export erstellen“.",
			"blue"
		);
		return;
	}

	if (BUSY_STATES.includes(frm.doc.status)) {
		frm.set_intro(
			"Der Export wird im Hintergrund erstellt. Sie können diese Seite verlassen — " +
				"sie aktualisiert sich von selbst, sobald das Paket fertig ist.",
			"orange"
		);
		return;
	}

	if (frm.doc.status === STATUS_COMPLETED) {
		let text =
			"Das Export-Paket ist fertig. Laden Sie es herunter und übergeben Sie es dem " +
			"Prüfer nur auf verschlüsseltem Weg — es enthält personenbezogene Daten.";
		if (!frm.doc.dtd_included) {
			text +=
				" <b>Achtung:</b> Die Datei gdpdu-01-08-2002.dtd fehlt im Paket. " +
				"Ein Administrator kann sie einmalig in den GDPdU Export Settings hinterlegen.";
		}
		frm.set_intro(text, frm.doc.dtd_included ? "green" : "orange");
		return;
	}

	if (frm.doc.status === STATUS_FAILED) {
		frm.set_intro(
			"Der letzte Versuch ist fehlgeschlagen. Prüfen Sie die Fehlermeldung und " +
				"starten Sie den Export erneut.",
			"red"
		);
		return;
	}

	frm.set_intro(
		"Alles bereit. Mit „Export erstellen“ starten Sie die Erzeugung des Pakets; " +
			"das kann bei großen Zeiträumen einige Minuten dauern.",
		"blue"
	);
}

function render_actions(frm) {
	frm.page.clear_primary_action();

	if (frm.is_new() || frm.is_dirty()) {
		// Frappe keeps "Speichern" as the primary action.
		return;
	}

	if (BUSY_STATES.includes(frm.doc.status)) {
		frm.page.set_primary_action(__("Status aktualisieren"), () => frm.reload_doc());
		return;
	}

	if (frm.doc.status === STATUS_COMPLETED) {
		frm.page.set_primary_action(__("Paket herunterladen"), () => download_package(frm), "download");
		frm.add_custom_button(__("Export wiederholen"), () => start_export(frm));
	} else {
		frm.page.set_primary_action(__("Export erstellen"), () => start_export(frm), "play");
	}

	frm.add_custom_button(__("Einstellungen"), () =>
		frappe.set_route("Form", "GDPdU Export Settings")
	);
}

// ------------------------------------------------------------------- actions

function start_export(frm) {
	const period = `${frappe.datetime.str_to_user(frm.doc.from_date)} bis ${frappe.datetime.str_to_user(
		frm.doc.to_date
	)}`;

	frappe.confirm(
		`Export für <b>${frappe.utils.escape_html(frm.doc.company)}</b><br>
		 Zeitraum: <b>${period}</b><br><br>
		 Der Export liest die Buchhaltung nur aus und verändert nichts. Jetzt starten?`,
		() => {
			frm.call({
				doc: frm.doc,
				method: "start_export",
				freeze: true,
				freeze_message: __("Export wird gestartet …"),
			}).then(() => {
				frappe.show_alert(
					{ message: __("Der Export läuft jetzt im Hintergrund."), indicator: "blue" },
					5
				);
				frm.reload_doc();
			});
		}
	);
}

function download_package(frm) {
	if (!frm.doc.export_file) {
		frappe.msgprint(__("Es ist keine Datei hinterlegt. Bitte erstellen Sie den Export erneut."));
		return;
	}
	window.open(frm.doc.export_file);
}

// ------------------------------------------------------------------ progress

function watch_progress(frm) {
	if (!frm.__gdpdu_subscribed) {
		frappe.realtime.on("gdpdu_export_update", (data) => {
			if (data && data.name === frm.doc.name) {
				frm.reload_doc();
			}
		});
		frm.__gdpdu_subscribed = true;
	}

	if (frm.__gdpdu_timer) {
		clearTimeout(frm.__gdpdu_timer);
		frm.__gdpdu_timer = null;
	}

	// Fallback for setups without a websocket connection.
	if (BUSY_STATES.includes(frm.doc.status)) {
		frm.__gdpdu_timer = setTimeout(() => {
			if (!frm.is_dirty()) {
				frm.reload_doc();
			}
		}, POLL_INTERVAL);
	}
}
