"""Test base class that works on Frappe v15 and v16.

v15 only ships ``frappe.tests.utils.FrappeTestCase``. v16 introduces
``frappe.tests.IntegrationTestCase`` and deprecates the old name, so the new
one is preferred whenever it exists.

This module is deliberately not named ``test_*`` so that the site-free unit test
discovery never imports it (it needs Frappe).
"""

from __future__ import annotations

try:  # Frappe v16+
	from frappe.tests import IntegrationTestCase as AppTestCase

	LEGACY_TEST_RUNNER = False
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as AppTestCase

	LEGACY_TEST_RUNNER = True

__all__ = ["LEGACY_TEST_RUNNER", "AppTestCase"]
