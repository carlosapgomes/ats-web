/**
 * Teste complementar (Node) da inversão de ordem das opções no mobile.
 *
 * Task: tasks/quick-ui-admission-flow-mobile-order.md. A cobertura canônica do
 * contrato HTML é Django-side (`apps/doctor/tests/test_admission_flow_order.py`);
 * este teste isola o comportamento do script real `static/js/mobile_select_order.js`
 * em um mini-DOM sem dependências externas (sem package.json, sem jsdom).
 *
 * Execução: node --test static/js/tests/mobile_select_order.test.js
 */

'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const SCRIPT_PATH = path.join(__dirname, '..', 'mobile_select_order.js');
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

// Espelha o select de templates/doctor/decision.html (ordem SSR = desktop).
const DESKTOP_ORDER = ['', 'scheduled', 'immediate', 'pre_icu', 'ward_icu_backup', 'pediatric_appt'];
const MOBILE_ORDER = ['', 'pediatric_appt', 'ward_icu_backup', 'pre_icu', 'immediate', 'scheduled'];
const MARKER_SELECTOR = 'select[data-mobile-reverse-options]';

// ── Mini-DOM (apenas a superfície usada pelo script) ──────────────────────

function createOption(value) {
  return { tagName: 'OPTION', value, selected: false, parentNode: null };
}

function createSelect(values, marked) {
  const select = {
    tagName: 'SELECT',
    childNodes: [],
    attributes: marked ? { 'data-mobile-reverse-options': '' } : {},
    appendChild(child) {
      const index = select.childNodes.indexOf(child);
      if (index !== -1) select.childNodes.splice(index, 1);
      child.parentNode = select;
      select.childNodes.push(child);
      return child;
    },
  };
  Object.defineProperty(select, 'options', { get: () => select.childNodes.slice() });
  values.forEach((value, index) => {
    const option = createOption(value);
    select.appendChild(option);
    option.selected = index === 0;
  });
  return select;
}

function valuesOf(select) {
  return select.options.map((option) => option.value);
}

function createMediaQueryList(matches) {
  const listeners = [];
  return {
    matches,
    addEventListener(type, handler) {
      if (type === 'change') listeners.push(handler);
    },
    set(newMatches) {
      this.matches = newMatches;
      listeners.forEach((handler) => handler({ matches: newMatches }));
    },
  };
}

/**
 * Carrega o script real em um sandbox. Por padrão o `document` fica em
 * `loading` (auto-init adiado), para os testes de `enhance` chamarem a API
 * explicitamente; os testes de auto-init escolhem o `readyState`.
 */
function loadScript({ matches = false, selects = [], readyState = 'loading', withMatchMedia = true } = {}) {
  const document = {
    readyState,
    listeners: {},
    addEventListener(type, handler) {
      document.listeners[type] = document.listeners[type] || [];
      document.listeners[type].push(handler);
    },
    querySelectorAll(selector) {
      return selector === MARKER_SELECTOR
        ? selects.filter((select) => select.attributes['data-mobile-reverse-options'] !== undefined)
        : [];
    },
  };
  const mediaQueryList = createMediaQueryList(matches);
  const window = { document, queries: [] };
  if (withMatchMedia) {
    window.matchMedia = (query) => {
      window.queries.push(query);
      return mediaQueryList;
    };
  }
  const sandbox = { window };
  vm.createContext(sandbox);
  vm.runInContext(SCRIPT_SOURCE, sandbox, { filename: SCRIPT_PATH });
  return { window, document, mediaQueryList, api: window.MobileSelectOrder };
}

// ── enhance: inversão e restauração ───────────────────────────────────────

test('enhance inverte as opções reais no mobile e mantém o placeholder em primeiro', () => {
  const { window, mediaQueryList, api } = loadScript();
  assert.ok(api, 'mobile_select_order.js não expôs window.MobileSelectOrder');
  const select = createSelect(DESKTOP_ORDER, true);

  api.enhance(select, mediaQueryList);
  mediaQueryList.set(true);

  assert.deepEqual(valuesOf(select), MOBILE_ORDER);
  assert.equal(window.queries.length, 0, 'enhance usa o mql recebido, não consulta o window');
});

