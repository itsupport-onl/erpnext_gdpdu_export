"""Payments and their allocation to the settled documents (SPEC.md, stage 2).

Source: submitted ``Payment Entry`` of the period and its reference rows.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..formats import clean_text
from .base import ExtractionContext, iter_chunks

_PAYMENTS = """
	SELECT
		pe.name, pe.posting_date, pe.payment_type, pe.party_type, pe.party,
		pe.paid_from, pe.paid_to, pe.paid_amount, pe.base_paid_amount,
		pe.paid_from_account_currency, pe.reference_no, pe.reference_date,
		pe.remarks, pe.creation, pe.owner
	FROM `tabPayment Entry` pe
	WHERE pe.company = %(company)s
		AND pe.docstatus = 1
		AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
	ORDER BY pe.posting_date, pe.name
"""

_ALLOCATIONS = """
	SELECT
		ref.name, ref.parent, ref.reference_doctype, ref.reference_name, ref.allocated_amount
	FROM `tabPayment Entry Reference` ref
	INNER JOIN `tabPayment Entry` pe ON pe.name = ref.parent
	WHERE pe.company = %(company)s
		AND pe.docstatus = 1
		AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
	ORDER BY ref.parent, ref.idx
"""


def iter_rows(ctx: ExtractionContext) -> Iterator[dict]:
	for payment in iter_chunks(_PAYMENTS, _params(ctx), ctx.chunk_size):
		yield {
			"Zahlungsnummer": payment.name,
			"Buchungsdatum": payment.posting_date,
			"Zahlungsart": payment.payment_type,
			"GegenparteiTyp": payment.party_type,
			"Gegenpartei": payment.party,
			"KontoVon": ctx.account_key(payment.paid_from),
			"KontoNach": ctx.account_key(payment.paid_to),
			"Betrag": payment.paid_amount,
			"Waehrung": payment.paid_from_account_currency or ctx.currency,
			"BetragFirmenwaehrung": payment.base_paid_amount,
			"Referenz": payment.reference_no,
			"Referenzdatum": payment.reference_date,
			"Buchungstext": clean_text(payment.remarks),
			"ErfasstAm": payment.creation,
			"ErfasstUm": payment.creation,
			"ErfasstVon": payment.owner,
		}


def iter_allocations(ctx: ExtractionContext) -> Iterator[dict]:
	for allocation in iter_chunks(_ALLOCATIONS, _params(ctx), ctx.chunk_size):
		yield {
			"ZuordnungsID": allocation.name,
			"Zahlungsnummer": allocation.parent,
			"Belegart": allocation.reference_doctype,
			"Belegnummer": allocation.reference_name,
			"ZugeordneterBetrag": allocation.allocated_amount,
		}


def _params(ctx: ExtractionContext) -> dict:
	return {"company": ctx.company, "from_date": ctx.from_date, "to_date": ctx.to_date}
