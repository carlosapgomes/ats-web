# Proposal: Ênfase de ingestão cáustica/corrosiva no relatório médico

**Change ID**: `highlight-caustic-ingestion-in-doctor-report`  
**Fase**: ajuste de segurança/clareza documental do relatório técnico da triagem  
**Risco**: PROFISSIONAL (altera apresentação de contexto clínico para médico; não altera decisão automática, policy, FSM, filas, permissões, banco ou schema LLM)  
**Dependências**: `align-llm-contract-and-doctor-routing`, `show-recent-exam-dates-in-doctor-report`, `doctor-queue`

## Problema

Alguns contextos clínicos importantes precisam aparecer com ênfase no relatório técnico exibido ao médico, mesmo quando não devem alterar automaticamente a decisão sugerida. Hoje o sistema já destaca contextos como:

- paciente pediátrico, via linha de contexto `paciente pediátrico: sim`;
- EDA para gastrostomia, via procedimento canônico `procedimento solicitado: EDA para gastrostomia`.

Entretanto, não há destaque específico para história de ingestão de substância cáustica/corrosiva. Esse contexto pode ser relevante para a avaliação médica, principalmente quando o relatório descreve há quanto tempo ocorreu a ingestão. Atualmente, se o LLM não mencionar espontaneamente esse dado no resumo, o médico pode precisar localizar a informação manualmente no texto completo/PDF.

## Objetivo

Exibir no relatório técnico da triagem uma ênfase documental quando o texto do relatório indicar ingestão de substância cáustica/corrosiva, tentando também identificar o tempo desde a ingestão quando estiver disponível no próprio texto.

A feature deve produzir uma sinalização como:

```text
⚠️ ingestão cáustica/corrosiva relatada: sim
tempo desde a ingestão: há 3 semanas
```

Quando o tempo não estiver claro:

```text
⚠️ ingestão cáustica/corrosiva relatada: sim
tempo desde a ingestão: não informado no relatório
```

## Escopo

### Funcionalidades

1. **Detector documental determinístico**
   - Detectar, no texto extraído do PDF, menções compatíveis com ingestão de substância cáustica/corrosiva.
   - Considerar variações com e sem acento, por exemplo:
     - `ingestão de cáustico` / `ingestao de caustico`;
     - `substância corrosiva` / `substancia corrosiva`;
     - `produto corrosivo`;
     - `soda cáustica` / `soda caustica`;
     - `ácido` / `acido`, quando em contexto de ingestão.
   - Evitar, de forma conservadora, falsos positivos óbvios como `nega ingestão`, `sem ingestão` ou `não ingeriu` quando a negação estiver no mesmo contexto textual.

2. **Extração documental do tempo desde a ingestão**
   - Tentar extrair expressões temporais próximas ao evento, sem fazer cálculo clínico nem converter para regra decisória.
   - Exemplos de expressões aceitas:
     - `há 3 dias`;
     - `há cerca de 2 semanas`;
     - `faz 1 mês`;
     - `ingestão em 12/05/2026`;
     - `episódio ocorreu no dia 12/05/2026`.
   - Preservar o texto literal quando possível.
   - Se houver ingestão detectada, mas sem tempo claro, exibir fallback explícito: `não informado no relatório`.

3. **Ênfase no relatório médico**
   - Renderizar a sinalização no topo do `Relatório Técnico da Triagem`, junto às linhas de contexto já usadas para procedimento, origem, transfusão, exames rastreados e pediatria.
   - A sinalização deve ser claramente visual, preferencialmente com alerta Bootstrap discreto ou linha iniciada por `⚠️`.

4. **Reforço de prompt LLM1 para resumos futuros**
   - Atualizar o prompt canônico/default do LLM1 para pedir que, quando houver ingestão cáustica/corrosiva, o resumo narrativo mencione o evento e o tempo desde a ingestão se disponível.
   - Não adicionar campos novos ao schema LLM1 neste change.
   - Não sobrescrever prompts ativos já existentes no banco.

## Fora de escopo

- Sugerir negativa automática por tempo desde ingestão.
- Codificar regra clínica de semanas/dias para aceitar ou negar.
- Alterar `suggestion`, `support_recommendation`, `preop_gate`, LLM2, policy EDA ou reconciliação.
- Alterar FSM, filas, estados, transições, notificações ou roteamento.
- Criar migration ou novos campos persistidos no banco.
- Alterar schema Pydantic LLM1/LLM2.
- Fazer OCR adicional ou reprocessamento histórico de casos antigos.
- Criar dashboard/métrica para ingestão cáustica/corrosiva.

## Critérios de sucesso

- Caso cujo texto contenha ingestão cáustica/corrosiva mostra alerta no relatório técnico médico.
- Quando houver expressão temporal próxima ao evento, o relatório mostra o tempo literal identificado.
- Quando o tempo não estiver disponível, o relatório mostra `tempo desde a ingestão: não informado no relatório`.
- Casos sem ingestão cáustica/corrosiva não exibem alerta.
- Negação simples no mesmo contexto (`nega ingestão`, `sem ingestão`, `não ingeriu`) não dispara alerta.
- O alerta não altera decisão sugerida, suporte recomendado, policy, FSM, fila ou status do caso.
- Prompt LLM1 passa a orientar menção narrativa do evento/tempo quando disponível.
- Testes cobrem detecção positiva, extração de tempo, fallback sem tempo, caso negativo e negação explícita.
- Quality gate do AGENTS.md passa.
