# Design: Sinalizações prioritárias de EDA em todo o fluxo operacional

## 1. Estado atual verificado

### 1.1 Contrato e prompt LLM1

`apps/pipeline/schemas/llm1.py` aceita atualmente:

```text
standard
gastrostomy
esophageal_dilation
foreign_body
unknown
```

O schema duplica o subtipo em:

- `eda.requested_procedure.subtype`;
- `preop_screening.rulebook_signals.eda_subtype`.

Quando ambos são conhecidos, o validator exige alinhamento. `eda.foreign_body_suspected` e `eda.is_pediatric` são flags adicionais.

`apps/pipeline/llm1_service.py` possui defaults canônicos e `_render_user_prompt()`. A instrução renderizada final é anexada mesmo quando há prompt ativo customizado no banco.

### 1.2 Scope gate

`apps/pipeline/scope_detection.py` reconhece EDA explícita, gastrostomia, dilatação esofágica e corpo estranho por campos estruturados e palavras-chave. Ecoendoscopia não está na lista suportada; por isso pode permanecer `unknown`/`non_eda` e seguir para revisão manual.

O detector textual consulta:

- texto extraído;
- nome do procedimento;
- `summary.one_liner`;
- `summary.bullet_points`;
- `preop_screening.evidence_spans`.

### 1.3 Policy

`apps/pipeline/policy/eda_preop_policy.py` resolve subtipo suportado. Somente `foreign_body` recebe bypass de exames mínimos. Gastrostomia e dilatação seguem o caminho padrão.

`apps/pipeline/policy/eda_policy.py` transforma laboratório e ECG em `not_required` apenas quando `indication_category == foreign_body`.

Ecoendoscopia deve ser adicionada ao conjunto suportado, mas não deve ganhar branch especial.

### 1.4 Apresentação médica

`apps/doctor/presenters.py` converte subtipo em nome canônico e mostra:

- `EDA`;
- `EDA para gastrostomia`;
- `EDA para dilatação esofágica`;
- `EDA para retirada de corpo estranho`.

Pediatria aparece como linha textual. Ingestão cáustica é detectada localmente no presenter e exibida como `alert-warning`. Corpo estranho não possui detector de negação compartilhado nem badge uniforme.

### 1.5 CHD e NIR

As views de `apps/scheduler/` e `apps/intake/` montam dicionários próprios para cards. Não existe coleção canônica de sinais nem partial compartilhado. As telas posteriores usam `summary_text`, decisão e fluxo, mas não garantem continuidade dos destaques.

## 2. Taxonomia

Não modelar os seis itens como um único enum mutuamente exclusivo. Eles pertencem a dimensões diferentes e podem coexistir.

| Código                | Categoria            | Ênfase        | Regra clínica/policy                         |
| --------------------- | -------------------- | ------------- | -------------------------------------------- |
| `foreign_body`        | `clinical_alert`     | `warning`     | preserva bypass de exames mínimos            |
| `caustic_ingestion`   | `clinical_alert`     | `warning`     | informativo; não nega automaticamente        |
| `pediatric`           | `special_population` | `attention`   | idade `< 16`; não cria roteamento automático |
| `echoendoscopy`       | `special_procedure`  | `operational` | policy padrão de EDA                         |
| `esophageal_dilation` | `special_procedure`  | `operational` | policy padrão de EDA                         |
| `gastrostomy`         | `special_procedure`  | `operational` | policy padrão de EDA                         |

Ordem canônica de exibição:

```text
foreign_body
caustic_ingestion
pediatric
echoendoscopy
esophageal_dilation
gastrostomy
```

A ordem prioriza alerta clínico, população e direcionamento procedimental. A presença de um item não remove os demais.

## 3. Persistência

### D1. Campo dedicado no Case

Adicionar projeção persistida separada dos artefatos do LLM:

```python
priority_signals = models.JSONField(default=list, blank=True)
```

