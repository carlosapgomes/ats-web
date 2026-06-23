# Design: Header de notificações e badges operacionais

## Estado atual

### Header global

`templates/base.html` renderiza, para usuário autenticado:

```django
<a href="{% url 'notifications' %}"
   id="notification-badge"
   class="btn btn-sm btn-light notif-badge"
   data-notifications-badge
   data-unread-count-url="{% url 'notifications_unread_count' %}"
   data-count="{{ notification_unread_count|default:0 }}"
   aria-label="Notificações: {{ notification_unread_count|default:0 }} não lidas">
  Notificações
  {% if notification_unread_count %}
  <span class="badge bg-danger ms-1">{{ notification_unread_count }}</span>
  {% endif %}
</a>
```

Logo depois, o link do perfil renderiza avatar + nome/papel e, quando existe, `queue_count`:

```django
{{ user.get_full_name|default:user.username }} · <strong>{{ active_role_display }}</strong>
{% if queue_count %}
<span class="badge bg-danger ms-1">{{ queue_count }}</span>
{% endif %}
```

Esse `queue_count` vem de `apps/accounts/context_processors.py` e representa fila operacional para médico/agendador, não notificações pessoais.

### Página de notificações

`templates/accounts/notifications.html` tem título, lista/estado vazio e `Marcar todas como lidas` quando há não lidas, mas não tem botão de retorno sempre visível.

### CSS de contador

`static/css/app.css` define `.notif-badge::after` vermelho, usando `data-count`. A classe é usada tanto para notificações quanto para abas de fila.

### Abas operacionais

`templates/doctor/queue.html` usa `.notif-badge` em:

- `Pendentes`, com `pending_count`;
- `Decididos Hoje`, com `decided_count`.

`templates/scheduler/queue.html` usa `.notif-badge` em:

- `Pendentes`, com `total_notice_count`.

A view do agendador já passa `processed_today_count`, mas o template ainda não exibe contador em `Processados Hoje`.

## Dimensionamento em slices

O change será dividido em **2 slices verticais enxutos**:

1. **Slice 001 — Header e inbox de notificações**
   - valor entregue: usuário identifica notificações como sino, não confunde fila com perfil, e consegue voltar da inbox.
   - superfície principal: `templates/base.html`, `templates/accounts/notifications.html`, testes de accounts e CSS mínimo se necessário.

2. **Slice 002 — Badges operacionais em abas de filas**
   - valor entregue: contadores de filas ficam semanticamente corretos; concluídos usam cor neutra; agendador vê contador de `Processados Hoje`.
   - superfície principal: `static/css/app.css`, `templates/doctor/queue.html`, `templates/scheduler/queue.html`, testes de doctor/scheduler.

Motivo para 2 slices: manter cada implementação pequena, testável e reversível. Um único slice misturaria header global, inbox e duas filas operacionais, aumentando arquivos e risco.

## Decisões

### D1. Notificações ficam no header global como sino

Usar botão/link compacto com SVG inline de Bootstrap Icon `bell` ou `bell-fill`, sem adicionar dependência global de Bootstrap Icons.

Motivos:

- o projeto usa Bootstrap 5.3, mas não carrega Bootstrap Icons globalmente;
- já existe precedente de SVG inline inspirado em Bootstrap Icons em `static/js/password-toggle.js`;
- evita nova dependência/CDN;
- melhora escaneabilidade do header.

Exemplo conceitual:

```django
<a href="{% url 'notifications' %}"
   id="notification-badge"
   class="btn btn-sm btn-light notification-icon-btn"
   data-notifications-badge
   data-unread-count-url="{% url 'notifications_unread_count' %}"
   data-count="{{ notification_unread_count|default:0 }}"
   aria-label="Notificações: {{ notification_unread_count|default:0 }} não lidas"
   title="Notificações">
  <svg ... aria-hidden="true">...</svg>
  <span class="visually-hidden">Notificações</span>
</a>
```

O contador pode continuar usando `data-count` e pseudo-elemento, desde que a classe seja específica de notificação e o JS continue encontrando `[data-notifications-badge]`.

### D2. Remover `queue_count` do nome/avatar

Não remover o context processor neste change. Apenas deixar de renderizar `queue_count` no header.

