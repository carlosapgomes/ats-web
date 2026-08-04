# Proposal: Manual oficial do usuário, PDF de divulgação e página in-app

**Change ID**: `official-user-manual-publication`  
**Risco**: PROFISSIONAL (documentação operacional oficial + rota autenticada de leitura; sem alteração de FSM, dados clínicos ou workflow)  
**Dependências funcionais**: `scheduler-historical-intercurrence-requests`, `case-communication-mention-aliases`  
**Fonte inicial**: `tmp/manual.md`

## Problema

O sistema já possui fluxos operacionais relativamente completos para NIR, Médico e CHD/Agendador, incluindo:

- upload e acompanhamento NIR;
- decisão médica;
- confirmação/negativa de agendamento;
- vinda imediata;
- intercorrência pós-agendamento aberta pelo NIR;
- comunicação histórica CHD → NIR para alterações internas;
- comunicação operacional por caso;
- notificações por menção.

Hoje, porém, o manual prático existe apenas como rascunho temporário em `tmp/manual.md`. Isso causa três problemas:

1. O documento não é uma fonte oficial versionada no repositório.
2. Não há geração reprodutível de PDF para treinamento/divulgação.
3. Usuários autenticados não conseguem abrir o manual diretamente pelo sistema.

## Objetivo

Transformar o rascunho em um manual oficial, versionado e acessível por dois meios:

1. **Markdown oficial no repositório** — fonte única em `docs/manual/manual-usuarios.md`.
2. **PDF de divulgação** — gerado por script versionado e reprodutível.
3. **Página dentro do sistema** — rota autenticada com link no header, abrindo em nova aba.

## Escopo

### Funcionalidades

1. Criar documento oficial em Markdown a partir de `tmp/manual.md`.
2. Garantir que o manual cubra os fluxos operacionais atuais, incluindo o fluxo recente:
   - CHD identifica mudança interna em caso histórico;
   - CHD usa `Buscar histórico > Detalhes > Comunicar NIR`;
   - NIR recebe notificação;
   - NIR decide se abre `Intercorrência Pós-Agendamento`;
   - caso volta para CHD responder formalmente.
3. Criar script de geração de PDF para divulgação.
4. Adicionar testes de sanidade para o artefato oficial e para o PDF gerado.
5. Criar página autenticada de manual no sistema, renderizando o Markdown oficial.
6. Adicionar link **Manual** no header para usuários autenticados, abrindo em nova aba.

## Fora de escopo

- Editor/admin para alterar o manual pelo sistema.
- Versionamento do manual em banco de dados.
- Download de PDF pela própria aplicação neste change.
- Internacionalização/múltiplos idiomas.
- Busca interna no manual.
- Sumário dinâmico avançado.
- Dependência externa pesada como Pandoc, WeasyPrint ou wkhtmltopdf.
- Alteração de fluxos operacionais, FSM, permissões ou modelos de caso.
- Aceitar menções acentuadas como `@médico` — isso pertence a outro change de parser, se necessário.

## Decisões de produto

### D1. Markdown é a fonte única oficial

O manual oficial deve viver em `docs/manual/manual-usuarios.md`. O PDF e a página in-app devem usar esse arquivo como fonte, evitando cópias divergentes.

### D2. PDF gerado por script, não mantido manualmente

O PDF deve ser gerado por script versionado. O output padrão pode ser `docs/manual/dist/manual-usuarios.pdf`, mas o arquivo gerado não precisa ser commitado como fonte de verdade.

### D3. Página de manual exige login

O manual descreve fluxos internos de operação. A página in-app deve ser acessível apenas para usuários autenticados.

### D4. Header abre o manual em nova aba

O link no header deve usar `target="_blank"` e `rel="noopener"` para permitir consulta sem interromper o trabalho operacional.

### D5. Sem nova dependência pesada para PDF

Como o projeto já possui `pymupdf`, o script deve preferir uma implementação com dependências já existentes ou stdlib. Se a implementação escolher outra dependência, deve justificar no relatório e atualizar `pyproject.toml` via `uv`, mas a preferência explícita é **não adicionar dependência**.

## Dimensionamento dos slices

O change será dividido em **2 slices verticais e enxutos**:

1. **Slice 001 — Manual oficial + geração de PDF**  
   Entrega o manual oficial versionado e um fluxo end-to-end de geração de PDF para divulgação.

2. **Slice 002 — Página in-app + link no header**  
   Entrega o acesso no sistema usando o mesmo Markdown oficial, com rota autenticada e link abrindo em nova aba.

Essa divisão evita um slice grande demais e mantém cada entrega com valor completo. O Slice 001 não toca navegação/sistema web. O Slice 002 não mexe no script de PDF.

## Critérios globais de sucesso

- `docs/manual/manual-usuarios.md` existe e é a fonte oficial do manual.
- O manual inclui instruções por papel: NIR, Médico e CHD/Agendador.
- O manual inclui o fluxo CHD → NIR para alteração interna em caso histórico.
- O manual inclui orientação sobre intercorrência pós-agendamento aberta pelo NIR.
- O manual inclui limites/tipos de arquivos de upload/anexos.
- O script gera um PDF válido a partir do Markdown oficial.
- A geração de PDF é testável e documentada.
- Usuário autenticado acessa a página do manual no sistema.
- Usuário não autenticado não acessa a página do manual.
- Header mostra link **Manual** para usuários autenticados.
- Link do header abre em nova aba.
- Página in-app lê o Markdown oficial; não duplica o conteúdo em template.
- Quality gate do `AGENTS.md` passa.
