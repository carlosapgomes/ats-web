# Design: Header responsivo com `navbar` do Bootstrap

**Change ID**: `mobile-header-navbar`

## Contexto

O header atual (`templates/base.html`) é um `<header class="app-header">` com `d-flex flex-column flex-lg-row`. No mobile, três problemas combinados degradam a renderização: (a) uma regra CSS global força verticalização acidental; (b) alinhamento pensado só para `lg`; (c) texto longo do avatar estoura a largura. A solução combina correção ortogonal do bug CSS + adoção do `navbar` Bootstrap + ajustes complementares mobile.

## Arquivos afetados

- `templates/base.html` — refator do `<header>` → `navbar` (Slice 2).
- `static/css/app.css` — correção do seletor `:has()` (Slice 1); regras do `navbar`/avatar mobile (Slices 2 e 3).
- `tests/` (novo) — teste de renderização do template base (Slice 2).

Não há mudanças em `models.py`, `views.py`, `urls.py`, `services.py` ou FSM.

## Solução técnica

### Estrutura HTML alvo (`navbar`, Opção C)

```html
<header class="app-header navbar navbar-expand-lg">
  <div class="container">
    <!-- Marca: sempre visível -->
    <a class="navbar-brand d-flex align-items-center gap-2 text-white" href="/">
      <img src="{% static 'icons/icon-192.png' %}" alt="" width="32" height="32">
      <span>
        <span class="app-header__title d-block">{{ app_display_name }}</span>
        <span class="app-header__subtitle d-block">{% block subtitle %}...{% endblock %}</span>
      </span>
    </a>

    {% if user.is_authenticated %}
    <!-- Sempre visíveis (mobile + desktop) -->
    <div class="d-flex align-items-center gap-2 order-lg-2">
      <a href="{% url 'notifications' %}" class="btn btn-sm btn-light ...">🔔</a>
      <a href="{% url 'profile' %}" class="avatar-circle">JS</a>

      <!-- Hambúrguer (somente < lg) -->
      <button class="navbar-toggler" type="button"
              data-bs-toggle="collapse" data-bs-target="#sessionMenu"
              aria-controls="sessionMenu" aria-expanded="false" aria-label="Menu da sessão">
        <span class="navbar-toggler-icon"></span>
      </button>
    </div>

    <!-- Colapsável (somente < lg; no desktop fica expandido) -->
    <div class="collapse navbar-collapse order-lg-3" id="sessionMenu">
      <!-- nome completo + papel -->
      <!-- manual do usuário -->
      <!-- trocar papel (se multi-role) -->
      <!-- sair -->
    </div>
    {% endif %}
  </div>
</header>
```

**Notas de implementação:**
- O `order-lg-*` garante que no desktop a ordem visual seja marca → ações de sessão (à direita), e no mobile marca → [notificação, avatar, hambúrguer] → menu colapsado.
- No desktop, o `navbar-collapse` aparece expandido inline (Bootstrap padrão), sem botão hambúrguer visível (este fica `display:none` acima de `lg` por padrão do Bootstrap).
- Avatar em iniciais: gerar via template (primeiras letras de `user.get_full_name|default:user.username`).

### Correção do bug CSS (Slice 1)

Hoje (`static/css/app.css`, `@media (max-width: 767.98px)`):

```css
/* Action button rows: stack vertically */
.d-flex.gap-2:has(> .btn) {
  flex-direction: column;
}
```

**Depois:** escopar ao contexto onde faz sentido (ações de case cards):

```css
.case-card .d-flex.gap-2:has(> .btn),
.btn-stack-mobile {
  flex-direction: column;
}
```

Validar que nenhum outro seletor conta com o comportamento global. (Investigar `.d-flex.gap-1.justify-content-lg-end` em `@media (max-width: 575.98px)` também — mantém-se, pois é mais específico.)

### Avatar compacto (Slice 3)

- Em < `sm` (576px): círculo com iniciais (ex.: "JS"), sem texto.
- Em ≥ `sm`: círculo + "Nome · **papel**" (texto completo), como hoje.
- Implementação: `.avatar-circle` com largura fixa 2rem, `d-inline-flex` centralizado; texto envolvente com classe `.avatar-meta` oculta via `d-none d-sm-inline`.

### Área de toque (Slice 3)

```css
@media (max-width: 991.98px) {
  .navbar .notification-icon-btn,
  .navbar .avatar-circle {
    min-width: 44px;
    min-height: 44px;
  }
}
```

### Preservação visual do desktop

- O gradiente `.app-header` (linear-gradient `--hospital-primary` → `--hospital-secondary`) é aplicado sobre o `navbar`.
- `navbar-expand-lg` garante que acima de 992px nada colapsa.
- Cores/typografia atuais (`.app-header__title`, `.app-header__subtitle`, `.app-session-meta`) reaproveitadas.

## Testabilidade

Templates Django não rodam isolados sem contexto. Slice 2 inclui um teste `pytest-django` que:

1. Renderiza `base.html` com `RequestFactory` + contexto mínimo (`user` autenticado com `roles.count() > 1`, `app_display_name`, `active_role_display`).
2. Asserções:
   - Contém `navbar navbar-expand-lg`.
   - Contém `navbar-brand` com o nome do app.
   - Contém `navbar-toggler` com `data-bs-target="#sessionMenu"`.
   - Contém `collapse navbar-collapse` com id `sessionMenu`.
   - Contém link de notificação e de sair.
3. Estado não autenticado: header sem bloco de sessão.

Teste de regressão visual do desktop é manual (relatório do slice documenta o checklist).

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Regressão visual no desktop | `navbar-expand-lg` + mesmas classes de cor/typography; checklist visual no relatório. |
| `navbar-collapse` quebrar layout desktop | Bootstrap só mostra o `collapse` como menu abaixo de `lg`; acima, fica inline. Validar. |
| `:has()` não suportado em navegador alvo | `:has()` já é usado hoje; manter. Se necessário, fornecer fallback via classe explícita `.btn-stack-mobile`. |
| Avatar com iniciais incorretas | Gerar com `{{ user.get_full_name|default:user.username|truncatechars:2 }}` ou filtro customizado simples. |
| JS do badge de notificação quebrar | Estrutura do `<a>` de notificação preserva `id`, `data-*` e classes funcionais; apenas envolvido no `navbar`. |

## Não objetivos (deferidos)

- Menu de navegação por páginas (não existe hoje).
- Tema dark / contraste AAA.
- Logo vetorial custom (usa `icon-192.png` / `icon.svg` existentes).

## Sequência de implementação

Ver `tasks.md`. Slice 1 é independente e de menor risco; Slice 2 depende da decisão de design; Slice 3 é polish sobre o 2.
