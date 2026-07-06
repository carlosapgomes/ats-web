# Design: Busca rápida client-side na fila médica pendente

## Estado atual

`apps/doctor/views.py::_doctor_queue_context()` monta `pending_cases` com todos os casos em `CaseStatus.WAIT_DOCTOR` e renderiza cards em `templates/doctor/_queue_content.html`.

`templates/doctor/queue.html` envolve o partial em:

```django
<div
  id="doctor-queue-content"
  hx-get="{% url 'doctor:queue_partial' %}?tab={{ active_tab }}"
  hx-trigger="every 20s"
  hx-swap="innerHTML"
>
  {% include "doctor/_queue_content.html" %}
</div>
```

Não há paginação na fila médica atual. Logo, um filtro client-side opera sobre todos os pendentes carregados.

## Decisões

### D1. Implementar filtro client-side, não server-side

A busca será feita com Vanilla JS sobre cards renderizados no HTML.

Motivos:

- atende ao problema atual de 50–60 pendentes;
- não cria endpoint novo;
- não coloca nome de paciente em query string, histórico do navegador ou logs;
- reduz risco e escopo;
- preserva SSR puro e ausência de SPA/API REST.

Limitação aceita: se houver paginação futura, o filtro client-side só buscará na página carregada. Como hoje não há paginação, isso não limita o uso atual.

### D2. Campo fora da área trocada por HTMX

Adicionar os controles de busca em `templates/doctor/queue.html`, fora de `#doctor-queue-content`, e somente quando `active_tab == "pending"`.

Motivos:

- evita o auto-refresh apagar o texto digitado;
- permite reaplicar o filtro após o partial atualizar;
- mantém `templates/doctor/_queue_content.html` focado nos cards.

Estrutura conceitual:

```django
{% if active_tab == 'pending' %}
<div class="card mb-3" data-doctor-queue-filter-panel>
  <label for="doctor-queue-search">Buscar por nome ou ocorrência</label>
  <div class="input-group">
    <input id="doctor-queue-search" type="search" data-doctor-queue-search>
    <button type="button" data-doctor-queue-clear>Limpar</button>
  </div>
  <div data-doctor-queue-filter-status></div>
</div>
{% endif %}
```

### D3. Cards com dados pesquisáveis explícitos

Em `templates/doctor/_queue_content.html`, nos cards pendentes, adicionar atributos `data-*` na raiz do card/coluna:

```django
<div class="col-12" data-doctor-queue-card
     data-patient-name="{{ c.patient_name }}"
     data-agency-record-number="{{ c.agency_record_number }}">
```

O JS deve ler os atributos e não depender de parsing frágil de texto visual.

### D4. Normalização no JavaScript

Criar `static/js/doctor_queue_filter.js` com IIFE Vanilla JS, sem dependências novas.

Normalização esperada:

```javascript
function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}
```

Busca:

- comparar termo normalizado com `data-patient-name` normalizado;
- comparar termo normalizado com `data-agency-record-number` normalizado;
- aceitar correspondência parcial (`includes`).

### D5. Limiar operacional

Para evitar filtro excessivo por 1–2 letras em nomes comuns:

- se o termo contém letras e tem menos de 3 caracteres, não filtrar; mostrar todos os cards e mensagem curta: `Digite pelo menos 3 letras para filtrar por nome.`;
- se o termo contém apenas números/caracteres de ocorrência, pode filtrar a partir de 1 caractere, pois o objetivo é localizar `agency_record_number`.

Implementação simples aceitável:

```javascript
function shouldFilter(rawTerm) {
  var term = rawTerm.trim();
  if (!term) return false;
  var hasLetter = /[A-Za-zÀ-ÿ]/.test(term);
  return !hasLetter || normalizeText(term).length >= 3;
}
```

### D6. Limpeza explícita e não persistência

O filtro deve ser temporário da página atual:

- botão `Limpar` limpa input, status e exibe todos os cards;
- tecla `Esc` no input executa o mesmo comportamento;
- apagar manualmente todo o texto também limpa;
- não usar query string, localStorage, sessionStorage, cookie ou sessão Django.

Ao abrir um card e voltar depois, a página recarrega sem filtro. Isso evita a percepção de que a fila tem menos pacientes do que realmente tem.

### D7. Reaplicar após auto-refresh HTMX

O JS deve escutar o evento global do HTMX e reaplicar o filtro se o conteúdo atualizado for `#doctor-queue-content`:

```javascript
document.body.addEventListener("htmx:afterSwap", function (event) {
  if (event.target && event.target.id === "doctor-queue-content") {
    applyFilter();
  }
});
```

Se HTMX não existir, o script deve continuar funcionando no carregamento inicial.

### D8. Acessibilidade e clareza

- Input com `<label>` visível.
- Botão `Limpar` com `type="button"`.
- Status com `aria-live="polite"` para leitores de tela.
- Mensagem de sem resultado (`Nenhum paciente encontrado para este filtro.`) pode ser um elemento escondido/exibido via JS dentro de `queue.html` ou `queue_content`.

## Arquivos previstos

| Arquivo | Tipo | Mudança |
|---------|------|---------|
| `templates/doctor/queue.html` | modificado | controles de busca fora do partial + include do JS em `extra_js` |
| `templates/doctor/_queue_content.html` | modificado | atributos `data-*` nos cards pendentes e, se necessário, elemento de vazio filtrado |
| `static/js/doctor_queue_filter.js` | novo | lógica Vanilla JS de filtro/limpeza/reaplicação pós-HTMX |
| `apps/doctor/tests/test_views.py` | modificado | testes server-side de presença dos controles, atributos e isolamento da aba decidida |

Ideal: 4 arquivos. Evitar tocar `apps/doctor/views.py`, modelos ou URLs.

## Estratégia de testes

Como o comportamento de filtro é majoritariamente JS sem browser runner configurado, os testes Django devem garantir o contrato HTML que o JS consome:

- controles renderizados na aba pendente;
- script incluído somente/ao menos na página da fila;
- cards pendentes têm `data-doctor-queue-card`, `data-patient-name` e `data-agency-record-number`;
- aba `Decididos Hoje` não renderiza controles de busca pendente;
- `hx-get` segue preservando `tab={{ active_tab }}`.

O implementador pode adicionar testes unitários JS apenas se já existir infraestrutura; não deve criar framework/bundler novo neste slice.

## Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Médico esquecer filtro ativo | status explícito + botão `Limpar` + não persistir ao sair/voltar |
| Auto-refresh apagar busca digitada | controles fora do partial + reaplicar no `htmx:afterSwap` |
| JS quebrar se não houver cards | funções defensivas e retorno seguro |
| Busca depender de texto visual frágil | usar `data-*` explícitos nos cards |
| Escopo crescer para busca server-side | registrar fora de escopo; sem endpoint novo |
| Acentos impedirem encontro | normalização NFD no JS |

## Rollback

Reverter:

1. `static/js/doctor_queue_filter.js`;
2. bloco de busca e include JS em `templates/doctor/queue.html`;
3. atributos `data-*` adicionados aos cards em `templates/doctor/_queue_content.html`;
4. testes associados.

Não há migração, dados persistidos ou alteração de fluxo clínico.
