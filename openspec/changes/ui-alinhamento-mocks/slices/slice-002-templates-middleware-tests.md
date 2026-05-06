# Slice 2: Templates alinhados com mocks + middleware multi-range + home redirect

## Objetivo

Alinhar os templates Django com a estrutura e classes dos mocks de referência,
e garantir que o middleware suporta múltiplos CIDR ranges e o home redirect funciona.

## Arquivos a modificar

### 1. `templates/base.html`

Alinhar estrutura com a dos mocks:
- Google Fonts via `<link>` (já deve ter — verificar)
- Bootstrap JS via CDN no final do body (verificar se tem)
- Estrutura do header: avatar, nome, papel ativo, botões trocar/sair

Comparar com `demo-reference/nir/dashboard.html` e ajustar diferenças de estrutura.

### 2. `templates/intake/intake_home.html`

Alinhar com `demo-reference/nir/dashboard.html`:
- Upload zone: `<input type="file">` dentro da zona (não `d-none` separado)
- Upload preview: igual ao mock
- Casos recentes: cards com `.patient-name` (quando disponível), badges com status CSS correto
- JS: se `upload.js` externo funciona, manter; senão embeddar inline como no mock

### 3. `templates/intake/my_cases.html`

Alinhar com a seção "Casos Recentes" do `demo-reference/nir/dashboard.html`:
- Cards com `.patient-name` e `.case-meta`
- Badges com classes `.status-done`, `.status-progress`, `.status-denied`
- Layout idêntico ao mock

### 4. `templates/intake/case_detail.html`

Alinhar com `demo-reference/nir/case-detail.html`:
- Top info card: nome, registro, data, status badge
- Stepper: 5 etapas com ícones e classes `.done` / `.current`
- Timeline: `.timeline-event` com `.timeline-event__dot` colorido por tipo de ator
  (`.system`, `.doctor`, `.scheduler`, `.reception`)
- Ações: botão "Confirmar Recebimento" com feedback visual (igual ao mock)

### 5. `apps/accounts/middleware.py`

`_is_intranet_ip` já suporta múltiplos ranges (implementado em sessão anterior).
Verificar se está commitado. Se não, commitar.

### 6. `apps/accounts/views.py`

`home_view` já redireciona (implementado em sessão anterior).
Verificar se está commitado. Se não, commitar.

## Arquivos novos (testes)

### 7. `apps/accounts/tests/test_middleware.py`

Adicionar testes para múltiplos CIDR ranges:
- `test_single_range_match`
- `test_single_range_no_match`
- `test_multiple_ranges_match_first`
- `test_multiple_ranges_match_second`
- `test_multiple_ranges_no_match`
- `test_empty_range_returns_false`
- `test_invalid_ip_returns_false`

### 8. `apps/accounts/tests/test_views.py`

Adicionar testes para `home_view` redirect:
- `test_home_redirects_to_intake_for_nir`
- `test_home_redirects_to_switch_role_when_no_role`
- `test_home_redirects_to_intake_for_doctor` (fallback temporário)

## Critérios de sucesso

- [ ] Templates renderizam com mesma estrutura DOM dos mocks
- [ ] Classes CSS do mock estão presentes nos templates
- [ ] Timeline dots coloridos por tipo de ator (system/doctor/scheduler/reception)
- [ ] Upload zone funcional: click abre file picker, drag & drop funciona
- [ ] Middleware suporta `"127.0.0.0/8,192.168.15.0/24"`
- [ ] `home_view` redireciona para `intake:home` quando papel=nir
- [ ] Todos os testes (291 + novos) passam
- [ ] ruff + mypy clean

## Arquivos: ideal ≤ 8
