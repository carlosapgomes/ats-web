# Design: Histórico e exportação de follow-ups

## D1 — Colocação da visualização (decisão do owner)

Sub-abas (`nav-tabs` Bootstrap) sob o pill **Follow-up**: **Registrar** (`/dashboard/follow-ups/`, URL e comportamento inalterados) e **Histórico & Exportação** (`/dashboard/follow-ups/history/`). Alternativas descartadas: seção no dashboard (fragmentaria o domínio e sujaria a cabine operacional — filas vivas) e pill própria (prematura: um único relatório; nav já tem 4 pills + "Auditoria" oculta). Se relatórios de outros domínios surgirem, uma pill "Relatórios" pode ser promovida depois (migração barata).

## D2 — População e versionamento

População = casos com ≥1 `CaseFollowUp`, **cada caso exatamente 1x, pela versão corrente** (maior `version`). Contrato novo no service `apps/cases/followup.py`:

- `current_follow_ups()` → queryset de `CaseFollowUp` contendo só as versões máximas por caso (`select_related("case", "recorded_by")`, `prefetch_related("procedure_outcomes__procedure")`). Implementação sugerida: subquery de `Max("version")` agrupada por `case`.

Histórico de versões de um caso **não** entra na visualização: continua acessível pela auditoria do caso (`CaseEvent` `FOLLOWUP_*` com snapshots). Agregados e CSV derivam **exclusivamente** de versões correntes — versões antigas nunca distorcem contagens.

## D3 — Eixo temporal: data de grupo (não `recorded_at`)

O eixo de filtro é a **data de grupo** do caso — `timezone.localdate(appointment_at)` para agendamento confirmado, senão `doctor_decided_at` (vinda imediata), via helper existente `_followup_group_date` (fonte única, mesma semântica da aba Registrar). Motivo: `recorded_at` pode ser dias depois do dia rastreado; relatório de supervisão organiza-se pelo **dia do agendamento/decisão**. Consequência aceita (consistente com a aba Registrar): caso remarcado após gravação move-se para a nova data de grupo.

Janela: `?start=&end=` ISO `YYYY-MM-DD` em datas **locais** (`America/Bahia`, helpers `timezone.localdate/localtime`). Default: **últimos 7 dias incluindo hoje** (`hoje-6 .. hoje`). Qualquer inconsistência — valor inválido, `start > end`, ou período > **31 dias** — cai silenciosamente no default (padrão de UX já usado pela aba Registrar com `?date=`). A janela ativa é exibida no header da página.

`?q=` busca por número de ocorrência (`agency_record_number`, contains case-insensitive) ou nome do paciente (`structured_data.patient.name` contains case-insensitive) **dentro da população da janela** (na aba Registrar a busca é global; aqui a janela é o filtro primário).

## D4 — Cards × filtros de linha

- **Cards-resumo** (casos com follow-up, taxa de realizado por procedimento, causas de não realização com breakdown de submotivo `resource_shortage`, internações) resumem **sempre a janela + busca** — filtro de linha não os altera (rótulo explícito "Resumo do período").
- **Filtros de linha** (`?performed=`, `?reason=`, `?admitted=`) aplicam-se à **tabela e ao CSV**: `performed`/`reason` filtram linhas de desfecho de procedimento; `admitted` filtra casos (nível de caso, remove o caso inteiro). Valores inválidos são ignorados (equivale a "todos").

Motivação: misturar filtro de linha nos agregados produz contagens ambíguas (caso com 2 procedimentos parcialmente filtrado); separar mantém os cards um retrato estável do período.

## D5 — Exportação CSV

`GET /dashboard/follow-ups/history/export/` com **exatos os mesmos params** da página (`start/end/q/performed/reason/admitted`). Resposta:

- `Content-Type: text/csv; charset=utf-8` com **BOM** (`\ufeff`) e **separador `;`** — abre direto no Excel pt-BR (padrão ANATEL/hospital BR); geração via módulo `csv` com `delimiter=";"` (escaping de `;`, aspas e quebras automático).
- `Content-Disposition: attachment; filename="followups_<start>_<end>.csv"`.
- 1 linha por desfecho de procedimento (da versão corrente), colunas (header PT-BR): `Case ID; Ocorrência; Paciente; Data; Procedimento; Desfecho; Causa; Submotivo; Outra causa (texto); Internação; Versão; Registrado por; Registrado em`. Valores humanos: `Realizado`/`Não realizado`, labels das choices de causa/submotivo/procedimento, internação canônica **`Sim`/`Não`**; datas `dd/mm/yyyy` e `dd/mm/yyyy hh:mm` locais.
- **Exporta TODAS as linhas da população filtrada, ignorando a paginação** da tabela (`?page=` não afeta o CSV; a tabela pagina em 25, o CSV nunca é truncado).
- Volumes baixos (janela ≤31 dias, ~dezenas/dia): `HttpResponse` simples, sem streaming.
- **Nenhum `CaseEvent`**: exportação é leitura (a doutrina de auditoria cobre escritas).

## D6 — SSR puro

Sem JS novo, sem lib de gráficos: cards Bootstrap + `progress` bars para breakdown de causas; forms `method="get"`; paginação `Paginator` 25/página (padrão do summaries). Partial compartilhado `templates/dashboard/_followup_tabs.html` renderiza as sub-abas com estado ativo por página; `followup_list.html` só ganha o include (frente intacta).

## D7 — Acesso e guard

`@role_required("manager", "admin")` em página e export, idêntico às demais views do follow-up. Nenhum guard de intranet (mesma superfície da aba Registrar).

## D8 — Performance e volumes

Filtragem de data de grupo é feita em Python sobre a população de follow-ups da janela — consistente com a aba Registrar (`_followup_group_date` é Python-side; volumes hospitalares são baixos; janela limitada a 31 dias). Sem novos índices. Se volumes crescerem, otimização fica para change futuro.

## Riscos e trade-offs

- **Consulta Python-side** — aceito por consistência e volume (D8).
- **Ignorar filtros inválidos** em vez de erro 400 — consistente com UX existente da aba (`?date=` inválido → default); validação server-side continua autoridade.
- **`admitted` filtra casos, `performed/reason` filtram linhas** — assimetria documentada (D4) e refletida nos labels do form.
