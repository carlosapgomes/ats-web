# Architecture Decision Records

Registros de decisões arquiteturais importantes.

## ADRs Ativas

| Número | Título | Status | Data |
|--------|--------|--------|------|
| [ADR-0001](ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md) | Arquitetura Django Web SSR para ATS de Triagem EDA | Accepted | 2026-05-05 |
| [ADR-0002](ADR-0002-emails-transacionais-autenticacao-cadastro.md) | Emails transacionais para autenticação e cadastro | Accepted | 2026-06-18 |
| [ADR-0003](ADR-0003-perfis-procedimento-tipo-exame-explicito.md) | Perfis de procedimento e tipo de exame explícito | Accepted — parcialmente superada pela ADR-0004 | 2026-08-04 |
| [ADR-0004](ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md) | Procedimentos múltiplos e contrato LLM neutro | Accepted — parcialmente superada pela ADR-0006 | 2026-08-06 |
| [ADR-0005](ADR-0005-local-de-archive-openspec.md) | Local de archive dos changes OpenSpec | Accepted | 2026-08-18 |
| [ADR-0006](ADR-0006-ecoendoscopia-e-cpre-como-procedimentos-independentes.md) | Ecoendoscopia e CPRE como procedimentos independentes | Accepted | 2026-09-12 |

## ADRs Deprecated/Superseded

(nenhuma integralmente; as ADRs 0003 e 0004 foram parcialmente superadas)

## Como criar uma nova ADR

1. Usar `.pi/skills/adr-generator/adr_generator.py` para reservar a numeração e criar o arquivo.
2. Revisar o conteúdo contra `docs/adr/template.md` e o change associado.
3. Atualizar referências e status de ADRs parcialmente ou integralmente superadas.
4. Regerar/revisar este índice.
5. Commitar a ADR junto dos artefatos de decisão relacionados.