Motivos:

- alteração mínima e reversível;
- pode haver testes/uso futuro do contexto;
- o contador operacional já existe nas abas de médico/agendador.

### D3. Botão de retorno determinístico na inbox

Adicionar link para `{% url 'home' %}` com texto `Voltar ao início`, sempre visível no cabeçalho da página.

Motivos:

- funciona mesmo quando usuário acessa `/notifications/` diretamente;
- evita depender de `history.back()`;
- respeita roteamento por papel ativo via `home_view`.

### D4. Separar classes de notificação e contadores de abas

Manter uma classe específica para badge de notificação, por exemplo:

```css
.notification-badge { position: relative; }
.notification-badge::after { background: #e74c3c; ... }
```

Criar classes de contador de aba, por exemplo:

```css
.nav-count-badge { position: relative; }
.nav-count-badge::after { ... }
.nav-count-badge--danger::after { background: #e74c3c; color: #fff; }
.nav-count-badge--neutral::after { background: #6c757d; color: #fff; }
```

Também esconder pseudo-elemento quando `data-count="0"` ou ausente.

### D5. Semântica de cores

- Vermelho: itens não lidos/pendentes que pedem ação.
- Neutro: itens já concluídos no dia.

Aplicação:

- `doctor Pendentes`: `nav-count-badge nav-count-badge--danger`.
- `doctor Decididos Hoje`: `nav-count-badge nav-count-badge--neutral`.
- `scheduler Pendentes`: `nav-count-badge nav-count-badge--danger`.
- `scheduler Processados Hoje`: `nav-count-badge nav-count-badge--neutral`.

### D6. Não alterar NIR

NIR mantém abas sem contadores:

- `Novo Encaminhamento`
- `Meus Casos`
- `Casos Encerrados`

A quantidade total dentro de `Meus Casos` permanece inalterada.

## Arquivos previstos

### Slice 001

| Arquivo | Mudança |
| --- | --- |
| `templates/base.html` | sino, remover badge `queue_count` no perfil |
| `templates/accounts/notifications.html` | botão `Voltar ao início` |
| `static/css/app.css` | CSS mínimo para botão/badge de notificação, se necessário |
| `apps/accounts/tests/test_notifications.py` | testes de sino, polling attrs e botão voltar |
| `apps/accounts/tests/test_context_processors.py` | ajustar/remover teste que esperava `queue_count` no header |

### Slice 002

| Arquivo | Mudança |
| --- | --- |
| `static/css/app.css` | classes semânticas de contador de abas |
| `templates/doctor/queue.html` | trocar `.notif-badge` por classes operacionais; neutro em `Decididos Hoje` |
| `templates/scheduler/queue.html` | trocar `.notif-badge`; adicionar contador neutro em `Processados Hoje` |
| `apps/doctor/tests/test_views.py` | asserts de classes/contadores médicos |
| `apps/scheduler/tests/test_views.py` | asserts de contador `Processados Hoje` e classes |

Se a implementação precisar tocar mais arquivos, deve justificar no relatório do slice.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Quebrar polling de notificações | Preservar `data-notifications-badge`, `data-unread-count-url`, `data-count` e `id="notification-badge"` |
| Ícone sem acessibilidade | Usar `aria-label`, `title` e `visually-hidden` |
| Badge duplicado no sino | Escolher uma única fonte visual de contador: pseudo-elemento por `data-count` ou `<span>`, não ambos |
| Vermelho continuar em concluídos | Testes devem verificar classe neutra nos links concluídos |
| Confundir NIR com novo contador | Slice 002 deve verificar que templates NIR não são alterados ou registrar inspeção no relatório |
| CSS legado `.notif-badge` ainda usado em abas | Trocar templates de filas para classes novas e manter `.notif-badge` apenas se necessário para compatibilidade |

## Estratégia de testes

- Preferir testes SSR por presença de atributos/classes/textos essenciais, sem asserts frágeis de HTML completo.
- Para CSS, usar testes estáticos simples quando fizer sentido:
  - classe neutra existe;
  - classe danger existe;
  - templates usam classes corretas.
- Não testar pixels/cor computada; testar semântica por classe.
- Manter TDD: adicionar/ajustar testes falhando antes de implementação.
