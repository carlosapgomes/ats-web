<!-- markdownlint-disable MD013 -->

# Proposal: Badges compactos e próximo passo no dashboard

**Change ID**: `dashboard-badge-progress-ux`  
**Risco**: ESSENCIAL  
**Dependências**: dashboard atual com lista em `templates/dashboard/_case_list.html` e detalhe compartilhado em `templates/intake/case_detail.html`

## Problema

No dashboard mobile, o badge de resultado `✓ Vinda para enfermaria (para retaguarda em UTI)` é longo demais. Ele ocupa a mesma linha/grade da data/hora no card de paciente e pode sobrepor ou empurrar visualmente a data. O mesmo tipo de texto longo também transborda o limite direito do card `Resultado Final` na página de detalhes do caso em telas pequenas.

Além disso, a lista de cards mostra o resultado/decisão principal, mas não mostra explicitamente qual é o próximo passo operacional pendente. Para descobrir isso, o usuário precisa inferir pelo status ou usar filtros, o que degrada a leitura rápida da fila gerencial.

## Objetivo

Melhorar a leitura mobile dos cards do dashboard e do card `Resultado Final` sem alterar as opções clínicas/operacionais apresentadas ao médico:

1. usar textos compactos apenas em badges de apresentação quando o label completo for longo;
2. impedir overflow/sobreposição de badges em mobile;
3. adicionar um sub-badge/indicador de próximo passo pendente nos cards da lista do dashboard.

## Escopo incluído

- Dashboard: cards de pacientes em `templates/dashboard/_case_list.html`.
- Dashboard backend/presenter: helpers em `apps/dashboard/views.py` para labels compactos e próximo passo, se necessário.
- CSS pontual em `static/css/app.css` para badges/linhas responsivas, se Bootstrap puro não resolver.
- Detalhe do caso compartilhado (`templates/intake/case_detail.html`) quando aberto pelo dashboard ou NIR, apenas no bloco `Resultado Final` para evitar overflow de badge longo.
- Testes de contrato HTML em `apps/dashboard/tests/test_dashboard.py` e/ou testes existentes de detalhe NIR/dashboard.

## Fora de escopo

- Alterar labels das opções do médico em formulários de decisão.
- Alterar regras de negócio, FSM, estados, permissões, filtros, queries ou migrations.
- Criar status novo ou campo novo no banco.
- Trocar Bootstrap/Vanilla JS por framework ou adicionar screenshot tests.
- Mudar a semântica do resultado final ou do fluxo operacional.

## Critérios de sucesso

- Badge principal no card mobile do dashboard não sobrepõe data/hora.
- Badge longo de enfermaria/retaguarda usa label compacto no dashboard, preservando significado.
- Cards do dashboard mostram um segundo indicador compacto de próximo passo quando houver pendência relevante.
- O indicador de próximo passo é derivado deterministicamente do estado/status atual, sem novo campo persistido.
- Badge do `Resultado Final` não transborda no mobile.
- Textos completos usados nas opções do médico e descrições de fluxo continuam preservados.
- Testes relevantes passam e quality gate do `AGENTS.md` fica verde.
