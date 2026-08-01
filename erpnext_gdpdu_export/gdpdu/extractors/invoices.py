"""Document level: outgoing and incoming invoices including their positions.

Source: submitted ``Sales Invoice`` / ``Purchase Invoice`` of the period and
their item rows (SPEC.md, stage 2). Read-only, chunked.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..formats import clean_text
from .base import ExtractionContext, iter_chunks

_INVOICES = """
	SELECT
		inv.name, inv.posting_date, inv.due_date, inv.currency, inv.conversion_rate,
		inv.net_total, inv.total_taxes_and_charges, inv.grand_total,
		inv.base_net_total, inv.base_total_taxes_and_charges, inv.base_grand_total,
		inv.is_return, inv.status, inv.remarks, inv.creation, inv.owner,
		{party_fields}
	FROM `tab{doctype}` inv
	WHERE inv.company = %(company)s
		AND inv.docstatus = 1
		AND inv.posting_date BETWEEN %(from_date)s AND %(to_date)s
	ORDER BY inv.posting_date, inv.name
"""

_ITEMS = """
	SELECT
		item.name, item.parent, item.idx, item.item_code, item.item_name, item.qty,
		item.uom, item.rate, item.net_amount, item.base_net_amount, item.cost_center,
		item.item_tax_template, item.{account_field} AS account
	FROM `tab{item_doctype}` item
	INNER JOIN `tab{doctype}` inv ON inv.name = item.parent
	WHERE inv.company = %(company)s
		AND inv.docstatus = 1
		AND inv.posting_date BETWEEN %(from_date)s AND %(to_date)s
	ORDER BY item.parent, item.idx
"""


def iter_sales_invoices(ctx: ExtractionContext) -> Iterator[dict]:
	for invoice in _fetch_invoices(ctx, "Sales Invoice", "inv.customer, inv.customer_name"):
		yield {
			"Debitor": invoice.customer,
			"DebitorName": invoice.customer_name,
			**_common_invoice_row(invoice),
		}


def iter_purchase_invoices(ctx: ExtractionContext) -> Iterator[dict]:
	party_fields = "inv.supplier, inv.supplier_name, inv.bill_no, inv.bill_date"
	for invoice in _fetch_invoices(ctx, "Purchase Invoice", party_fields):
		yield {
			"Kreditor": invoice.supplier,
			"KreditorName": invoice.supplier_name,
			"LieferantenBelegnummer": invoice.bill_no,
			"LieferantenBelegdatum": invoice.bill_date,
			**_common_invoice_row(invoice),
		}


def iter_sales_invoice_items(ctx: ExtractionContext) -> Iterator[dict]:
	for item in _fetch_items(ctx, "Sales Invoice", "Sales Invoice Item", "income_account"):
		yield {"Ertragskonto": ctx.account_key(item.account), **_common_item_row(item)}


def iter_purchase_invoice_items(ctx: ExtractionContext) -> Iterator[dict]:
	for item in _fetch_items(ctx, "Purchase Invoice", "Purchase Invoice Item", "expense_account"):
		yield {"Aufwandskonto": ctx.account_key(item.account), **_common_item_row(item)}


# ---------------------------------------------------------------- internals


def _fetch_invoices(ctx: ExtractionContext, doctype: str, party_fields: str):
	query = _INVOICES.format(doctype=doctype, party_fields=party_fields)
	return iter_chunks(query, _params(ctx), ctx.chunk_size)


def _fetch_items(ctx: ExtractionContext, doctype: str, item_doctype: str, account_field: str):
	query = _ITEMS.format(doctype=doctype, item_doctype=item_doctype, account_field=account_field)
	return iter_chunks(query, _params(ctx), ctx.chunk_size)


def _params(ctx: ExtractionContext) -> dict:
	return {"company": ctx.company, "from_date": ctx.from_date, "to_date": ctx.to_date}


def _common_invoice_row(invoice) -> dict:
	return {
		"Belegnummer": invoice.name,
		"Belegdatum": invoice.posting_date,
		"Faelligkeit": invoice.due_date,
		"Waehrung": invoice.currency,
		"Wechselkurs": invoice.conversion_rate,
		"Netto": invoice.net_total,
		"Steuer": invoice.total_taxes_and_charges,
		"Brutto": invoice.grand_total,
		"NettoFirmenwaehrung": invoice.base_net_total,
		"SteuerFirmenwaehrung": invoice.base_total_taxes_and_charges,
		"BruttoFirmenwaehrung": invoice.base_grand_total,
		"IstGutschrift": "1" if invoice.is_return else "0",
		"Status": invoice.status,
		"Buchungstext": clean_text(invoice.remarks),
		"ErfasstAm": invoice.creation,
		"ErfasstUm": invoice.creation,
		"ErfasstVon": invoice.owner,
	}


def _common_item_row(item) -> dict:
	return {
		"PositionsID": item.name,
		"Belegnummer": item.parent,
		"Position": item.idx,
		"Artikel": item.item_code,
		"Bezeichnung": item.item_name,
		"Menge": item.qty,
		"Einheit": item.uom,
		"Einzelpreis": item.rate,
		"Netto": item.net_amount,
		"NettoFirmenwaehrung": item.base_net_amount,
		"Kostenstelle": item.cost_center,
		"Steuervorlage": item.item_tax_template,
	}
