"""Slice 001 — tabela-verdade exaustiva de ``best_covering_selection``.

Fundação do change ``normalize-detected-set-to-valid-selection`` (ADR-0011
decisão 1): a função devolve a seleção válida mais completa que cobre o
conjunto detectado, com a sentinela ``invalid`` quando nenhuma combinação da
matriz cobre — inclusive para o conjunto vazio (divergência deliberada de
``selection_key(()) == ""``, documentada na docstring da função).

Cobre:
- R1: função total e pura — deduplica exatamente, nunca filtra valores fora do
  catálogo para fabricar validade, independe de ordem/tipo de coleção e não
  muta a entrada;
- R2: tabela-verdade completa (singletons; par exato; base absorvida por
  pacote nos cinco pares; vazio; duas variações da mesma base; variação +
  colonoscopia; dois especializados; especializado + convencional;
  desconhecido sozinho e misto);
- R2b: ``PROCEDURE_PACKAGE_BASES`` é a constante autoritativa equivalente ao
  mapa do pipeline (guarda anti-drift; a troca do import no pipeline é do
  slice 002).
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.cases.models import EDA_COLONOSCOPY, ProcedureType
from apps.cases.procedures import (
    INVALID_SELECTION_KEY,
    PROCEDURE_PACKAGE_BASES,
    SUPPORTED_PROCEDURE_TYPES,
    best_covering_selection,
    selection_key,
)

IDENTITIES: tuple[str, ...] = SUPPORTED_PROCEDURE_TYPES

# Pacote atômico -> base convencional que ele clinicamente contém (ADR-0011 D1).
PACKAGE_BASE_PAIRS: tuple[tuple[str, str], ...] = (
    (ProcedureType.EDA_GASTROSTOMY, ProcedureType.EDA),
    (ProcedureType.EDA_CAPSULE, ProcedureType.EDA),
    (ProcedureType.EDA_DILATION, ProcedureType.EDA),
    (ProcedureType.RECTOSIGMOIDOSCOPY_DILATION, ProcedureType.RECTOSIGMOIDOSCOPY),
    (ProcedureType.RECTOSIGMOIDOSCOPY_ARGON, ProcedureType.RECTOSIGMOIDOSCOPY),
)


class TestSingletonSelection:
    @pytest.mark.parametrize("code", IDENTITIES)
    def test_singleton_returns_its_own_key(self, code: str) -> None:
        assert best_covering_selection((code,)) == code


class TestExactPairSelection:
    @pytest.mark.parametrize(
        "detected",
        [
            (ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            (ProcedureType.COLONOSCOPY, ProcedureType.EDA),
            [ProcedureType.COLONOSCOPY, ProcedureType.EDA],
            {ProcedureType.EDA, ProcedureType.COLONOSCOPY},
        ],
    )
    def test_exact_pair_returns_combined_key(self, detected: Any) -> None:
        assert best_covering_selection(detected) == EDA_COLONOSCOPY


class TestPackageAbsorbsBase:
    @pytest.mark.parametrize(("package", "base"), PACKAGE_BASE_PAIRS)
    def test_base_plus_its_package_returns_the_package(self, package: str, base: str) -> None:
        assert best_covering_selection((base, package)) == package
        assert best_covering_selection((package, base)) == package


class TestTotalAndPure:
    def test_equivalent_collections_of_different_types_agree(self) -> None:
        expected = EDA_COLONOSCOPY
        assert best_covering_selection(("eda", "colonoscopy")) == expected
        assert best_covering_selection(["colonoscopy", "eda"]) == expected
        assert best_covering_selection({"eda", "colonoscopy"}) == expected
        assert best_covering_selection(frozenset({"colonoscopy", "eda"})) == expected

    def test_exact_duplicates_are_deduplicated_first(self) -> None:
        assert best_covering_selection(["eda", "eda"]) == ProcedureType.EDA
        assert best_covering_selection(["eda", "colonoscopy", "colonoscopy"]) == EDA_COLONOSCOPY
        assert best_covering_selection(("eda", "eda_dilation", "eda")) == ProcedureType.EDA_DILATION

    def test_does_not_mutate_the_input(self) -> None:
        detected = ["eda", "eda_dilation"]
        best_covering_selection(detected)
        assert detected == ["eda", "eda_dilation"]

    def test_empty_collection_returns_the_reserved_sentinel(self) -> None:
        assert best_covering_selection(()) == INVALID_SELECTION_KEY
        assert best_covering_selection([]) == INVALID_SELECTION_KEY
        assert best_covering_selection(set()) == INVALID_SELECTION_KEY
        assert best_covering_selection(None) == INVALID_SELECTION_KEY

    def test_empty_diverges_from_selection_key_empty_string(self) -> None:
        assert selection_key(()) == ""
        assert best_covering_selection(()) == INVALID_SELECTION_KEY


class TestFailClosedSets:
    @pytest.mark.parametrize(
        "detected",
        [
            (ProcedureType.EDA_CAPSULE, ProcedureType.EDA_DILATION),
            (ProcedureType.EDA, ProcedureType.EDA_CAPSULE, ProcedureType.EDA_DILATION),
            (
                ProcedureType.RECTOSIGMOIDOSCOPY,
                ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
                ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
            ),
        ],
    )
    def test_two_variations_of_the_same_base_are_invalid(self, detected: Any) -> None:
        assert best_covering_selection(detected) == INVALID_SELECTION_KEY

    @pytest.mark.parametrize(
        "detected",
        [
            (ProcedureType.EDA_DILATION, ProcedureType.COLONOSCOPY),
            (ProcedureType.EDA_CAPSULE, ProcedureType.COLONOSCOPY),
            (ProcedureType.RECTOSIGMOIDOSCOPY_DILATION, ProcedureType.COLONOSCOPY),
        ],
    )
    def test_variation_with_colonoscopy_is_invalid(self, detected: Any) -> None:
        assert best_covering_selection(detected) == INVALID_SELECTION_KEY

    def test_two_specialized_types_are_invalid(self) -> None:
        assert best_covering_selection((ProcedureType.ECHOENDOSCOPY, ProcedureType.CPRE)) == INVALID_SELECTION_KEY

    @pytest.mark.parametrize(
        "detected",
        [
            (ProcedureType.EDA, ProcedureType.ECHOENDOSCOPY),
            (ProcedureType.COLONOSCOPY, ProcedureType.CPRE),
            (ProcedureType.EDA, ProcedureType.COLONOSCOPY, ProcedureType.CPRE),
        ],
    )
    def test_specialized_with_conventional_types_is_invalid(self, detected: Any) -> None:
        # A função é pura: a precedência especializado→convencional (ADR-0008)
        # acontece ANTES, fora do helper, sobre o conjunto bruto detectado.
        assert best_covering_selection(detected) == INVALID_SELECTION_KEY

    @pytest.mark.parametrize("detected", [("unknown",), ("",), ("eda_typo",)])
    def test_unknown_value_alone_is_invalid(self, detected: Any) -> None:
        assert best_covering_selection(detected) == INVALID_SELECTION_KEY

    @pytest.mark.parametrize(
        "detected",
        [
            ("eda", "unknown"),
            ("eda_capsule", "unknown"),
            ("eda", "colonoscopy", "unknown"),
        ],
    )
    def test_unknown_value_mixed_is_never_filtered_into_validity(self, detected: Any) -> None:
        assert best_covering_selection(detected) == INVALID_SELECTION_KEY


class TestProcedurePackageBasesContract:
    def test_entries_are_the_five_package_base_relations(self) -> None:
        assert PROCEDURE_PACKAGE_BASES == {package: base for package, base in PACKAGE_BASE_PAIRS}

    def test_entries_are_atomic_catalog_identities(self) -> None:
        used = set(PROCEDURE_PACKAGE_BASES) | set(PROCEDURE_PACKAGE_BASES.values())
        assert used <= set(SUPPORTED_PROCEDURE_TYPES)

    def test_matches_the_pipeline_variation_base_map(self) -> None:
        # Import local: ``apps.cases`` (produção) não importa ``apps.pipeline``
        # (layering cases←pipeline). Aqui é só a guarda anti-drift do slice 001.
        from apps.pipeline.procedure_reconciliation import _VARIATION_BASE_TYPES

        assert PROCEDURE_PACKAGE_BASES == _VARIATION_BASE_TYPES
