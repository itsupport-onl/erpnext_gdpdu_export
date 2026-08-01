"""Open items at the end of the export period (SPEC.md, stage 2).

The balances are computed from the journal instead of the current outstanding
amount of the documents, so the result really is the state at the key date.
ERPNext points from a payment or credit note to the original invoice via
``against_voucher``; that is what the rows are grouped by.
"""

from __future__ import annotations

from collections.abc import Iterator

import frappe

from .base import ExtractionContext

CUSTOMER = "Customer"
SUPPLIER = "Supplier"

_ACCOUNT_TYPES = {CUSTOMER: "Receivable", SUPPLIER: "Payable"}

#: Debit balances are open for customers, credit balances for suppliers.
_BALANCE = {CUSTOMER: "SUM(gle.debit - gle.credit)", SUPPLIER: "SUM(gle.credit - gle.debit)"}

#: The settled document: a payment or credit note points to the original invoice
#: via ``against_voucher``, everything else stands for itself.
_VOUCHER = "COALESCE(NULLIF(gle.against_voucher, ''), gle.voucher_no)"
_VOUCHER_TYPE = "COALESCE(NULLIF(gle.against_voucher_type, ''), gle.voucher_type)"

# GROUP BY repeats the full expressions on purpose: MariaDB resolves a GROUP BY
# alias that matches an existing column (voucher_type!) to the column, which
# would put an invoice and its payment into separate groups.
_OPEN_ITEMS = """
	SELECT
		gle.party AS party,
		{voucher} AS open_voucher,
		MIN({voucher_type}) AS open_voucher_type,
		gle.account AS account,
		MIN(gle.posting_date) AS posting_date,
		{balance} AS open_amount
	FROM `tabGL Entry` gle
	INNER JOIN `tabAccount` acc ON acc.name = gle.account
	WHERE gle.company = %(company)s
		AND gle.posting_date <= %(to_date)s
		AND IFNULL(gle.is_cancelled, 0) = 0
		AND gle.party_type = %(party_type)s
		AND IFNULL(gle.party, '') != ''
		AND acc.account_type = %(account_type)s
	GROUP BY gle.party, {voucher}, gle.account
	HAVING ROUND({balance}, 2) <> 0
	ORDER BY gle.party, open_voucher
"""


def get_open_items(ctx: ExtractionContext, party_type: str) -> list:
	"""Return the open items of one party type; cached because two tables need them."""
	cache_key = ("open_items", party_type)
	if cache_key not in ctx.cache:
		ctx.cache[cache_key] = frappe.db.sql(
			_OPEN_ITEMS.format(
				balance=_BALANCE[party_type],
				voucher=_VOUCHER,
				voucher_type=_VOUCHER_TYPE,
			),
			{
				"company": ctx.company,
				"to_date": ctx.to_date,
				"party_type": party_type,
				"account_type": _ACCOUNT_TYPES[party_type],
			},
			as_dict=True,
		)
	return ctx.cache[cache_key]


def get_parties_with_open_items(ctx: ExtractionContext, party_type: str) -> set[str]:
	"""Parties that still have an open item — their master data must be exported."""
	return {row.party for row in get_open_items(ctx, party_type) if row.party}


def iter_customers(ctx: ExtractionContext) -> Iterator[dict]:
	yield from _iter_rows(ctx, CUSTOMER)


def iter_suppliers(ctx: ExtractionContext) -> Iterator[dict]:
	yield from _iter_rows(ctx, SUPPLIER)


def _iter_rows(ctx: ExtractionContext, party_type: str) -> Iterator[dict]:
	for row in get_open_items(ctx, party_type):
		yield {
			"Partei": row.party,
			"Beleg": row.open_voucher,
			"Konto": ctx.account_key(row.account),
			"Belegart": row.open_voucher_type,
			"Belegdatum": row.posting_date,
			"OffenerBetrag": row.open_amount,
			"Waehrung": ctx.currency,
			"Stichtag": ctx.to_date,
		}
