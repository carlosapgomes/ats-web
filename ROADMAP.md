# ROADMAP — ATS Web

> Fases e changes previstos para a implementação completa do sistema.
> Cada change será expandido em proposal + design + slices quando for a vez de implementar.

---

## Fase 0 — Bootstrap ✅ (CONCLUÍDA)

**Change**: `openspec/changes/bootstrap-django-ats-core/`

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

## Fase 1 — Intake NIR

Upload de PDF pelo NIR, criação do caso, fila de "meus casos", visualização básica.

**Change**: `openspec/changes/intake-nir/`

- [ ] **Slice 1**: Tema hospitalar — paleta + fontes + header
- [ ] **Slice 2**: App intake + decorator `role_required`
- [ ] **Slice 3**: Upload de PDF + criação do caso + extração de texto
- [ ] **Slice 4**: Meus Casos — lista com filtros e cards
- [ ] **Slice 5**: Detalhe do caso — dados + PDF inline + timeline
- [ ] **Slice 6**: Quality gate completo

---

## Fase 2 — Pipeline LLM

Processamento automático do caso via LLM + decision engine determinístico.

- Integração com OpenAI (client abstraído, injetável)
- **LLM1**: extração estruturada (patient, EDA, labs, ECG, ASA, policy_precheck)
- **LLM2**: sugestão de decisão (accept/deny + support + rationale)
- **EDA Preop Policy**: engine determinístico de regras (thresholds, minimum exams, conditional gates)
- **EDA Policy Reconciliation**: hard rules sobre saída LLM2, registro de contradições
- **Support Synthesis**: derivação ASA + risco cardiovascular → recomendação de suporte
- **Scope Detection**: detectar se exame é EDA; se não → manual_review (pula médico)
- Job assíncrono via django-q2 para pipeline completa
- Persistência de artifacts no Case (structured_data, summary_text, suggested_action)

---

## Fase 3 — Fila Médica (Doctor)

Decisão médica sobre casos processados.

- Tela de fila médica (casos em WAIT_DOCTOR)
- Tela de detalhe para decisão:
  - PDF inline
  - Dados estruturados (patient, labs, ECG, ASA)
  - Sugestão LLM + resultado do policy engine
  - Prior case lookup (negações recentes do mesmo registro)
- Formulário de decisão:
  - decision: accept / deny
  - support_flag (se accept): none / anesthesist / anesthesist_icu
  - admission_flow (se accept): scheduled / immediate
  - reason (se deny): texto livre
- Transição FSM: WAIT_DOCTOR → DOCTOR_ACCEPTED / DOCTOR_DENIED
- Evento auditável da decisão

---

## Fase 4 — Fila do Agendador (Scheduler)

Agendamento ou notificação de vinda imediata.

- Tela de fila do agendador (casos em WAIT_APPT)
- Seção separada para notificações de vinda imediata (somente leitura)
- Tela de agendamento:
  - Formulário: confirmed/denied, data/hora, local, instruções, motivo
  - Comportamento bifurcado: formulário (scheduled) vs informativo (immediate)
- Transição FSM: WAIT_APPT → APPT_CONFIRMED / APPT_DENIED
- Evento auditável

---

## Fase 5 — Resultado Final NIR + Fechamento

Resultado volta ao NIR, confirmação e cleanup.

- Tela de resultado final por tipo:
  - Aceito (agendado): data/hora, local, instruções, médico, suporte
  - Aceito (imediato): médico, suporte
  - Negado: motivo
  - Falha: causa
  - Fora de escopo: explicação
- Botão "Confirmar Recebimento" (substitui 👍 do Matrix)
- Transição FSM: → WAIT_R1_CLEANUP_THUMBS → CLEANUP_RUNNING → CLEANED
- Cleanup: marcar como CLEANED (caso some das filas)

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
  ├── Fase 1 (intake NIR) ← próxima
    │     └── Fase 2 (pipeline LLM) ← precisa de intake + PromptTemplate
  │           └── Fase 3 (fila médica) ← precisa de LLM artifacts
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
