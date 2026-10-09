"""Guard de persistibilidade para artefatos LLM (S1/D7).

O PostgreSQL rejeita U+0000 em JSONB/texto (``UntranslatableCharacter``). Um
artefato LLM contaminado falha no save — e o handler antigo regravava a
MESMA instancia contaminada, perdendo tambem o registro da falha (orfao
5074806). Este modulo oferece a rejeicao ANTES de qualquer write, com erro
tipado de conteudo tecnico limitado (sem raw/excerpt clinico).

Decodificar o JSON antes de verificar: o escape ``\\u0000`` vira o caractere
real e deve falhar; o literal de seis caracteres barra-u-0000 NAO e NUL e
passa intacto (nunca sanitizar/reescrever conteudo clinico em silencio).
"""

from __future__ import annotations

from typing import Any

LLM_OUTPUT_NOT_PERSISTABLE_CODE = "llm_output_not_persistable"

_MAX_PATH_CHARS = 200


class LlmOutputNotPersistableError(ValueError):
    """Artefato LLM contem dado que o banco nao persiste (U+0000).

    Atributos ``stage`` (``llm1``/``llm2``) e ``path`` (caminho tecnico
    limitado, sem valores clinicos) permitem diagnostico sem vazar conteudo.
    """

    def __init__(self, *, stage: str, path: str) -> None:
        self.stage = stage
        self.path = path[:_MAX_PATH_CHARS]
        self.error_code = LLM_OUTPUT_NOT_PERSISTABLE_CODE
        super().__init__(
            f"Saida LLM nao persistivel (stage={stage}, path={self.path}): caractere NUL rejeitado antes de writes."
        )


def assert_persistable(value: Any, *, stage: str, path: str = "output") -> None:
    """Rejeita U+0000 em strings/chaves/valores aninhados (dicts, listas, tuplas).

    Levanta :class:`LlmOutputNotPersistableError` no primeiro NUL encontrado.
    Escalares nao-string sao ignorados; o literal de seis caracteres
    barra-u-0000 nao contem NUL real e passa sem modificacao.

    Diagnostico S1/D7 (P1-B): o caminho e puramente estrutural
    (``[key]``/``[indice]`` sobre a raiz tecnica do chamador). O texto da
    chave de dicionario — controlado pelo LLM/não confiavel — NUNCA entra
    no diagnostico: uma chave rejeitada com NUL contaminaria a mensagem e o
    payload de falha, que o PostgreSQL rejeitaria de novo, alem de poder
    vazar texto clinico para logs.
    """
    if isinstance(value, str):
        if "\x00" in value:
            raise LlmOutputNotPersistableError(stage=stage, path=path)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and "\x00" in key:
                raise LlmOutputNotPersistableError(stage=stage, path=f"{path}[key]")
            assert_persistable(item, stage=stage, path=f"{path}[key]")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_persistable(item, stage=stage, path=f"{path}[{index}]")
        return


def assert_llm1_persistable(*, structured_data: dict[str, object], summary_text: str) -> None:
    """Verifica o resultado LLM1 antes de projecao/artefato (R2)."""
    assert_persistable(structured_data, stage="llm1", path="structured_data")
    assert_persistable(summary_text, stage="llm1", path="summary_text")


def assert_llm2_persistable(*, procedure_recommendations: list[dict[str, object]]) -> None:
    """Verifica o resultado LLM2 antes de recomendacao/WAIT_DOCTOR (R2)."""
    assert_persistable(procedure_recommendations, stage="llm2", path="procedure_recommendations")
