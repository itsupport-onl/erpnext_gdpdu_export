"""debitoren.csv and kreditoren.csv — customer and supplier master data (SPEC.md).

Only parties with a journal movement in the period are exported: they are the
ones the journal refers to, and exporting the full address book would hand out
more personal data than the tax audit requires.
"""

from __future__ import annotations

from collections.abc import Iterator

import frappe

from .base import ExtractionContext

CUSTOMER_TABLE_KEY = "customers"
SUPPLIER_TABLE_KEY = "suppliers"

_PARTIES_IN_PERIOD = """
	SELECT DISTINCT gle.party
	FROM `tabGL Entry` gle
	WHERE gle.company = %(company)s
		AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND IFNULL(gle.is_cancelled, 0) = 0
		AND gle.party_type = %(party_type)s
		AND IFNULL(gle.party, '') != ''
	ORDER BY gle.party
"""

_ADDRESSES = """
	SELECT
		link.link_name AS party, address.address_line1, address.address_line2,
		address.pincode, address.city, address.country
	FROM `tabAddress` address
	INNER JOIN `tabDynamic Link` link
		ON link.parent = address.name AND link.parenttype = 'Address'
	WHERE link.link_doctype = %(party_type)s
		AND link.link_name IN %(parties)s
	ORDER BY link.link_name, IFNULL(address.is_primary_address, 0) DESC, address.creation ASC
"""


def iter_customers(ctx: ExtractionContext) -> Iterator[dict]:
	yield from _iter_parties(ctx, "Customer", "customer_name")


def iter_suppliers(ctx: ExtractionContext) -> Iterator[dict]:
	yield from _iter_parties(ctx, "Supplier", "supplier_name")


def _iter_parties(ctx: ExtractionContext, party_type: str, name_field: str) -> Iterator[dict]:
	parties = _parties_in_period(ctx, party_type)
	if not parties:
		return

	details = _party_details(party_type, name_field, parties)
	addresses = _primary_addresses(party_type, parties)

	for party in parties:
		detail = details.get(party, {})
		address = addresses.get(party, {})
		street = " ".join(
			part for part in (address.get("address_line1"), address.get("address_line2")) if part
		)

		if not address:
			ctx.protocol.add_warning(
				code=f"missing_address_{party_type.lower()}",
				message=(
					"Für mindestens einen Geschäftspartner mit Buchungen ist keine Anschrift hinterlegt."
				),
				hint=(
					"Die Zeile wird ohne Adresse exportiert. Ergänzen Sie die Adresse im "
					"Stammsatz, damit der Prüfer die Angaben vollständig erhält."
				),
				sample=detail.get("party_name") or party,
			)

		yield {
			"Kennung": party,
			"Name": detail.get("party_name") or party,
			"Strasse": street,
			"PLZ": address.get("pincode"),
			"Ort": address.get("city"),
			"Land": address.get("country"),
			"UStIdNr": detail.get("tax_id"),
		}


def _parties_in_period(ctx: ExtractionContext, party_type: str) -> list[str]:
	rows = frappe.db.sql(
		_PARTIES_IN_PERIOD,
		{
			"company": ctx.company,
			"from_date": ctx.from_date,
			"to_date": ctx.to_date,
			"party_type": party_type,
		},
		as_dict=True,
	)
	return [row.party for row in rows]


def _party_details(party_type: str, name_field: str, parties: list[str]) -> dict[str, dict]:
	rows = frappe.get_all(
		party_type,
		filters={"name": ("in", parties)},
		fields=["name", f"{name_field} as party_name", "tax_id"],
	)
	return {row.name: {"party_name": row.party_name, "tax_id": row.tax_id} for row in rows}


def _primary_addresses(party_type: str, parties: list[str]) -> dict[str, dict]:
	rows = frappe.db.sql(
		_ADDRESSES,
		{"party_type": party_type, "parties": tuple(parties)},
		as_dict=True,
	)

	addresses: dict[str, dict] = {}
	for row in rows:
		# The query is ordered by primary flag first, so the first hit wins.
		addresses.setdefault(row.party, row)
	return addresses
