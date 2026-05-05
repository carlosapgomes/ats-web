# Design: Bootstrap Django ATS Core

## Context

Projeto greenfield. Este change cria toda a fundação do sistema. A análise de
domínio completa está em `docs/DOMAIN_ANALYSIS.md`. A ADR-0001 formaliza as
decisões arquiteturais.

## Goals / Non-Goals

**Goals:**

1. Estrutura do projeto Django funcional com `uv`.
2. Modelos de domínio criados e migrados (User, Role, Case, CaseEvent, PromptTemplate).
3. Login/logout com seleção de papel ativo.
4. Troca de papel via avatar/perfil.
5. Middleware de intranet guard.
6. Template base com Bootstrap 5.3 + header com badge de papel.
7. Quality gate configurado (ruff, mypy, pytest).

**Non-Goals:**

- Upload de PDF (change seguinte).
- Pipeline LLM (change seguinte).
- Fila médica / decisão médica (change seguinte).
- Fila do agendador (change seguinte).
- Dashboard supervisor (change seguinte).
- Gestão de prompts via UI (change seguinte).

## Decisions

### 1) Estrutura de apps Django

#### Decisão

```
ats_web/
├── config/               # settings, urls, wsgi, asgi
├── apps/
│   ├── accounts/         # User, Role, auth views, middleware
│   ├── cases/            # Case, CaseEvent, CaseStatus FSM
│   └── llm/              # PromptTemplate
├── templates/            # base.html, login, switch-role
├── static/               # css/, js/, vendor/ (Bootstrap)
├── manage.py
└── pyproject.toml
```

#### Racional

Separação por domínio (accounts, cases, llm). Apps de fluxo (intake, doctor,
scheduler, dashboard) serão adicionados em changes seguintes quando os modelos
base estiverem estáveis.

### 2) Modelo User com multi-role

#### Decisão

```python
class Role(models.Model):
    name = models.CharField(max_length=20, unique=True)
    # valores: nir, doctor, scheduler, manager, admin

class User(AbstractUser):
    roles = models.ManyToManyField(Role, related_name="users")
    account_status = models.CharField(
        max_length=10,
        choices=[("active", "Active"), ("blocked", "Blocked"), ("removed", "Removed")],
        default="active",
    )
    is_active = models.BooleanField(default=True)
```

O papel ativo é armazenado na **sessão Django** (`session["active_role"]`),
não no modelo. Ao logar, se o usuário tem 1 papel, é selecionado
automaticamente. Se tem múltiplos, redireciona para tela de seleção.

#### Alternativas consideradas

- `active_role` como campo no modelo: descartada porque cria race condition
  se o usuário abre múltiplas abas com papéis diferentes.
- Role como CharField sem tabela: descartada porque impede M2M e queries
  eficientes por papel.

### 3) Case FSM — 17 estados preservados

#### Decisão

Usar `django-fsm` com `FSMField`. Todos os 17 estados do legado são
preservados como choices. Cada transição registra um `CaseEvent` automaticamente.

```python
class CaseStatus(models.TextChoices):
    NEW = "NEW"
    R1_ACK_PROCESSING = "R1_ACK_PROCESSING"
    EXTRACTING = "EXTRACTING"
    LLM_STRUCT = "LLM_STRUCT"
    LLM_SUGGEST = "LLM_SUGGEST"
    R2_POST_WIDGET = "R2_POST_WIDGET"
    WAIT_DOCTOR = "WAIT_DOCTOR"
    DOCTOR_DENIED = "DOCTOR_DENIED"
    DOCTOR_ACCEPTED = "DOCTOR_ACCEPTED"
    R3_POST_REQUEST = "R3_POST_REQUEST"
    WAIT_APPT = "WAIT_APPT"
    APPT_CONFIRMED = "APPT_CONFIRMED"
    APPT_DENIED = "APPT_DENIED"
    FAILED = "FAILED"
    R1_FINAL_REPLY_POSTED = "R1_FINAL_REPLY_POSTED"
    WAIT_R1_CLEANUP_THUMBS = "WAIT_R1_CLEANUP_THUMBS"
    CLEANUP_RUNNING = "CLEANUP_RUNNING"
    CLEANED = "CLEANED"
```

Transições seguem exatamente o grafo documentado em `DOMAIN_ANALYSIS.md` seção 3.2.

### 4) CaseEvent — auditoria append-only

#### Decisão

```python
class CaseEvent(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="events")
    timestamp = models.DateTimeField(auto_now_add=True)
    actor_type = models.CharField(max_length=10)  # system, bot, human
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["case", "timestamp"]),
            models.Index(fields=["event_type", "timestamp"]),
        ]
```

Nenhum evento é editado ou removido. A única fonte de verdade sobre o
histórico do caso.

### 5) Middleware Intranet Guard

#### Decisão

