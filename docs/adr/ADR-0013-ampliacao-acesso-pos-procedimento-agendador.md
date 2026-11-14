# ADR-0013: Ampliação da política de acesso ao pós-procedimento para o Agendador

## Status

Accepted — decisão de produto confirmada pelo owner na proposta do change `grant-scheduler-post-procedure-access` (2026-11-13); implementada e integrada em `main` pelos slices S1/S2 e publicada na prerelease `v0.11.0-rc.1`. Registrada como condição pré-arquivamento do change, junto da atualização de Purpose das specs canônicas.

## Contexto

O desfecho pós-exame (realizado / não realizado com causa oficial, internação, histórico e exportação CSV) era acessível apenas a supervisores do CHD (`manager` ativo com papel `scheduler`) e `admin`. O Agendador — papel operacional responsável pela fila de agendamento e notificação de vinda imediata — precisava acompanhar e registrar esses desfechos, mas a única saída disponível era atribuir o papel `manager`, que libera o dashboard gerencial inteiro (métricas, todos os casos, fechamento administrativo, PDFs).

A política de acesso centralizava-se em `can_access_followup` (`apps/accounts/services.py`), consumida pelo decorator `followup_access_required` e pelo context processor `role_context`; as quatro views de pós-procedimento (`followup_list`, `followup_form`, `followup_history`, `followup_history_export`) empilhavam login + `role_required("manager", "admin")` + guard específico. Requisitos não negociáveis: auditoria por ator real, dados identificáveis de pacientes (dados sensíveis + CSV), isolamento gerencial intocado (inclusive por URL direta), papel ativo único por sessão preservado e middleware de intranet inalterado.

## Decisão

1. **Matriz central por papel ativo, sem atribuição de papéis adicionais:** ampliar `can_access_followup` para reconhecer o papel ativo `scheduler` (autenticado e ativo), mantendo a exigência de vínculo CHD para `manager` e o acesso de `admin` sem vínculo. `doctor`/`nir` ativos jamais acessam o recurso, mesmo em conta multi-role; a sessão continua sendo a fonte do papel ativo. `scheduler` é adicionado ao `role_required` **somente nas quatro views** de pós-procedimento, mantendo login e guard específico.
2. **Mesmas URLs e implementação, segunda entrada de navegação:** as quatro rotas sob `/dashboard/follow-ups/` permanecem as mesmas para todos os papéis; o prefixo não concede acesso ao dashboard (cada endpoint tem guard próprio). A navegação do Agendador (`scheduler/_nav.html`) ganha a entrada Pós-Procedimento, condicionada à mesma política central; os templates de página selecionam o partial de navegação pelo papel ativo. Seleção de partial é apresentação, não autorização.
3. **População global e versões compartilhadas:** nenhum filtro por `case.scheduler`, criador ou autor do follow-up — o Agendador opera exatamente sobre `is_followup_eligible` (todos os elegíveis, inclusive vinda imediata e casos de outros usuários). Qualquer papel autorizado pode criar a primeira versão ou atualizar versão de outro autor; autoria/instante por versão permanecem registrados (append-only), sem edição de rows anteriores.
4. **Paridade total de Histórico & Exportação:** o Agendador consulta os mesmos desfechos correntes, resumos, filtros, paginação, projeção de causas legadas e CSV do supervisor — mesma leitura, zero writes; exportação não cria eventos de auditoria.
5. **Isolamento gerencial e rede preservados:** dashboard, Prompts, Usuários e demais superfícies gerenciais continuam bloqueados para `scheduler` inclusive por URL direta; `IntranetGuardMiddleware` e o bypass multi-role existente não são alterados (scheduler-only fora da intranet permanece 403, inclusive POST/CSV).
6. **Capabilities históricas mantidas:** os nomes `supervisor-appointment-follow-up` e `supervisor-followup-history` são preservados (sem renomeação estrutural); as deltas promovem os requisitos à matriz ampliada e os Purpose das specs canônicas passam a descrever o acesso do Agendador.