test('enhance mantém a ordem do SSR fora do mobile', () => {
  const { mediaQueryList, api } = loadScript();
  const select = createSelect(DESKTOP_ORDER, true);

  api.enhance(select, mediaQueryList);
  mediaQueryList.set(false);

  assert.deepEqual(valuesOf(select), DESKTOP_ORDER);
});

test('alternar mobile → desktop → mobile é idempotente e restaura a ordem original', () => {
  const { mediaQueryList, api } = loadScript({ matches: true });
  const select = createSelect(DESKTOP_ORDER, true);

  api.enhance(select, mediaQueryList);
  assert.deepEqual(valuesOf(select), MOBILE_ORDER, 'matches=true no enhance já inverte');

  mediaQueryList.set(false);
  assert.deepEqual(valuesOf(select), DESKTOP_ORDER, 'saiu do mobile: ordem original exata');
  mediaQueryList.set(true);
  mediaQueryList.set(true);
  assert.deepEqual(valuesOf(select), MOBILE_ORDER, 'reaplicar no mobile não acumula inversão');
  mediaQueryList.set(false);
  assert.deepEqual(valuesOf(select), DESKTOP_ORDER);
});

test('a opção selecionada é preservada após a inversão (valor submetido não muda)', () => {
  const { mediaQueryList, api } = loadScript();
  const select = createSelect(DESKTOP_ORDER, true);
  const chosen = select.options[1]; // scheduled
  select.options[0].selected = false;
  chosen.selected = true;

  api.enhance(select, mediaQueryList);
  mediaQueryList.set(true);

  assert.equal(select.options[select.options.length - 1], chosen, 'opção escolhida continua sendo o mesmo nó');
  assert.equal(chosen.selected, true, 'selectedness preservada ao mover o nó');
  assert.equal(select.options.filter((option) => option.selected).length, 1, 'uma única opção selecionada');
});

// ── enhanceAll: seletor declarativo e auto-init ───────────────────────────

test('auto-init só toca selects marcados e usa o corte de md (768px)', () => {
  const marked = createSelect(DESKTOP_ORDER, true);
  const untouched = createSelect(DESKTOP_ORDER, false);
  const { window, mediaQueryList, api } = loadScript({ matches: true, selects: [marked, untouched], readyState: 'complete' });

  assert.deepEqual(valuesOf(marked), MOBILE_ORDER, 'document pronto: auto-init aplicou');
  assert.deepEqual(valuesOf(untouched), DESKTOP_ORDER, 'select sem o atributo fica na ordem do SSR');
  assert.deepEqual(window.queries, [api.MOBILE_QUERY], 'uma única consulta de mídia por página');
  assert.equal(api.MOBILE_QUERY, '(max-width: 767.98px)');

  mediaQueryList.set(false);
  assert.deepEqual(valuesOf(marked), DESKTOP_ORDER, 'auto-init responde ao change do mql');
});

test('auto-init espera o DOMContentLoaded quando o document ainda está carregando', () => {
  const select = createSelect(DESKTOP_ORDER, true);
  const { document, mediaQueryList, api } = loadScript({ matches: true, selects: [select], readyState: 'loading' });

  assert.deepEqual(valuesOf(select), DESKTOP_ORDER, 'nada antes do DOMContentLoaded');
  assert.ok(api, 'API exposta mesmo com document carregando');
  assert.ok(document.listeners.DOMContentLoaded, 'registrou o auto-init');

  document.listeners.DOMContentLoaded.forEach((handler) => handler());
  assert.deepEqual(valuesOf(select), MOBILE_ORDER);

  mediaQueryList.set(false);
  assert.deepEqual(valuesOf(select), DESKTOP_ORDER);
});

test('sem window.matchMedia o script é no-op e mantém a ordem do SSR', () => {
  const select = createSelect(DESKTOP_ORDER, true);
  const { window, api } = loadScript({ withMatchMedia: false, selects: [select], readyState: 'complete' });

  assert.ok(api, 'API exposta mesmo sem matchMedia');
  assert.equal(api.enhanceAll(window.document).length, 0, 'nada aplicado');
  assert.deepEqual(valuesOf(select), DESKTOP_ORDER);
});
