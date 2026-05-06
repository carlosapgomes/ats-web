# Proposal: Alinhamento Visual com Mocks de Referência

**Change ID**: `ui-alinhamento-mocks`
**Fase**: 2b — intermediária entre Fase 2 (Pipeline LLM) e Fase 3 (Fila Médica)
**Risco**: ESSENCIAL (apenas templates, CSS, JS — zero lógica de negócio)
**Dependências**: nenhuma (não bloqueia nem depende de outras changes)

## Problema

Os mocks em `demo-reference/` (dashboard.html, case-detail.html, styles.css) foram
produzidos como referência visual para todo o sistema. Durante a implementação das
Fases 0-2, **nunca foram consultados**. Resultado:

1. **Estáticos quebrados**: `upload.js` retorna 404 no runserver — o upload zone é
   invisível e não-funcional no browser.
2. **CSS incompleto**: `app.css` omite classes presentes no mock (timeline dots,
   decision sections, summary boxes, pulse animation, responsive breakpoints,
   notif-badge, etc.).
3. **Templates desalinhados**: os templates Django não usam as mesmas convenções de
   classe e estrutura dos mocks.
4. **`.env` não é carregado**: `python-dotenv` está no `pyproject.toml` mas nunca
   é chamado — settings dependem de variáveis de ambiente que não existem.
5. **`home_view` não redireciona**: continua renderizando placeholder em vez de
   redirecionar para o app do papel ativo.
6. **`INTRANET_IP_RANGE` não suporta múltiplos ranges**:Middleware falha com
   `127.0.0.0/8,192.168.15.0/24`.

## Objetivo

Corrigir todos os itens acima para que o sistema rodando em `localhost` seja
**visual e funcionalmente equivalente** aos mocks de referência.

## Escopo

- `static/css/app.css` — alinhar com `demo-reference/css/styles.css`
- `static/js/upload.js` — já funcional, só precisa servir corretamente
- `templates/base.html` — alinhar com estrutura dos mocks
- `templates/intake/intake_home.html` — alinhar com `demo-reference/nir/dashboard.html`
- `templates/intake/case_detail.html` — alinhar com `demo-reference/nir/case-detail.html`
- `templates/intake/my_cases.html` — alinhar com seção "Casos Recentes" do dashboard
- `config/settings/base.py` — carregar `.env` via `python-dotenv`
- `apps/accounts/views.py` — `home_view` redireciona para app do papel ativo
- `apps/accounts/middleware.py` — suportar múltiplos CIDR ranges
- Testes para middleware multi-range e redirect do home_view

## Fora de escopo

- Nova funcionalidade de negócio
- Templates de outras fases (doctor, scheduler, manager)
- Mudanças em modelos, views ou ORM
- Templates admin
