"""Extractors — one per exported table, all read-only.

Interface: ``iter_rows(ctx) -> Iterator[dict]`` where the dict keys are the
column names of the matching table in :mod:`gdpdu.schema`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from . import accounts, journal, parties, taxes
from .base import DEFAULT_CHUNK_SIZE, AccountInfo, ExtractionContext

EXTRACTORS: dict[str, Callable[[ExtractionContext], Iterator[dict]]] = {
	"journal": journal.iter_rows,
	"accounts": accounts.iter_rows,
	"customers": parties.iter_customers,
	"suppliers": parties.iter_suppliers,
	"taxes": taxes.iter_rows,
}


def get_extractor(table_key: str) -> Callable[[ExtractionContext], Iterator[dict]]:
	try:
		return EXTRACTORS[table_key]
	except KeyError:
		raise KeyError(f"No extractor registered for table {table_key!r}") from None


__all__ = [
	"DEFAULT_CHUNK_SIZE",
	"EXTRACTORS",
	"AccountInfo",
	"ExtractionContext",
	"get_extractor",
]
