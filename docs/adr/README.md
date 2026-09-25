# Architecture Decision Records

Registros de decisoes arquiteturais importantes do projeto.

## ADRs Ativas
| Numero | Titulo | Status | Data |
|--------|--------|--------|------|
| [ADR-0001](ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md) | Arquitetura Django Web SSR para ATS de Triagem EDA | Accepted | 2026-05-30 |
| [ADR-0002](ADR-0002-emails-transacionais-autenticacao-cadastro.md) | Emails transacionais para autenticação e cadastro | Accepted | 2026-07-26 |
| [ADR-0003](ADR-0003-perfis-procedimento-tipo-exame-explicito.md) | Perfis de procedimento e tipo de exame explícito | Accepted — parcialmente superada pela [ADR-0004](ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md) nas decisões 1, 2, 3, 5, 6, 8 e 9. As decisões 4, 7, 10 e 11 permanecem válidas. | 2026-08-09 |
| [ADR-0004](ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md) | Procedimentos múltiplos e contrato LLM neutro | Accepted — parcialmente superada pela [ADR-0006](ADR-0006-ecoendoscopia-e-cpre-como-procedimentos-independentes.md) e pela [ADR-0010](ADR-0010-catalogo-ampliado-e-pacotes-atomicos-de-procedimentos-endoscopicos.md) nas decisões que limitavam catálogo e contrato gravável a quatro tipos e schema 3.0. | 2026-09-12 |
| [ADR-0005](ADR-0005-local-de-archive-openspec.md) | Local de archive dos changes OpenSpec | Accepted | 2026-08-18 |
| [ADR-0006](ADR-0006-ecoendoscopia-e-cpre-como-procedimentos-independentes.md) | Ecoendoscopia e CPRE como procedimentos independentes | Accepted — precedência especializada parcialmente superada pela [ADR-0008](ADR-0008-precedencia-procedimentos-especializados-reconciliacao.md); catálogo/contrato 3.0 parcialmente superados pela [ADR-0010](ADR-0010-catalogo-ampliado-e-pacotes-atomicos-de-procedimentos-endoscopicos.md). | 2026-09-12 |
| [ADR-0007](ADR-0007-cobertura-de-follow-up-restrita-a-procedimentos-autorizados.md) | Cobertura de follow-up restrita a procedimentos autorizados | Accepted — referências à taxonomia de causas parcialmente superadas pela [ADR-0009](ADR-0009-taxonomia-oficial-causas-nao-realizacao.md); decisão de cobertura permanece válida. | 2026-09-13 |
| [ADR-0008](ADR-0008-precedencia-procedimentos-especializados-reconciliacao.md) | Precedência de procedimentos especializados na reconciliação | Accepted | 2026-09-18 |
| [ADR-0009](ADR-0009-taxonomia-oficial-causas-nao-realizacao.md) | Taxonomia oficial e compatibilidade histórica das causas de não realização | Accepted | 2026-09-18 |
| [ADR-0010](ADR-0010-catalogo-ampliado-e-pacotes-atomicos-de-procedimentos-endoscopicos.md) | Catálogo ampliado e pacotes atômicos de procedimentos endoscópicos | Accepted | 2026-09-25 |

## ADRs Deprecated/Superseded
| Numero | Titulo | Status | Data |
|--------|--------|--------|------|
| - | - | - | - |

## Como criar uma nova ADR
1. Execute `python3 adr_generator.py --title "Sua decisao"`
2. Revise contexto, decisao, alternativas e consequencias
3. Commit da ADR junto do change relacionado
