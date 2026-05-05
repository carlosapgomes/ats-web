# Slice 6: PromptTemplate Model

> **Status**: DONE
> **Depende de**: Slice 2 (accounts app com User)
> **Change**: `openspec/changes/bootstrap-django-ats-core/`

---

## Leitura Obrigatória Antes de Implementar

Antes de escrever qualquer código, leia estes arquivos na ordem:

1. `AGENTS.md` — regras do projeto, stack, comandos de validação, política de testes
2. `docs/adr/ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md` — decisão arquitetural aceita
3. `docs/DOMAIN_ANALYSIS.md` — análise completa de domínio (entidades, estados, transições, eventos, permissões, telas)

Estes documentos dão o contexto de **por que** cada modelo, estado e regra existe.
Sem lê-los, você não terá contexto do domínio clínico (triagem EDA, políticas de pré-operatório, fluxo NIR-médico-agendador).

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Você está em `/home/carlos/projects/ats-web/`, um projeto Django greenfield.
Os **Slices 1-5** já foram executados:
- Estrutura base + accounts (User/Role/auth) + cases (Case FSM + CaseEvent)
- Intranet guard + template base com Bootstrap 5.3

Leia `AGENTS.md` para regras do projeto.

### Sua Tarefa

Criar o app `llm` com o modelo `PromptTemplate` — prompts versionados para
a pipeline LLM (LLM1 e LLM2). Apenas 1 versão ativa por nome.

### Arquivos a Criar/Modificar (idealmente <= 5)

```
apps/llm/__init__.py
apps/llm/models.py       # PromptTemplate
apps/llm/admin.py        # admin registration
apps/llm/apps.py         # AppConfig
config/settings/base.py  # MODIFICAR: adicionar "apps.llm" em INSTALLED_APPS
```

### Detalhes Técnicos

#### apps/llm/models.py

```python
import uuid
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class PromptTemplate(models.Model):
    """Template de prompt versionado para LLM.

    Apenas 1 versão pode estar ativa por nome.
    A constraint é garantida em nível de aplicação (clean/save)
    e via unique constraint parcial no banco.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    version = models.PositiveIntegerField()
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        unique_together = [("name", "version")]
        ordering = ["-name", "-version"]
        indexes = [
            models.Index(fields=["name", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} v{self.version} {'[active]' if self.is_active else ''}"

    def clean(self):
        super().clean()
        if self.is_active:
            # Garantir apenas 1 ativo por nome
            active = PromptTemplate.objects.filter(
                name=self.name, is_active=True
            ).exclude(pk=self.pk)
            if active.exists():
                raise ValidationError(
                    f"Já existe uma versão ativa para '{self.name}'. "
                    "Desative a versão atual antes de ativar esta."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls, name: str) -> "PromptTemplate | None":
        """Retorna a versão ativa do prompt pelo nome."""
        return cls.objects.filter(name=name, is_active=True).first()

    def activate(self, user=None):
        """Ativa esta versão e desativa as demais do mesmo nome."""
        PromptTemplate.objects.filter(
            name=self.name, is_active=True
        ).exclude(pk=self.pk).update(is_active=False)
        self.is_active = True
        self.updated_by = user
        self.save()

    def deactivate(self, user=None):
        """Desativa esta versão."""
        self.is_active = False
        self.updated_by = user
        self.save()
```

### TDD — Testes a Escrever PRIMEIRO

Criar `apps/llm/tests/` com:

1. **test_models.py**:
   - `test_create_prompt_template`: criar template com nome, versão e conteúdo
   - `test_unique_name_version`: não pode criar 2 templates com mesmo nome+versão
   - `test_get_active_returns_active_version`: get_active retorna a versão ativa
   - `test_get_active_returns_none_when_no_active`: get_active retorna None se não há
   - `test_activate_deactivates_others`: ativar v2 desativa v1
   - `test_activate_sets_is_active`: activate() marca como ativo
   - `test_deactivate`: deactivate() marca como inativo
   - `test_cannot_have_two_active_same_name`: clean() rejeita 2 ativos com mesmo nome
   - `test_different_names_can_both_be_active`: nomes diferentes podem ter ativos independentes
   - `test_str_representation`: __str__ mostra nome, versão e status

### Critérios de Sucesso (Self-Eval Gates)

```bash
# Gate 1: migrations
uv run python manage.py makemigrations llm --settings=config.settings.dev
uv run python manage.py migrate --settings=config.settings.dev

# Gate 2: Django check
uv run python manage.py check --settings=config.settings.dev

# Gate 3: testes
uv run pytest apps/llm/tests/ -v

# Gate 4: regressão
uv run pytest -v
```

### Relatório

Gere `/tmp/slice-006-report.md`.
Informe `REPORT_PATH=/tmp/slice-006-report.md`.
