---
name: openspec-vertical-change-writer
description: Cria ou revisa changes OpenSpec com slices verticais, enxutos, contexto zero para implementador LLM, TDD, critérios/gates de aceitação e relatório verificável por terceiro LLM.
---

# Skill: OpenSpec Vertical Change Writer

Use esta skill sempre que criar ou revisar um novo change em `openspec/changes/<change-id>/`.

Esta skill é **geral para desenho de changes e slices**. Para slices que serão implementados especificamente por DeepSeek4-Flash, use também a skill complementar `deepseek-slice-writer` para reforçar protocolo de incompleto, checks por inspeção e relatório verificável.

## Instrução recorrente do projeto

Ao criar um novo change OpenSpec, preserve este princípio:

> Lembrando que preciso que os slices sejam verticais e enxutos, tocando o mínimo de arquivos necessários, por isso verifique o dimensionamento do número de slices. Considere também que os slices serão implementados por um outro LLM com contexto zero. Portanto, cada arquivo markdown de slice deve conter um handoff+prompt, dando contexto ao LLM implementador e orientando sobre a metodologia de desenvolvimento: clean code, dry, you-aint-gonna-need-it e TDD. Deixe claro em cada arquivo os critérios e gates de autoavaliação/aceitação, e exiga um relatório markdown em um arquivo temporário para que um terceiro LLM verifique a implementação.

## Quando usar

- Antes de criar `proposal.md`, `design.md`, `tasks.md` e `slices/*.md`.
- Ao dimensionar número de slices de um change.
- Ao revisar se um slice ficou horizontal demais.
- Ao transformar uma intenção de feature em plano implementável por LLM com contexto zero.

## Saída esperada de um change

Estrutura recomendada:

```text
openspec/changes/<change-id>/
├── proposal.md
├── design.md
├── tasks.md
├── specs/<capability>/spec.md        # quando aplicável
└── slices/
    ├── slice-001-<nome>.md
    ├── slice-002-<nome>.md
    └── ...
```

## Regras para dimensionar slices

1. **Verticalidade**: cada slice deve entregar valor observável end-to-end, ainda que pequeno.
2. **Escopo enxuto**: tocar o mínimo de arquivos necessários; ideal <= 5 quando viável.
3. **Sem fatias horizontais puras**: evitar slice “só backend”, “só template”, “só JS” se não entregar fluxo testável.
4. **Sem antecipar slices futuros**: cada slice deve implementar apenas o necessário para seu objetivo.
5. **Testabilidade**: cada slice precisa ter testes claros e comandos de validação próprios.
6. **Contexto zero**: o slice deve conter contexto suficiente para outro LLM implementar sem depender de conversa anterior.
7. **Verificabilidade**: o slice deve exigir relatório temporário com evidências para terceiro LLM revisar.

## Conteúdo obrigatório de cada slice

Cada `slices/slice-*.md` deve conter:

1. **Handoff para implementador LLM com contexto zero**
   - arquivos que deve ler;
   - resumo do estado atual;
   - objetivo exato;
   - limites de escopo.

2. **Objetivo do slice**
   - fluxo end-to-end em texto simples.

3. **Contexto técnico atual**
   - arquivos relevantes;
   - comportamento existente;
   - restrições conhecidas.

4. **Escopo funcional em requisitos numerados**
   - `R1`, `R2`, `R3`...
   - cada requisito deve ser testável ou verificável.

5. **Arquivos esperados**
   - lista enxuta;
   - exigir justificativa no relatório se tocar arquivos extras.

6. **TDD obrigatório**
   - RED: testes que devem falhar antes da implementação;
   - GREEN: implementação mínima;
   - REFACTOR: clean code, DRY e YAGNI.

7. **Critérios de sucesso**
   - checklist binário.

8. **Gates de autoavaliação**
   - perguntas objetivas que o implementador deve responder no relatório.

9. **Relatório obrigatório**
   - caminho `/tmp/<change>-slice-<n>-report.md`;
   - evidência RED/GREEN;
   - snippets antes/depois;
   - quality gate;
   - respostas aos gates;
   - justificativas de escopo.

10. **Prompt pronto para implementador LLM**
    - autocontido;
    - instrui a ler artefatos;
    - reforça TDD, clean code, DRY, YAGNI;
    - manda atualizar `tasks.md`, gerar relatório, commit/push e parar.

## Template curto de prompt para slice

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/<change-id>/{proposal.md,design.md,tasks.md,slices/<slice>.md} first.
Implement ONLY this slice. Use vertical slicing; avoid horizontal slicing by layer.
Keep the slice lean: touch only the minimum files needed and justify any extra file in the report.
Use TDD: RED (failing test) -> GREEN (minimal pass) -> REFACTOR (clean safely).
In REFACTOR, enforce clean code, DRY, YAGNI, clear names, cohesive functions, low coupling and no dead code.
Do not implement future slices. Do not alter models/migrations/FSM/permissions unless explicitly required by this slice.
Run the validation commands from AGENTS.md. Update tasks.md only after all criteria pass.
Create a detailed temporary markdown report with RED/GREEN evidence, before/after snippets, quality gate results, self-evaluation gates and any scope justification.
Reply with REPORT_PATH=<temp-markdown-path>, commit and push, then STOP for planner review.
```

## Integração com DeepSeek4-Flash

Se o implementador for DeepSeek4-Flash, complemente o slice com a skill `deepseek-slice-writer`, especialmente:

- protocolo obrigatório para DeepSeek4-Flash;
- condições automáticas de `INCOMPLETO`;
- checks de inspeção `rg`;
- relatório com `Handoff para verificador`.

## Checklist de revisão do change

Antes de entregar o OpenSpec:

- [ ] `proposal.md` explica problema, objetivo, escopo incluído/fora e critérios de sucesso.
- [ ] `design.md` existe se não for bugfix QUICK simples.
- [ ] `tasks.md` lista slices em ordem implementável.
- [ ] Cada slice é vertical e testável.
- [ ] Cada slice tem handoff + prompt para LLM com contexto zero.
- [ ] Cada slice exige TDD, clean code, DRY e YAGNI.
- [ ] Cada slice tem critérios e gates de autoavaliação.
- [ ] Cada slice exige relatório temporário para terceiro LLM.
- [ ] O número de slices equilibra entrega de valor e escopo enxuto.
