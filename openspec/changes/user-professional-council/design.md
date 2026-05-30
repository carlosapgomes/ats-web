# Design: Dados de conselho profissional no usuário

## Decisões

### D1: Campos diretamente em `apps.accounts.User`

Adicionar os dados ao modelo customizado `User`, porque:

- o projeto já usa `AbstractUser` customizado;
- o requisito atual é de no máximo um conselho principal por usuário;
- os dados precisam aparecer em listagens e interfaces de usuário;
- uma tabela separada aumentaria complexidade sem benefício imediato.

Campos propostos:

```python
class ProfessionalCouncil(models.TextChoices):
    COREN = "COREN", "COREN"
    CRM = "CRM", "CRM"

professional_council = models.CharField(
    "Conselho profissional",
    max_length=10,
    choices=ProfessionalCouncil.choices,
    blank=True,
)
professional_council_number = models.CharField(
    "Número do conselho profissional",
    max_length=30,
    blank=True,
)
```

### D2: Campos opcionais, mas consistentes em par

A regra de consistência deve ficar no modelo, idealmente em `User.clean()`, para não depender apenas da UI.

Regras:

- `professional_council == ""` e `professional_council_number == ""`: válido.
- conselho preenchido e número vazio: `ValidationError`.
- número preenchido e conselho vazio: `ValidationError`.
- ambos preenchidos: válido.

### D3: Número como texto

`professional_council_number` deve ser `CharField`, não inteiro, para preservar zeros à esquerda, pontuação eventual e formatos operacionais usados pelos conselhos.

### D4: Migration aditiva e segura

Criar migration em `apps/accounts/migrations/` adicionando os dois campos com `blank=True` e default implícito vazio. Não há backfill obrigatório.

### D5: UI administrativa SSR existente

Atualizar `apps/admin_ui/forms.py` e `templates/admin_ui/user_form.html` para criação/edição.

Na listagem `templates/admin_ui/user_list.html`, adicionar coluna `Conselho` com exibição compacta:

```text
CRM 12345
COREN 67890
—
```

### D6: Django Admin

Atualizar `apps/accounts/admin.py`:

- incluir os campos em `fieldsets`;
- incluir coluna opcional em `list_display` ou pelo menos `search_fields`/form admin se fizer sentido.

## Arquivos previstos

| Arquivo | Tipo | Alteração |
|---|---|---|
| `apps/accounts/models.py` | modificado | choices, campos e validação |
| `apps/accounts/migrations/000X_user_professional_council.py` | novo | migration aditiva |
| `apps/accounts/admin.py` | modificado | expor campos no Django Admin |
| `apps/accounts/tests/test_models.py` | modificado | testes de defaults e validação |
| `apps/admin_ui/forms.py` | modificado | incluir campos nos forms |
| `templates/admin_ui/user_form.html` | modificado | campos no formulário |
| `templates/admin_ui/user_list.html` | modificado | coluna de exibição |
| `apps/admin_ui/tests/test_users_crud.py` | modificado | testes create/update/list |

## Riscos e mitigação

- **Quebra de criação de usuários existente**: manter campos opcionais e atualizar testes existentes apenas quando necessário.
- **Validação não chamada por `.save()` direto**: garantir testes usando `full_clean()` para regra de modelo; forms devem acionar validação via `ModelForm.is_valid()`.
- **Layout da tabela**: coluna compacta, sem novos filtros neste slice.
