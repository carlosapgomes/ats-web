# Proposal: Caso corrigido / vínculo entre reenvios

**Change ID**: `corrected-case-resubmission-linkage`  
**Fase**: Fase 3 — robustez operacional pós-anexos  
**Risco**: PROFISSIONAL (adiciona relação entre casos, novo fluxo de upload NIR e contexto na tela médica)  
**Dependências**: `case-attachments-initial-upload`, `fix-prior-case-lookup-after-closure`, `intake-nir`, `pipeline-llm`, `doctor-queue`

## Problema

Quando um caso foi decidido ou encaminhado com informação incompleta ou potencialmente contaminada, não é seguro corrigir silenciosamente o mesmo `Case`.

Exemplos:

- anexo errado visto pelo médico;
- anexo faltante percebido após decisão médica;
- relatório principal errado/incompleto;
- reenvio necessário após negativa;
- complementação documental recebida tarde demais para entrar no mesmo caso.

O sistema já possui dois mecanismos relacionados, mas eles não resolvem toda a necessidade:

1. **Prior-case lookup automático**: detecta negativa recente pelo mesmo `agency_record_number` e oferece contexto ao pipeline/médico. Isso cobre reenvios não declarados, mas não captura intenção nem motivo do NIR.
2. **Anexos complementares antes da decisão**: permite complementar o mesmo caso antes da decisão médica, mas bloqueia complementação após a decisão.

Falta um caminho explícito e auditável para o NIR criar um novo caso corrigido a partir de um caso anterior, sem sobrescrever histórico e sem herdar documentos potencialmente contaminados.

## Objetivo

Implementar um fluxo explícito de reenvio corrigido:

```text
NIR localiza/abre caso anterior
→ clica “Reenviar caso corrigido”
→ informa motivo obrigatório
→ envia novo PDF principal e anexos próprios opcionais
→ sistema cria novo Case
→ novo Case referencia o caso anterior
→ caso anterior registra evento de que foi corrigido/substituído
→ médico vê no novo caso que se trata de reenvio corrigido
```

O caso anterior permanece auditável e não é reaberto. O novo caso passa pelo pipeline normal.

## Dois caminhos complementares

### 1. Reenvio genérico detectado automaticamente

Se o NIR fizer upload normal sem selecionar caso anterior:

- o sistema pode detectar prior case recente por `agency_record_number`;
- isso gera apenas contexto de “negação recente”;
- não há `correction_reason`;
- não há vínculo formal entre casos;
- não deve ser tratado como correção explícita.

### 2. Reenvio corrigido explícito

Se o NIR iniciar pelo caso anterior:

- o novo caso recebe vínculo formal para o anterior;
- o NIR informa motivo obrigatório;
- eventos auditáveis registram a relação;
- UI médica e NIR mostram a relação de forma clara.

## Escopo

### Modelo/dados

Adicionar campos opcionais em `Case`:

```python
corrects_case = ForeignKey("self", null=True, blank=True, related_name="corrected_by_cases", on_delete=PROTECT)
correction_reason = TextField(blank=True)
correction_created_by = ForeignKey(User, null=True, blank=True, related_name="case_corrections_created", on_delete=PROTECT)
correction_created_at = DateTimeField(null=True, blank=True)
```

Os campos só devem ser preenchidos em caso de reenvio corrigido explícito.

### Upload NIR corrigido

Criar fluxo NIR a partir de um caso anterior:

```text
/cases/<case_id>/corrected-resubmission/
```

Comportamento esperado:

- GET renderiza formulário contextualizado pelo caso anterior.
- POST exige exatamente 1 PDF principal.
- POST aceita anexos PDF/JPEG/PNG opcionais, com os mesmos limites do upload inicial.
- `correction_reason` é obrigatório.
- confirmação explícita é obrigatória quando houver checkbox de confirmação.
- cria novo `Case` com `corrects_case` apontando para o anterior.
- não copia PDF, anexos, eventos, decisões ou dados extraídos do caso anterior.
- novo caso segue pipeline normal de extração/LLM.

### Auditoria

Registrar eventos:

```text
CASE_CORRECTION_CREATED  # no novo caso
CASE_MARKED_SUPERSEDED   # no caso anterior
```

Payload mínimo recomendado:

```json
{
  "original_case_id": "...",
  "corrected_case_id": "...",
  "correction_reason": "...",
  "created_by_id": "..."
}
```

### UI NIR

- Mostrar ação `Reenviar caso corrigido` em contextos NIR relevantes:
  - detalhe operacional do caso quando acessível;
  - busca de casos encerrados para casos `CLEANED`.
- Mostrar no detalhe do caso novo:

```text
Este caso corrige o caso anterior X.
Motivo do reenvio: ...
```

- Mostrar no detalhe/listagem do caso anterior, quando aplicável:

```text
Este caso foi corrigido pelo caso Y.
```

### UI médica

Na tela de decisão do novo caso, se `case.corrects_case` existir, mostrar card curto antes do relatório técnico/decisão:

```text
↻ Reenvio corrigido

Este caso foi reenviado pelo NIR para corrigir o caso anterior <registro / id curto>.

Motivo informado pelo NIR:
"..."

Desfecho do caso anterior:
Negado pelo médico em <data>, se houver.
Motivo: <doctor_reason>, se houver.

Atenção:
Os documentos e anexos do caso anterior não foram herdados. Avalie apenas o relatório e os anexos deste caso atual.
```

Não embutir PDF, anexos ou timeline completa do caso anterior na tela de decisão.

## Semântica dos campos textuais

| Elemento | Serve para | Não serve para |
| --- | --- | --- |
| `doctor_reason` | motivo formal obrigatório quando o médico nega | conversa ida-e-volta com NIR |
| `doctor_observation` | nota curta complementar vinculada à decisão médica | thread, negociação, coordenação assíncrona |
| `correction_reason` | motivo pelo qual o NIR cria um novo caso corrigido | justificar a decisão médica anterior |
| `CaseCommunicationMessage` futuro | conversa operacional contextual por caso | substituir decisão, agendamento, confirmação ou motivo formal |
| `CaseEvent` | auditoria append-only de fatos relevantes | chat ou texto operacional longo |

`doctor_observation` não deve ser removido ou redesenhado neste change.

## Fora de escopo

- Reabrir o mesmo `Case` após decisão.
- Copiar anexos automaticamente entre casos.
- Copiar PDF, eventos, decisões, extrações ou sugestões do caso anterior.
- Encerrar automaticamente o caso anterior.
- Alterar FSM.
- Implementar comunicação/thread por caso.
- Remover ou redefinir `doctor_observation`.
- Criar matching explícito por nome do paciente, CNS, CPF ou prontuário.
- Alterar prior-case lookup automático.
- Processar anexos por IA/OCR.

## Critérios de sucesso

- NIR consegue criar novo caso corrigido a partir de um caso anterior.
- Motivo do reenvio corrigido é obrigatório.
- Novo caso referencia o caso anterior.
- Caso anterior não é sobrescrito nem reaberto.
- Novo caso inicia pipeline normal como upload novo.
- Anexos do caso anterior não são herdados.
- Anexos enviados no reenvio pertencem apenas ao novo caso.
- Eventos auditáveis registram a relação nos dois casos.
- Médico vê aviso claro de reenvio corrigido no novo caso.
- Médico não vê documentos/anexos do caso anterior embutidos no novo caso.
- Prior-case lookup automático continua funcionando como fallback independente.
- Quality gate do AGENTS.md passa.
