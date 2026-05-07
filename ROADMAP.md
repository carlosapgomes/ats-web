# ROADMAP — ATS Web

> Fases e changes previstos para a implementação completa do sistema.
> Cada change será expandido em proposal + design + slices quando for a vez de implementar.

---

## Fase 0 — Bootstrap ✅ (CONCLUÍDA)

**Change**: `openspec/archive/bootstrap-django-ats-core/`

Estrutura base do projeto Django: pyproject, config, User multi-role, Case FSM,
CaseEvent, PromptTemplate, intranet guard, template base Bootstrap.

- [x] **Slice 1**: Bootstrap projeto Django
- [x] **Slice 2**: User + Role + autenticação + troca de papel
- [x] **Slice 3**: Case FSM 17 estados + CaseEvent auditoria
- [x] **Slice 4**: Middleware intranet guard
- [x] **Slice 5**: Template base Bootstrap 5.3
- [x] **Slice 6**: PromptTemplate versionado
- [x] **Slice 7**: Quality gate completo (ruff + mypy + pytest)

---

## Fase 1 — Intake NIR ✅ (CONCLUÍDA)

Upload de PDF pelo NIR, criação do caso, fila de "meus casos", visualização básica.

**Change**: `openspec/archive/intake-nir/`

- [x] **Slice 1**: Tema hospitalar — paleta + fontes + header
- [x] **Slice 2**: App intake + decorator `role_required`
- [x] **Slice 3**: Upload de PDF + criação do caso + extração de texto
- [x] **Slice 4**: Meus Casos — lista com filtros e cards
- [x] **Slice 5**: Detalhe do caso — dados + PDF inline + timeline
- [x] **Slice 6**: Quality gate completo

---

## Fase 2 — Pipeline LLM ✅ (CONCLUÍDA)

Processamento automático do caso via LLM + decision engine determinístico.

**Change**: `openspec/archive/pipeline-llm/`

- [x] **Slice 1**: App pipeline + LLM client abstraído (OpenAI SDK)
- [x] **Slice 2**: Policy engine — EDA Preop Policy (thresholds, minimum exams, conditional gates)
- [x] **Slice 3**: Policy engine — Reconciliation + Support Synthesis
- [x] **Slice 4**: Scope Detection (EDA / non-EDA / unknown)
- [x] **Slice 5**: LLM1 Service + LLM2 Service (JSON parser + prompt rendering)
- [x] **Slice 6**: Pipeline orchestrator + django-q2 task + integração intake
- [x] **Slice 7**: Quality gate completo

---

## Fase 2b — Alinhamento Visual com Mocks ✅ (CONCLUÍDA)

Corrigir UI para ser visual e funcionalmente equivalente aos mocks de referência.

**Change**: `openspec/archive/ui-alinhamento-mocks/`

- [x] **Slice 1**: Infra de estáticos + CSS completo + .env loading
- [x] **Slice 2**: Templates alinhados com mocks + middleware multi-range + home redirect
- [x] **Slice 3**: Quality gate completo

---

## Fase 3 — Fila Médica (Doctor)

Decisão médica sobre casos processados.

**Change**: `openspec/changes/doctor-queue/`

- [x] **Slice 1**: App doctor + queue view + templates alinhados com mocks ✅
- [x] **Slice 2**: Decision view + form condicional + FSM transitions ✅
- [x] **Slice 3**: Quality gate completo ✅

**331 testes, 3 slices + 2 follow-ups, arquivado em `openspec/archive/doctor-queue/`**

---

## Fase 4 — Fila do Agendador (Scheduler)

Agendamento ou notificação de vinda imediata.

**Change**: `openspec/changes/scheduler-queue/`

- [x] **Slice 1**: App scheduler + queue view + templates + auto-transition ✅
- [x] **Slice 2**: Confirm view + form condicional + FSM transitions ✅
- [x] **Slice 3**: Quality gate completo ✅

**356 testes, arquivado em `openspec/archive/scheduler-queue/`**

---

## Fase 5 — Resultado Final NIR + Fechamento

Resultado volta ao NIR, confirmação e cleanup.

**Change**: `openspec/changes/nir-result-closure/`

- [x] **Slice 1**: Resultado final + auto-transição + nome do paciente no case_detail ✅
- [x] **Slice 2**: Quality gate completo ✅

**368 testes, arquivado em `openspec/archive/nir-result-closure/`**

---

## Fase 6 — Dashboard Supervisor

Visão gerencial e operacional para managers/admins.

- Dashboard com métricas do período:
  - Pacientes recebidos, processados, avaliados
  - Aceitos (agendamento), vinda imediata, recusados
  - Em andamento (por etapa)
- Lista de todos os casos com filtros (status, etapa, resultado, data)
- Paginação
- Detalhe do caso com timeline completa (todos os CaseEvents)

---

## Fase 7 — Administração

Gestão de usuários e prompts pelo admin via UI.

- CRUD de usuários (criar, bloquear, reativar, remover)
- Atribuição de papéis (multi-role)
- Proteções: não auto-bloquear, não deixar sem admin ativo
- CRUD de prompts (criar versão, ativar, desativar)
- Trilha de auditoria de ações administrativas

---

## Fase 8 — Resumo Periódico

Geração automática de resumos operacionais.

- Cron job django-q2 com janelas configuráveis (cutoffs)
- Agregação de métricas por janela
- Persistência do resumo (SupervisorSummaryDispatch)
- Exibição no dashboard do supervisor
- Idempotência: não gerar duplicatas para mesma janela

---

## Fase 9 — Prior Case Lookup

Consulta de casos anteriores do mesmo paciente.

- Busca por agency_record_number
- Detectar negações recentes (7 dias)
- Exibir contexto de caso anterior na tela de decisão médica
- Registrar lookup como evento auditável

---

## Fase 10 — PWA e Polish

Transformar em PWA instalável e refinamentos de UX.

- manifest.json (nome, ícone, tema)
- Service worker mínimo (cache de estáticos)
- Meta tags viewport, theme-color, apple-mobile-web-app
- Prompt de instalação
- Badges de contagem nas filas (novo caso, decisão pendente)
- Responsividade mobile

---

## Dependências entre fases

```
Fase 0 (bootstrap) ✅ CONCLUÍDA
  ├── Fase 1 (intake NIR) ✅ CONCLUÍDA
  │     └── Fase 2 (pipeline LLM) ✅ CONCLUÍDA
  │           └── Fase 2b (alinhamento visual) ✅ CONCLUÍDA
  │                 └── Fase 3 (fila médica) ← próxima, precisa de LLM artifacts + UI alinhada
  │                 ├── Fase 4 (fila agendador) ← precisa de decisão médica
  │                 └── Fase 5 (resultado NIR) ← precisa de decisão + agendamento
  ├── Fase 6 (dashboard) ← precisa de Case + CaseEvent
  └── Fase 7 (administração) ← precisa de User + PromptTemplate

Fase 8 (resumo periódico) ← precisa de django-q2 + dados operacionais
Fase 9 (prior case lookup) ← precisa de casos suficientes
Fase 10 (PWA) ← pode ser feito a qualquer momento após Fase 5
```

---

## Referências

- `docs/DOMAIN_ANALYSIS.md` — análise completa de domínio
- `docs/adr/ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md` — decisão arquitetural

## Dívida Técnica

- **django-fsm → viewflow.fsm**: `django-fsm` 3.0+ está deprecated, integrado ao `viewflow.fsm`. Migrar quando houver necessidade de novos recursos ou quando o pacote parar de funcionar com Django futuro. Não urgente.