Não inserir sinalizações derivadas em `structured_data`, porque esse campo representa a resposta validada do LLM1. Não inserir em `suggested_action`, porque os badges não são decisão nem recomendação LLM2.

Formato persistido versão 1:

```json
[
  {
    "code": "caustic_ingestion",
    "category": "clinical_alert",
    "detail": "há 3 semanas",
    "version": 1
  },
  {
    "code": "echoendoscopy",
    "category": "special_procedure",
    "detail": "",
    "version": 1
  }
]
```

Regras:

- Persistir somente códigos conhecidos.
- Não persistir classes CSS ou texto traduzido; labels e estilos são projeção de apresentação.
- `detail` é opcional e curto; serve para idade/tempo documentado.
- Não persistir combinações como `pediatric_echoendoscopy`.
- Deduplicar por `code` e ordenar canonicamente.

### D2. Resolvedor puro compartilhado

Criar módulo coeso em `apps/cases/priority_signals.py`, sem ORM e sem chamadas LLM, com API conceitual:

```python
resolve_priority_signals(
    *, structured_data: dict[str, object], source_text: str
) -> list[dict[str, object]]

build_priority_signal_badges(
    priority_signals: object,
) -> list[dict[str, str]]
```

O resolvedor é fonte única para pipeline, migration snapshot conceitual/testes e apresentação. A migration deve ser autocontida; se precisar duplicar lógica por exigência de migrations históricas, limitar a duplicação ao snapshot da versão 1 e documentá-la.

`build_priority_signal_badges` deve ignorar payload malformado de forma segura e produzir labels/classes Bootstrap a partir dos códigos persistidos.

### D3. Novos casos

Após LLM1 validar e antes do scope gate/LLM2:

```text
structured_data + extracted_text
→ resolve_priority_signals
→ Case.priority_signals
→ save
```

O evento `LLM1_OK` deve incluir apenas `priority_signal_codes` além do resumo, sem copiar texto clínico sensível adicional.

O mesmo valor persistido será consumido por médico, CHD e NIR; nenhuma view deve redetectar sinais a partir do PDF.

### D4. Backfill

Migration `0013` (número deve ser confirmado no momento da implementação) adiciona o campo e executa backfill:

- incluir somente `Case.status != CLEANED`;
- usar `structured_data` e `extracted_text` existentes;
- não chamar LLM;
- não alterar FSM/status/decisões/eventos;
- não classificar casos `CLEANED` preexistentes;
- ser idempotente e iterar em chunks;
- não sobrescrever lista não vazia em reexecução defensiva.

Casos novos que futuramente chegarem a `CLEANED` preservam seus sinais e os exibem no detalhe histórico. “Sem backfill de encerrados” não significa apagar sinais de casos novos ao encerrar.

## 4. Detecção

### D5. Pediatria

Fonte principal:

```text
patient.age é inteiro, não bool, e age < 16
```

Fallback compatível para payload antigo sem idade:

```text
eda.is_pediatric is True
```

Quando a idade existir e for `>= 16`, o contrato validado novo impede flag divergente. O detalhe do sinal pode ser `"10 anos"`.

### D6. Corpo estranho

Sinais estruturados aceitos:

- subtipo solicitado `foreign_body`;
- subtipo rulebook `foreign_body`;
- `eda.indication_category == foreign_body`;
- `eda.foreign_body_suspected is True`.

Fallback textual deve exigir contexto positivo e tratar negações próximas, incluindo pelo menos:

- `sem corpo estranho`;
- `corpo estranho descartado`;
- `nega ingestão de corpo estranho`;
- `não há corpo estranho`.

O fallback não deve apenas liberar scope: deve produzir o mesmo código canônico consumido por policy/apresentação quando houver evidência positiva suficiente.

### D7. Ingestão cáustica

Mover/reutilizar a lógica atualmente local ao presenter para o resolvedor compartilhado, preservando:

