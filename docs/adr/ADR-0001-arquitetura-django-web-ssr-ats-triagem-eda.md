# ADR-0001: Arquitetura Django Web SSR para ATS de Triagem EDA

## Status

Accepted

## Contexto

O sistema legado (`augmented-triage-system`) opera via salas Matrix com FastAPI,
SQLAlchemy e bots assíncronos. Precisamos reimplementar a funcionalidade como
um aplicativo web Django (PWA), sem migrar código ou dados.

Requisitos:
- Fluxo operacional completo: NIR (upload PDF) → médico (decisão) → agendador (confirmação) → NIR (fechamento)
- Pipeline LLM para extração estruturada e sugestão de decisão
- Decision engine determinístico (políticas clínicas EDA)
- Trilha de auditoria completa (quem fez o quê e quando)
- Acesso externo via túnel Cloudflare com SSL
- Restrição de intranet para papéis NIR e Agendador
- Multi-role com papel ativo selecionável pelo usuário

## Decisão

### Stack

| Camada | Tecnologia | Versão |
|--------|-----------|--------|
| Backend | Python | 3.13+ |
| Framework | Django | 5.2+ |
| Estados | django-fsm | latest |
| Filas | django-q2 | latest |
| Banco | PostgreSQL | 17+ |
| CSS | Bootstrap | 5.3 |
| JS | Vanilla | ES6+ |
| Empacotador | uv | latest |
| Testes | pytest | latest |
| Lint | ruff | latest |
| Types | mypy | latest |

### Arquitetura

- **Monolito Django SSR**: templates server-side, sem SPA, sem API REST.
- **PDF storage**: filesystem local (`MEDIA_ROOT`).
- **Notificações**: in-app (dentro do aplicativo), sem email/SMS/push.
- **Multi-role**: admin atribui múltiplos papéis; usuário escolhe papel ativo ao logar e pode trocar via avatar/perfil.
- **Intranet restriction**: middleware Django valida IP contra range configurado via `INTRANET_IP_RANGE` (CIDR) para papéis `nir` e `scheduler`.
- **Auditoria**: tabela `CaseEvent` append-only como única fonte de verdade sobre histórico.
- **Máquina de estados**: todos os 17 estados do legado preservados via django-fsm.
- **Cleanup**: marcar caso como `CLEANED` — caso sai das filas e só aparece na auditoria.

### Papéis

| Papel | Fila principal | Restrição de rede |
|-------|---------------|-------------------|
| `nir` | Upload + meus casos + resultado final | Intranet only |
| `doctor` | Fila médica + decisão | Qualquer lugar |
| `scheduler` | Fila agendamento + vinda imediata | Intranet only |
| `manager` | Dashboard + métricas + todos os casos | Qualquer lugar |
| `admin` | Tudo + gestão usuários + gestão prompts | Qualquer lugar |

### Simplificações vs Legado

1. **Rooms Matrix → Telas Django**: cada "Room" vira uma fila/página web.
2. **Template parsing desaparece**: formulários HTML substituem templates textuais.
3. **Reactions 👍 → Botão**: "Confirmar Recebimento" na tela de resultado.
4. **case_messages desaparece**: `CaseEvent` cobre toda a rastreabilidade.
5. **Jobs "post room" desaparecem**: SSR renderiza a informação, não precisa postar.
6. **Cleanup = marcar fechado**: sem redaction de dados.

### Entidades principais

- `User` (com M2M roles e active_role na sessão)
- `Role` (nir/doctor/scheduler/manager/admin)
- `Case` (17 estados FSM, 30+ campos)
- `CaseEvent` (auditoria append-only, ~40 tipos de evento)
- `PromptTemplate` (versionado, 1 ativo por nome)
- `SupervisorSummaryDispatch` (controle de resumos periódicos)

## Alternativas Consideradas

1. **SPA (React/Vue) + Django REST Framework**:
   - Vantagens: UX mais rica, offline capability
   - Desvantagens: complexidade 3x maior, não alinha com constraint de vanilla JS
   - Por que não: o AGENTS.md define explicitamente sem framework JS e sem DRF

2. **Manter todos os 17 estados** vs **Simplificar para ~11**:
   - Vantagens da simplificação: FSM mais enxuto
   - Desvantagens: perda de rastreabilidade granular na auditoria
   - Por que não escolhida: a auditoria requer saber quem fez o quê e quando em cada ponto

3. **S3/object storage para PDFs**:
   - Vantagens: escalabilidade, durability
   - Desvantagens: complexidade adicional, custo
   - Por que não: sistema hospitalar com volume controlado, filesystem local suficiente

4. **Notificações por email**:
   - Vantagens:reach maior
   - Desvantagens: dependência de SMTP, complexidade, risco de PHI em email
   - Por que não: todas as notificações são in-app por decisão de produto

## Consequências

### Positivas
- Stack simples e coeso (Django-only)
- SSR garante segurança (sem PHI no JS client-side)
- Formulários HTML eliminam toda a camada de template parsing do legado
- Multi-role dá flexibilidade operacional
- Intranet restriction via middleware é simples e auditável
- Auditoria append-only com CaseEvent cobre todas as necessidades

### Negativas/Trade-offs
- Monolito Django limita escalabilidade horizontal (aceitável para volume hospitalar)
- Filesystem local para PDFs requer backup externo
- PWA limitado (sem offline real, apenas cache de estáticos)
- Multi-role requer UX cuidadosa na seleção de papel ativo

### Riscos e Mitigações
- **PHI em filesystem**: mitigar com permissões restritas no diretório + backup criptografado
- **IP spoofing via Cloudflare**: mitigar validando `CF-Connecting-IP` header configurável
- **Lockout admin**: mitigar com regra de "pelo menos 1 admin ativo" (herdada do legado)
- **Sessão de papel ativo expirada**: mitigar com fallback para tela de seleção de papel
