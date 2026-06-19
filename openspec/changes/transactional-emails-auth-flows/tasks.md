# Tasks: Emails transacionais para autenticação e cadastro

## Slices verticais

- [x] Slice 000 — ADR + OpenSpec/design do change (`slices/slice-000-adr-and-openspec.md`)
- [x] Slice 001 — Password reset transacional end-to-end (`slices/slice-001-password-reset.md`)
- [x] Slice 002 — Perfil do usuário + alteração de senha mantendo sessão atual (`slices/slice-002-profile-password-change.md`)
- [x] Slice 003 — Email automático de cadastro/ativação via token nativo (`slices/slice-003-registration-email.md`)
- [ ] Slice 004 — Hardening **futuro/opcional** (logs gunicorn, observabilidade SMTP) — fora do escopo deste change, a tratar como change separado (`slices/slice-004-hardening-followups.md`)

## Definition of Done do change

- [x] ADR-0002 criada e indexada.
- [x] Configuração de email por env vars documentada e implementada.
- [x] Fluxo “esqueci minha senha” disponível na tela de login.
- [x] Reset de senha usa token nativo do Django e não revela existência de email.
- [x] Rate limit simples aplicado somente ao POST do password reset.
- [x] Login e reset confirm possuem opção “mostrar senha”.
- [x] Perfil autenticado disponível para usuário logado.
- [x] Alteração de senha exige senha atual e mantém sessão atual.
- [x] Password change possui opção “mostrar senha”.
- [x] Criação de usuário pela gestão administrativa envia email automaticamente.
- [x] Email de cadastro usa link de definição/redefinição de senha com token nativo.
- [x] Usuários apenas `nir`/`scheduler` recebem link com `INTERNAL_APP_BASE_URL`.
- [x] Usuários com qualquer papel `doctor`/`manager`/`admin` recebem link com `PUBLIC_APP_BASE_URL`.
- [x] Envio permanece síncrono; `django-q2` não é usado para emails neste change.
- [x] Nenhuma notificação operacional de caso é enviada por email.
- [x] Testes relevantes adicionados/ajustados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório de cada slice gerado em markdown temporário (`tmp/slice-00{1,2,3}-*.md`).
- [x] Commit e push realizados após cada slice.

## Observações para implementadores

- Implementar somente o próximo slice incompleto.
- Não iniciar slice seguinte sem confirmação explícita.
- Cada slice deve atualizar este arquivo quando concluído.
- Cada relatório deve incluir `REPORT_PATH=<temp-markdown-path>` para revisão por outro LLM.