```python
class IntranetGuardMiddleware:
    # Lê INTRANET_IP_RANGE do settings (formato CIDR, ex: "10.0.0.0/8")
    # Lê TRUSTED_PROXY_HEADER do settings (ex: "HTTP_CF_CONNECTING_IP")
    # Para cada request:
    #   1. Extrair IP do cliente
    #   2. Se user autenticado e active_role in {"nir", "scheduler"}
    #   3. Verificar se IP está dentro do range
    #   4. Se fora → 403 + evento de auditoria
```

O Cloudflare Tunnel padrão envia o IP real do cliente no header
`CF-Connecting-IP`. O `TRUSTED_PROXY_HEADER` default será
`HTTP_CF_CONNECTING_IP`. Em dev (sem Cloudflare), usa `REMOTE_ADDR`.

> **Nota**: confirmar na documentação do Cloudflare Tunnel qual header
> carrega o IP real do cliente. Se for diferente de `CF-Connecting-IP`,
> ajustar o default no settings.

#### Alternativas consideradas

- Validação por VLAN/VPN: descartada por depender de infra externa.
- Validação apenas no login: descartada porque não protege contra sessão
  hijacking externo.

### 6) Login com seleção de papel

#### Decisão

Fluxo de login:

```
POST /login/
  → autenticar credenciais (Django auth)
  → se inválido → renderizar login com erro
  → se válido:
     → se 1 papel: definir session["active_role"] e redirecionar para home
     → se múltiplos: redirecionar para /switch-role/
```

Troca de papel:

```
GET /switch-role/
  → listar papéis disponíveis como cards/botões

POST /switch-role/
  → validar que papel está em user.roles
  → se papel é nir/scheduler: validar IP contra intranet
  → definir session["active_role"]
  → redirecionar para home do papel
```

### 7) Template base com Bootstrap 5.3

#### Decisão

- Bootstrap 5.3 via CDN (a intranet tem acesso à internet).
- Header fixo com: logo, badge do papel ativo, avatar com dropdown (trocar papel, perfil, logout).
- Sidebar ou nav com links filtrados pelo papel ativo.
- Template base que todas as páginas herdam.
- Container responsivo com Bootstrap grid.

### 8) PDF storage local

#### Decisão

```python
# settings.py
MEDIA_ROOT = Path(BASE_DIR) / "media"
MEDIA_URL = "/media/"

# Case model
pdf_file = models.FileField(upload_to="pdfs/%Y/%m/")
```

Em produção, servir via whitenoise ou nginx alias. Não usar S3.

## Risks / Trade-offs

- **Migration inicial grande**: mitigar criando migrations incrementais por app.
- **Sessão de papel ativo pode expirar**: mitigar com fallback automático para
  seleção de papel quando `session["active_role"]` ausente.
- **IP spoofing**: mitigar configurando `TRUSTED_PROXY_HEADER` adequadamente
  para o túnel Cloudflare.

## Slice Plan

Este change será implementado em slices verticais:

### Slice 1: Bootstrap do projeto Django
- `pyproject.toml` com todas as dependências
- `config/settings/` (base, dev, prod)
- `config/urls.py`
- `manage.py`
- Primeira migration
- **Critério de sucesso**: `uv run python manage.py check` sem erros

### Slice 2: Modelos User + Role + autenticação
- App `accounts` com User e Role
- Login/logout views
- Seleção de papel no login
- Troca de papel via avatar
- **Critério de sucesso**: login funcional, papel ativo na sessão

### Slice 3: Modelo Case + CaseEvent + FSM
- App `cases` com Case e CaseEvent
- FSM com 17 estados e todas as transições
- Evento de auditoria automático em cada transição
- **Critério de sucesso**: caso criado, transição de estado, evento registrado

### Slice 4: Middleware Intranet Guard
- Middleware validando IP por papel
- Configuração via env vars
- **Critério de sucesso**: nir bloqueado de IP externo, doctor acessa normalmente

### Slice 5: Template base + Bootstrap 5.3
- `base.html` com header, nav, footer
- Header com badge de papel e avatar dropdown
- Bootstrap 5.3 configurado
- **Critério de sucesso**: renderização visual correta, nav filtrada por papel

### Slice 6: PromptTemplate model
- App `llm` com PromptTemplate
- Constraint de 1 ativo por nome
- **Critério de sucesso**: criar versão, ativar, desativar

### Slice 7: Quality gate completo
- pytest + pytest-django configurados
- ruff + mypy configurados
- CI-ready
- **Critério de sucesso**: `uv run ruff check . && uv run mypy . && uv run pytest` passa

## Open Questions

- **Cloudflare IP header**: assumir `CF-Connecting-IP` como default.
  Confirmar na documentação do Cloudflare Tunnel padrão. Se diferente,
  ajustar env var `TRUSTED_PROXY_HEADER`.

## Closed Questions

- ~~O diretório `MEDIA_ROOT` precisa de criptografia em repouso para LGPD?~~
  **Resposta**: Não precisa. Permissões de filesystem são suficientes.
- ~~O service worker PWA deve cache-ar o Bootstrap via CDN ou servir local?~~
  **Resposta**: CDN. A intranet tem acesso à internet.
