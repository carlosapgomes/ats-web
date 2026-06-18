# Tasks: Emails transacionais para autenticação e cadastro

## Slices verticais

- [x] Slice 000 — ADR + OpenSpec/design do change (`slices/slice-000-adr-and-openspec.md`)
- [ ] Slice 001 — Password reset transacional end-to-end (`slices/slice-001-password-reset.md`)
- [ ] Slice 002 — Perfil do usuário + alteração de senha mantendo sessão atual (`slices/slice-002-profile-password-change.md`)
- [ ] Slice 003 — Email automático de cadastro/ativação via token nativo (`slices/slice-003-registration-email.md`)
- [ ] Slice 004 — Hardening futuro/opcional (`slices/slice-004-hardening-followups.md`)

## Definition of Done do change

- [ ] ADR-0002 criada e indexada.
- [ ] Configuração de email por env vars documentada e implementada.
- [ ] Fluxo “esqueci minha senha” disponível na tela de login.
- [ ] Reset de senha usa token nativo do Django e não revela existência de email.
- [ ] Rate limit simples aplicado somente ao POST do password reset.
- [ ] Login e reset confirm possuem opção “mostrar senha”.
- [ ] Perfil autenticado disponível para usuário logado.
- [ ] Alteração de senha exige senha atual e mantém sessão atual.
- [ ] Password change possui opção “mostrar senha”.
- [ ] Criação de usuário pela gestão administrativa envia email automaticamente.
- [ ] Email de cadastro usa link de definição/redefinição de senha com token nativo.
- [ ] Usuários apenas `nir`/`scheduler` recebem link com `INTERNAL_APP_BASE_URL`.
- [ ] Usuários com qualquer papel `doctor`/`manager`/`admin` recebem link com `PUBLIC_APP_BASE_URL`.
- [ ] Envio permanece síncrono; `django-q2` não é usado para emails neste change.
- [ ] Nenhuma notificação operacional de caso é enviada por email.
- [ ] Testes relevantes adicionados/ajustados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório de cada slice gerado em markdown temporário.
- [ ] Commit e push realizados após cada slice.

## Observações para implementadores

- Implementar somente o próximo slice incompleto.
- Não iniciar slice seguinte sem confirmação explícita.
- Cada slice deve atualizar este arquivo quando concluído.
- Cada relatório deve incluir `REPORT_PATH=<temp-markdown-path>` para revisão por outro LLM.
