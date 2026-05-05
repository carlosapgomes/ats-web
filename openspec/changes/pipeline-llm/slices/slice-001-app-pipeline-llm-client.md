# Slice 1: App Pipeline + LLM Client Abstraído

> **Status**: TODO
> **Depende de**: Fase 1 completa
> **Change**: `openspec/changes/pipeline-llm/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — regras do projeto, stack, comandos de validação
2. `docs/DOMAIN_ANALYSIS.md` — seção 6 (políticas clínicas), seção 3 (FSM)
3. `apps/cases/models.py` — Case, CaseStatus, FSM transitions
4. `apps/llm/models.py` — PromptTemplate (será usado pelo pipeline)
5. Legado `infrastructure/llm/llm_client.py` — protocol e static client

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Você está em `/home/carlos/projects/ats-web/`, projeto Django greenfield.
Fase 1 (Intake NIR) concluída: 144 testes, upload de PDF funciona.
Após upload, o caso fica em status `LLM_STRUCT`. Precisamos criar o app que vai processá-lo.

### Sua Tarefa

1. Criar app `apps/pipeline/` com estrutura mínima
2. Criar `LlmClient` protocol (Protocol class do typing)
3. Criar `StaticLlmClient` para testes (resposta fixa)
4. Criar `create_openai_client()` factory function
5. Configurar settings para LLM

### Dependência nova

```bash
uv add openai
```

### Arquivos a Criar (idealmente <= 6)

```
apps/pipeline/__init__.py              # Criar
apps/pipeline/apps.py                  # Criar (PipelineConfig)
apps/pipeline/llm.py                   # Criar (LlmClient protocol + implementations)
apps/pipeline/tests/__init__.py        # Criar
apps/pipeline/tests/test_llm_client.py # Criar
config/settings/base.py                # MODIFICAR: adicionar "apps.pipeline" + LLM settings
```

### Detalhes Técnicos

#### apps/pipeline/apps.py

```python
from django.apps import AppConfig

class PipelineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pipeline"
```

#### apps/pipeline/llm.py

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from django.conf import settings


@runtime_checkable
class LlmClient(Protocol):
    """Protocol for LLM chat completion."""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return completion text for the supplied prompts."""
        ...


class StaticLlmClient:
    """Test-friendly client returning a fixed response."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._response_text


class RecordingLlmClient:
    """Test client that records calls and returns configured responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = iter(responses or [])
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return next(self._responses, "")


def get_llm_client() -> LlmClient:
    """Factory: returns configured LLM client from settings."""
    factory_path = getattr(settings, "LLM_CLIENT_FACTORY", None)
    if factory_path is None:
        return StaticLlmClient(response_text='{"error": "no_llm_configured"}')

    from importlib import import_module
    module_path, func_name = factory_path.rsplit(".", 1)
    module = import_module(module_path)
    factory = getattr(module, func_name)
    return factory()


def create_openai_client() -> LlmClient:
    """Create OpenAI chat completions client from Django settings."""
    from openai import OpenAI

    api_key = settings.OPENAI_API_KEY
    model = settings.OPENAI_MODEL
    base_url = getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    class OpenAiLlmClient:
        def __init__(self, openai_client: OpenAI, model_name: str) -> None:
            self._client = openai_client
            self._model = model_name

        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("OpenAI returned empty content")
            return content

    return OpenAiLlmClient(client, model)
```

#### config/settings/base.py

Adicionar em `INSTALLED_APPS`:
```python
"apps.pipeline",
```

Adicionar no final do arquivo:
```python
# LLM Configuration
LLM_CLIENT_FACTORY = "apps.pipeline.llm.create_openai_client"
OPENAI_API_KEY = env.str("OPENAI_API_KEY", default="")
OPENAI_MODEL = env.str("OPENAI_MODEL", default="gpt-4o")
OPENAI_BASE_URL = env.str("OPENAI_BASE_URL", default="https://api.openai.com/v1")
```

Em `config/settings/test.py`:
```python
LLM_CLIENT_FACTORY = None  # Use StaticLlmClient in tests
```

### TDD — Testes

#### apps/pipeline/tests/test_llm_client.py

1. `test_static_client_returns_fixed_response`: StaticLlmClient("hello").complete() → "hello"
2. `test_recording_client_captures_calls`: RecordingLlmClient logs system_prompt + user_prompt
3. `test_recording_client_returns_sequential_responses`: múltiplas chamadas retornam em sequência
4. `test_get_llm_client_returns_static_when_no_factory`: settings sem factory → StaticLlmClient
5. `test_get_llm_client_calls_factory`: settings com factory path → chama factory
6. `test_openai_client_creates_with_settings`: create_openai_client usa settings (mock OpenAI)

### Critérios de Sucesso

```bash
uv add openai
uv run python manage.py check --settings=config.settings.dev
uv run pytest -v
# Esperado: todos passando, zero regressão
```

### Relatório

Gere `/tmp/slice-pipeline-001-report.md`.
Informe `REPORT_PATH=/tmp/slice-pipeline-001-report.md`.