## Alternativas Consideradas

1. **Atribuir papel `manager` ao Agendador:** zero mudança de código, mas liberaria dashboard, métricas, fechamento administrativo e PDFs de todos os casos — ampliação de privilégio muito além da necessidade; rejeitada.
2. **Rotas e handlers espelhados em `/scheduler/`:** URLs "limpas" por papel, mas duplicação de regras/validações/redirecionamentos com risco de divergência silenciosa entre implementações; rejeitada (extração para app compartilhado também desnecessária nesta entrega).
3. **Predicado paralelo de acesso nos templates:** mudança pontual na navegação, mas criaria segunda fonte de verdade de política divergente da central; rejeitada — o contexto continua delegando a `can_access_followup`.
4. **Filtrar população por autoria/agendador:** superfície menor de dados, mas não atende a decisão operacional confirmada pelo owner (desfechos de vinda imediata e de casos agendados por outros usuários precisam ser registráveis); rejeitada.
5. **Nova capability dedicada ao Agendador (`scheduler-followup-*`):** soaria mais precisa, mas exigiria renomeação estrutural e specs gêmeas para o mesmo fluxo; rejeitada em favor de deltas nas capabilities existentes.

## Consequências

### Positivas

- Agendador conclui o ciclo operacional (agendar → confirmar → registrar desfecho → consultar/exportar) sem escalar privilégios.
- Uma única implementação de política, leitura e gravação para todos os papéis autorizados; paridade de dados por construção.
- Auditoria real: autor de cada versão/evento é sempre o usuário que submeteu, inclusive em atualizações cruzadas entre papéis.
- Isolamento gerencial permanece provável e testável por URL direta; superfície de acesso novo é restrita e explícita.

### Negativas/Trade-offs

- `scheduler` passa a acessar dados identificáveis de pacientes de **todos** os elegíveis e exportá-los em CSV — aceito explicitamente pelo owner, mas amplia a superfície de dados sensíveis por papel.
- Rotas compartilhadas sob prefixo `/dashboard/` para um papel sem dashboard confundem a organização visual; mitigado pela navegação contextual e documentado no manual (URL própria só se virar requisito).
- `can_access_followup` vira ponto único de atenção: qualquer mudança futura de matriz deve reexecutar as regressões negativas gerenciais e de rede.
- A corrida preexistente em atualizações simultâneas (`MAX(version)+1` antes do bloco atômico) permanece sem resolução de conflitos — fora do escopo desta decisão.

### Riscos e Mitigações

- **Ampliação indevida de acesso:** guards por view + política central testados na fronteira HTTP (GET/POST/negativas sem seguir redirects); parametrização das rotas gerenciais reais do `apps/dashboard/urls.py` como regressão obrigatória.
- **Link administrativo vazando em página compartilhada:** seleção de partial por papel ativo nas três páginas (inclusive re-render de POST inválido) com verificação dos hrefs renderizados.
- **Falso positivo de bypass multi-role nas fixtures:** testes com conta somente `scheduler` dentro da intranet; cenário multi-role com papel ativo `scheduler` mantém dashboard bloqueado.
- **PII em exportação:** CSV existente sem eventos de auditoria; acesso circunscrito à intranet e à matriz aprovada, revisável em auditoria de `CaseEvent` das gravações.

## Histórico de Mudanças

- 2026-11-13: Criada como Accepted. Decisão implementada pelos slices S1/S2 do change `grant-scheduler-post-procedure-access` (revisões independentes `OK with notes`, zero P0/P1; suite completa 4.804 passed no gate final), publicado em `v0.11.0-rc.1` (evidence pack `docs/releases/2026-11-13_v0.11.0-rc.1.md`). Registro cumprindo a condição pré-arquivamento definida no `tasks.md` do change: criação desta ADR + atualização do Purpose das specs canônicas na promoção das deltas.