- ingestão + substância cáustica/corrosiva em proximidade;
- negação explícita;
- extração de tempo relativo/data quando disponível;
- ausência de regra automática de negativa.

Corpo estranho e ingestão cáustica devem projetar badges com a mesma ênfase `warning`.

### D8. Procedimentos especiais

Resolver por subtipo estruturado e por termos explícitos de solicitação.

#### Ecoendoscopia

Termos:

- `ecoendoscopia`;
- `eco-endoscopia`;
- `ultrassonografia endoscópica`;
- `ultrassom endoscópico`;
- `EUS` com boundary e contexto de solicitação/procedimento.

Modificadores como punção, PAAF, biópsia, FNA ou FNB não criam novo sinal e não tiram o caso do fluxo.

#### Dilatação esofágica

Reusar `esophageal_dilation` e termos conservadores:

- dilatação esofágica;
- dilatação do esôfago;
- dilatação de esôfago;
- dilatação endoscópica esofágica.

Não usar a palavra `dilatação` isolada.

#### Gastrostomia

Reusar sinais existentes de `gastrostomy`, GTT, PEG e gastrostomia em contexto procedimental.

## 5. Ecoendoscopia no contrato e scope

### D9. Enum

Adicionar `echoendoscopy` a `EdaRequestedProcedureSubtype`, às instruções de schema e a todos os conjuntos explícitos de subtipos suportados. Manter `schema_version == "1.1"` para compatibilidade incremental, como em extensões anteriores do contrato.

Nome canônico:

```text
EDA com ecoendoscopia
```

Quando coexistir com dilatação:

```text
EDA com ecoendoscopia e dilatação esofágica
```

O enum principal pode continuar contendo um subtipo; a coleção de sinais preserva todas as características detectadas. Não criar enum combinatório.

### D10. Precedência de scope

Regra aprovada:

```text
solicitação explícita de EDA suportada OU ecoendoscopia
→ exam_type efetivo EDA
```

Isso prevalece mesmo quando o documento também menciona CPRE, colonoscopia ou outro exame atualmente fora de escopo. A detecção deve distinguir solicitação atual de histórico sempre que a estrutura do documento permitir, priorizando `Motivo da Solicitação` e campos estruturados do procedimento.

Se não houver solicitação suportada de EDA/ecoendoscopia e houver somente exame fora de escopo, preservar revisão manual atual.

### D11. Policy

Ecoendoscopia entra no conjunto de subtipos suportados e segue exatamente o caminho padrão:

- exames mínimos obrigatórios;
- thresholds usuais;
- gates condicionais usuais;
- decisão reconciliada usual;
- se médico aceitar com fluxo `scheduled`, segue para `WAIT_APPT` e comunicação final ao NIR.

Não adicionar branch `if subtype == echoendoscopy` para bypass. Somente corpo estranho mantém exceção.

## 6. Apresentação

### D12. Partial compartilhado

Criar:

```text
templates/cases/_priority_signals.html
```

Contrato de contexto:

```text
priority_signal_badges: list[{code, label, css_class, emphasis}]
```

O partial:

- não executa detecção;
- não acessa texto bruto;
- usa somente badges projetados a partir do valor persistido;
- não renderiza container vazio;
- usa Bootstrap 5.3 e HTML SSR;
- permite wrap em mobile.

Labels recomendados:

| Código                | Label                                              |
| --------------------- | -------------------------------------------------- |
| `foreign_body`        | `⚠ Suspeita de corpo estranho`                     |
| `caustic_ingestion`   | `⚠ Ingestão cáustica/corrosiva` + detalhe de tempo |
| `pediatric`           | `Pediatria` + detalhe de idade                     |
| `echoendoscopy`       | `Ecoendoscopia`                                    |
| `esophageal_dilation` | `Dilatação esofágica`                              |
| `gastrostomy`         | `Gastrostomia`                                     |

### D13. Médico

Fila médica:

- badges próximos ao nome/título do caso, antes do resumo;
- úteis antes de o triador abrir o caso.

Tela de decisão:

- mesmos badges imediatamente no topo do relatório automático;
- procedimento canônico continua visível;
- não substituir nome, registro, status ou avisos de lock.

Corpo do relatório:

- `foreign_body` e `caustic_ingestion` entram deterministicamente no início de `Achados críticos`;
- `pediatric`, `echoendoscopy`, `esophageal_dilation` e `gastrostomy` entram em uma linha determinística de contextos prioritários no `Resumo clínico`;
- o `summary.one_liner` continua exibido, mas não é fonte obrigatória dos destaques;
- evitar duplicar a mesma linha de ingestão cáustica no contexto e em achados críticos.

### D14. CHD

Exibir o partial compartilhado em:

- cards pendentes da fila;
- cards processados/ciências quando possuírem sinais;
- topo do formulário de confirmação;
- topo do detalhe read-only/processado.

Não alterar ordenação, locks, formulários, decisão de agenda, disponibilidade de turnos nem permissões.

### D15. NIR

Exibir o partial compartilhado em:

- cards de “Meus Casos”;
- topo do detalhe operacional/resultado;
- topo do detalhe encerrado quando o caso possui sinais persistidos.

Casos `CLEANED` antigos não backfillados mostram nenhum badge. Casos novos que foram encerrados continuam mostrando seus badges.

Não alterar confirmação de recebimento, resultado final, locks, busca ou permissões.

## 7. Compatibilidade e segurança

- Payload ausente/malformado de `priority_signals` rende lista vazia, nunca erro 500.
- Casos e fixtures antigos recebem default `[]`.
- A migration não reexecuta LLM e não altera decisões.
- O campo persistido não contém classes CSS nem trechos longos do laudo.
- Nenhuma sinalização decide automaticamente médico, executor, turno ou agenda.
- Nenhuma nova permissão é criada.
- O scope de ecoendoscopia é testado contra regressão de casos exclusivamente fora de EDA.

## 8. Observabilidade

Para novos casos, `LLM1_OK.payload` inclui:

```json
{ "priority_signal_codes": ["pediatric", "echoendoscopy"] }
```

Não criar evento por renderização. Backfill não deve produzir milhares de eventos operacionais durante migration.

## 9. Rollback

### Código/UI

Reverter slices em ordem inversa remove badges do NIR, CHD e médico sem alterar FSM.

### Scope/policy

Reverter o Slice 001 faz ecoendoscopia voltar ao comportamento anterior de revisão manual. Antes de rollback em produção, verificar casos de ecoendoscopia já em `WAIT_DOCTOR`/`WAIT_APPT`; não retroceder status automaticamente.

### Banco

O reverse da migration pode remover `priority_signals` somente se houver decisão explícita de rollback de schema. Como o campo é projeção derivável, sua perda não apaga PDF, texto extraído, decisão ou agenda. O `RunPython` reverso é `noop`.

## 10. Dimensionamento dos slices

### Slice 001 — Ecoendoscopia chega ao médico

Valor vertical: contrato/prompt → scope → policy padrão → nome canônico no relatório médico.

### Slice 002 — Sinais persistidos aparecem na fila médica

Valor vertical: model/migration/backfill + resolvedor + pipeline novo → badges na fila médica. É o slice estrutural maior; ampliar arquivos é inevitável para cruzar persistência, pipeline e UI, e deve ser justificado no relatório.

### Slice 003 — Relatório médico consolidado

Valor vertical: a tela de decisão usa os sinais persistidos no topo e corpo, removendo dependência de detecção local/LLM para destaque.

### Slice 004 — Continuidade no CHD

Valor vertical: o CHD vê os mesmos badges na fila, confirmação e detalhes, sem alteração operacional.

### Slice 005 — Continuidade no NIR

Valor vertical: o NIR vê os mesmos badges em lista, detalhe e resultado/histórico aplicável.
