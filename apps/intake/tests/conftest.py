"""Shared fixtures for intake tests.

App-specific fixtures only. Shared fixtures (user, case_factory, advance_to)
are in tests/shared_case_fixtures.py (loaded via root conftest.py).
"""

import pytest
from django.test import override_settings


@pytest.fixture
def colonoscopy_intake_enabled():
    """Liga a flag de intake de Colonoscopia durante o teste (D10, fix round 1).

    Desde o fix D10 corrigir/reprojetar para Colonoscopia ou EDA + Colonoscopia
    exige ``COLONOSCOPY_INTAKE_ENABLED=True`` (mesma derivação por jornada do
    combobox). Suítes que exercitam a MECÂNICA de correção com essas
    identidades declaram este fixture; a recusa com a flag DESLIGADA é fixada
    em ``test_expanded_procedure_correction``.
    """
    with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
        yield
