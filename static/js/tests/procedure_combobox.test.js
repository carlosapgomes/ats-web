/**
 * Teste complementar (Node) do combobox pesquisável de procedimento.
 *
 * Design D9: a cobertura canônica é Django-side (contrato HTML/POST, re-render,
 * fallback SSR e validação backend). Este teste isola teclado, ARIA,
 * normalização de busca e ausência de valor livre carregando o arquivo real
 * `static/js/procedure_combobox.js` em um mini-DOM sem dependências externas
 * (sem package.json, sem jsdom — vanilla JS apenas).
 *
 * Execução: node --test static/js/tests/procedure_combobox.test.js
 */

'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const SCRIPT_PATH = path.join(__dirname, '..', 'procedure_combobox.js');
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

// ── Mini-DOM (apenas a superfície usada pelo componente) ──────────────────

class FakeEvent {
  constructor(type, init) {
    this.type = type;
    this.bubbles = Boolean(init && init.bubbles);
    this.defaultPrevented = false;
    this.cancelBubble = false;
  }

  preventDefault() {
    this.defaultPrevented = true;
  }

  stopPropagation() {
    this.cancelBubble = true;
  }
}

function createClassList(element) {
  const read = () => (element.getAttribute('class') || '').split(/\s+/).filter(Boolean);
  const write = (classes) => element.setAttribute('class', classes.join(' '));
  return {
    add(name) {
      const classes = read();
      if (classes.indexOf(name) === -1) {
        classes.push(name);
        write(classes);
      }
    },
    remove(name) {
      write(read().filter((className) => className !== name));
    },
    contains(name) {
      return read().indexOf(name) !== -1;
    },
  };
}

function dispatch(element, event) {
  if (!event.target) {
    event.target = element;
  }
  if (typeof event.preventDefault !== 'function') {
    event.defaultPrevented = false;
    event.preventDefault = function () {
      event.defaultPrevented = true;
    };
  }
  if (typeof event.stopPropagation !== 'function') {
    event.stopPropagation = function () {
      event.cancelBubble = true;
    };
  }
  let current = element;
  while (current) {
    event.currentTarget = current;
    const handlers = (current.listeners && current.listeners[event.type]) || [];
    for (const handler of handlers.slice()) {
      handler.call(current, event);
    }
    if (event.cancelBubble) {
      break;
    }
    current = current.parentNode;
  }
  return !event.defaultPrevented;
}

function createElement(ownerDocument, tagName) {
  const element = {
    tagName: String(tagName).toUpperCase(),
    nodeType: 1,
    parentNode: null,
    childNodes: [],
    attributes: {},
    listeners: {},
    hidden: false,
    disabled: false,
    value: '',
    textContent: '',
    id: '',
    className: '',
    ownerDocument: ownerDocument,
  };

  element.setAttribute = (name, value) => {
    element.attributes[name] = String(value);
    if (name === 'id') {
      element.id = String(value);
    }
    if (name === 'class') {
      element.className = String(value);
    }
  };
  element.getAttribute = (name) =>
    Object.prototype.hasOwnProperty.call(element.attributes, name) ? element.attributes[name] : null;
  element.hasAttribute = (name) => Object.prototype.hasOwnProperty.call(element.attributes, name);
  element.removeAttribute = (name) => {
    delete element.attributes[name];
    if (name === 'id') {
      element.id = '';
    }
    if (name === 'class') {
      element.className = '';
    }
  };
  element.classList = createClassList(element);
  element.appendChild = (child) => {
    if (child.parentNode) {
      child.parentNode.removeChild(child);
    }
    child.parentNode = element;
    element.childNodes.push(child);
    return child;
  };
  element.insertBefore = (child, reference) => {
    if (child.parentNode) {
      child.parentNode.removeChild(child);
    }
    child.parentNode = element;
    const index = element.childNodes.indexOf(reference);
    if (index === -1) {
      element.childNodes.push(child);
    } else {
      element.childNodes.splice(index, 0, child);
    }
    return child;
  };
  element.removeChild = (child) => {
    const index = element.childNodes.indexOf(child);
    if (index !== -1) {
      element.childNodes.splice(index, 1);
      child.parentNode = null;
    }
    return child;
  };
  element.addEventListener = (type, handler) => {
    element.listeners[type] = element.listeners[type] || [];
    element.listeners[type].push(handler);
  };
  element.dispatchEvent = (event) => dispatch(element, event);
  element.focus = () => {
    if (element.ownerDocument) {
      element.ownerDocument.activeElement = element;
    }
  };
  Object.defineProperty(element, 'children', {
    get: () => element.childNodes.filter((node) => node.nodeType === 1),
  });
  if (element.tagName === 'SELECT') {
    Object.defineProperty(element, 'options', {
      get: () => element.childNodes.filter((node) => node.tagName === 'OPTION'),
    });
  }
  return element;
}

function createFakeDocument() {
  const document = {
    nodeType: 9,
    listeners: {},
    activeElement: null,
    readyState: 'complete',
    createElement: (tagName) => createElement(document, tagName),
    createTextNode: (text) => ({ nodeType: 3, textContent: String(text), parentNode: null }),
    addEventListener: (type, handler) => {
      document.listeners[type] = document.listeners[type] || [];
      document.listeners[type].push(handler);
    },
    dispatchEvent: (event) => dispatch(document, event),
    querySelectorAll: () => [],
    querySelector: () => null,
    getElementById: () => null,
  };
  return document;
}

// ── Fixtures ──────────────────────────────────────────────────────────────

function loadCombobox() {
  const fakeWindow = { Event: FakeEvent };
  const sandbox = { window: fakeWindow };
  vm.createContext(sandbox);
  vm.runInContext(SCRIPT_SOURCE, sandbox, { filename: SCRIPT_PATH });
  assert.ok(fakeWindow.ProcedureCombobox, 'procedure_combobox.js não expôs window.ProcedureCombobox');
  return fakeWindow.ProcedureCombobox;
}

function addOption(select, value, text, extra) {
  const option = select.ownerDocument.createElement('option');
  option.value = value;
  option.textContent = text;
  if (extra && extra.aliases) {
    option.setAttribute('data-search-aliases', extra.aliases);
  }
  if (extra && extra.disabled) {
    option.disabled = true;
  }
  select.appendChild(option);
  return option;
}

function buildFixture(document) {
  const root = document.createElement('div');
  const select = document.createElement('select');
  select.setAttribute('id', 'exam-type-select');
  select.setAttribute('name', 'exam_type');
  select.setAttribute('aria-labelledby', 'exam-type-select-label');
  select.setAttribute('aria-describedby', 'exam-type-guidance');
  select.setAttribute('data-procedure-combobox', '');

  addOption(select, '', 'Selecione o tipo de exame…');
  addOption(select, 'eda', 'EDA');
  addOption(select, 'colonoscopy', 'Colonoscopia');
  addOption(select, 'eda_colonoscopy', 'EDA + Colonoscopia', { aliases: 'EDA, Colonoscopia' });
  addOption(select, 'echoendoscopy', 'Ecoendoscopia — indisponível para novos envios', { disabled: true });
  addOption(select, 'cpre', 'CPRE — indisponível para novos envios', { disabled: true });

  root.appendChild(select);
  return { root: root, select: select };
}

function rowsOf(list) {
  return list.childNodes.filter((node) => node.tagName === 'LI');
}

function rowByValue(list, value) {
  return rowsOf(list).find((row) => row.getAttribute('data-value') === value);
}

function visibleRows(list) {
  return rowsOf(list).filter((row) => row.hidden !== true);
}

function fireKey(input, key) {
  const event = new FakeEvent('keydown');
  event.key = key;
  input.dispatchEvent(event);
  return event;
}

function type(input, value) {
  input.value = value;
  input.dispatchEvent(new FakeEvent('input'));
}

// ── Normalização e busca (R3) ─────────────────────────────────────────────

test('normalizeSearch ignora caixa e diacríticos', () => {
  const combobox = loadCombobox();
  assert.equal(combobox.normalizeSearch('Cápsula'), 'capsula');
  assert.equal(combobox.normalizeSearch('  GTT  '), 'gtt');
  assert.equal(combobox.normalizeSearch('EDA + Colonoscopia'), 'eda + colonoscopia');
  assert.equal(combobox.normalizeSearch(null), '');
  assert.equal(combobox.normalizeSearch(undefined), '');
});

test('matchesQuery encontra label canônico e alias aprovado sem criar valor livre', () => {
  const combobox = loadCombobox();
  const capsule = { text: 'EDA + Cápsula', aliases: '' };
  const gastrostomy = { text: 'EDA + Gastrostomia (GTT)', aliases: 'GTT, gastrostomia' };

  assert.equal(combobox.matchesQuery(capsule, 'capsula'), true);
  assert.equal(combobox.matchesQuery(capsule, 'CÁPSULA'), true);
  assert.equal(combobox.matchesQuery(gastrostomy, 'gtt'), true);
  assert.equal(combobox.matchesQuery(capsule, 'colonoscopia'), false);
  assert.equal(combobox.matchesQuery(capsule, ''), true, 'busca vazia mantém todas as opções');
});

test('nextActiveIndex percorre somente opções navegáveis e circula', () => {
  const combobox = loadCombobox();
  const rows = [{ navigable: true }, { navigable: false }, { navigable: true }, { navigable: true }];

  assert.equal(combobox.nextActiveIndex(rows, -1, 1), 0, 'primeira opção navegável');
  assert.equal(combobox.nextActiveIndex(rows, -1, -1), 3, 'última opção navegável');
  assert.equal(combobox.nextActiveIndex(rows, 0, 1), 2, 'pula opção desabilitada');
  assert.equal(combobox.nextActiveIndex(rows, 3, 1), 0, 'circular para frente');
  assert.equal(combobox.nextActiveIndex(rows, 0, -1), 3, 'circular para trás');
  assert.equal(combobox.nextActiveIndex([{ navigable: false }], -1, 1), -1);
});

// ── Semântica ARIA (R2) ───────────────────────────────────────────────────

test('enhance expõe combobox ARIA sobre o select canônico', () => {
  const combobox = loadCombobox();
  const document = createFakeDocument();
  const fixture = buildFixture(document);
  const control = combobox.enhance(fixture.select, { document: document });

  assert.equal(fixture.select.getAttribute('data-combobox-enhanced'), 'true');
  assert.equal(fixture.select.getAttribute('tabindex'), '-1');
  assert.equal(fixture.select.getAttribute('aria-hidden'), 'true', 'sem controle duplicado para AT');
  assert.equal(control.input.getAttribute('role'), 'combobox');
  assert.equal(control.input.getAttribute('aria-expanded'), 'false');
  assert.equal(control.input.getAttribute('aria-controls'), control.list.id);
  assert.equal(control.input.getAttribute('aria-autocomplete'), 'list');
  assert.equal(control.input.getAttribute('aria-labelledby'), 'exam-type-select-label');
  assert.equal(control.input.getAttribute('aria-describedby'), 'exam-type-guidance');
  assert.equal(control.list.getAttribute('role'), 'listbox');
  assert.equal(control.input.value, '', 'sem seleção inicial');

  const ids = rowsOf(control.list).map((row) => row.id);
  assert.deepEqual(ids, [
    'exam-type-select-option-eda',
    'exam-type-select-option-colonoscopy',
    'exam-type-select-option-eda-colonoscopy',
    'exam-type-select-option-echoendoscopy',
    'exam-type-select-option-cpre',
  ], 'ids estáveis por valor canônico, sem o placeholder');

  const disabled = rowByValue(control.list, 'cpre');
  assert.equal(disabled.getAttribute('aria-disabled'), 'true');
  assert.equal(disabled.classList.contains('procedure-combobox__option--disabled'), true);
});

test('enhance é idempotente (re-render/dupla carga não duplica o controle)', () => {
  const combobox = loadCombobox();
  const document = createFakeDocument();
  const fixture = buildFixture(document);
  combobox.enhance(fixture.select, { document: document });
  const wrapper = fixture.select.parentNode;
  const second = combobox.enhance(fixture.select, { document: document });

  assert.equal(second, null);
  assert.equal(fixture.root.children.length, 1, 'wrapper único em volta do select');
  assert.equal(wrapper.children.filter((child) => child.tagName === 'INPUT').length, 1);
  assert.equal(wrapper.children.filter((child) => child.tagName === 'UL').length, 1);
});

// ── Teclado (R2) ──────────────────────────────────────────────────────────

test('setas abrem a lista, pulam opções desabilitadas e Enter confirma a seleção', () => {
  const combobox = loadCombobox();
  const document = createFakeDocument();
  const fixture = buildFixture(document);
  const control = combobox.enhance(fixture.select, { document: document });
  let changes = 0;
  fixture.select.addEventListener('change', () => {
    changes += 1;
  });

  fireKey(control.input, 'ArrowDown');
  assert.equal(control.input.getAttribute('aria-expanded'), 'true');
  assert.equal(control.input.getAttribute('aria-activedescendant'), 'exam-type-select-option-eda');

  fireKey(control.input, 'ArrowDown');
  assert.equal(control.input.getAttribute('aria-activedescendant'), 'exam-type-select-option-colonoscopy');

  fireKey(control.input, 'ArrowDown');
  assert.equal(control.input.getAttribute('aria-activedescendant'), 'exam-type-select-option-eda-colonoscopy');

  fireKey(control.input, 'ArrowDown');
  assert.equal(
    control.input.getAttribute('aria-activedescendant'),
    'exam-type-select-option-eda',
    'opções desabilitadas (ecoendoscopia/CPRE) não são navegáveis',
  );

  fireKey(control.input, 'ArrowUp');
  assert.equal(control.input.getAttribute('aria-activedescendant'), 'exam-type-select-option-eda-colonoscopy');

  fireKey(control.input, 'Enter');
  assert.equal(fixture.select.value, 'eda_colonoscopy', 'código canônico no controle submetido');
  assert.equal(control.input.value, 'EDA + Colonoscopia');
  assert.equal(control.input.getAttribute('aria-expanded'), 'false');
  assert.equal(control.input.getAttribute('aria-activedescendant'), null);
  assert.equal(changes, 1, 'mudança propagada para o select (upload.js)');
});

test('Home e End apontam para os extremos navegáveis', () => {
  const combobox = loadCombobox();
  const document = createFakeDocument();
  const fixture = buildFixture(document);
  const control = combobox.enhance(fixture.select, { document: document });

  fireKey(control.input, 'ArrowDown');
  fireKey(control.input, 'End');
  assert.equal(control.input.getAttribute('aria-activedescendant'), 'exam-type-select-option-eda-colonoscopy');

  fireKey(control.input, 'Home');
  assert.equal(control.input.getAttribute('aria-activedescendant'), 'exam-type-select-option-eda');
});

test('Escape e Tab fecham a lista sem alterar a seleção confirmada', () => {
  const combobox = loadCombobox();
  const document = createFakeDocument();
  const fixture = buildFixture(document);
  const control = combobox.enhance(fixture.select, { document: document });

  fireKey(control.input, 'ArrowDown');
  const escape = fireKey(control.input, 'Escape');
  assert.equal(escape.defaultPrevented, true);
  assert.equal(control.input.getAttribute('aria-expanded'), 'false');
  assert.equal(control.input.getAttribute('aria-activedescendant'), null);
  assert.equal(fixture.select.value, '', 'Escape não altera o valor submetido');

  fireKey(control.input, 'ArrowDown');
  fireKey(control.input, 'Tab');
  assert.equal(control.input.getAttribute('aria-expanded'), 'false');
});

// ── Busca e ausência de valor livre (R3) ─────────────────────────────────

test('a busca filtra por label/alias sem alterar o valor submetido', () => {
  const combobox = loadCombobox();
  const document = createFakeDocument();
  const fixture = buildFixture(document);
  const control = combobox.enhance(fixture.select, { document: document });

  type(control.input, 'colonoscopia');
  assert.equal(control.input.getAttribute('aria-expanded'), 'true');
  assert.deepEqual(
    visibleRows(control.list).map((row) => row.getAttribute('data-value')),
    ['colonoscopy', 'eda_colonoscopy'],
  );
  assert.equal(fixture.select.value, '', 'texto digitado não vira valor');

  type(control.input, 'capsula');
  assert.deepEqual(visibleRows(control.list), [], 'sem correspondência e sem alias inventado');
  assert.equal(control.empty.hidden, false);
  assert.match(control.empty.textContent, /Nenhum procedimento/);
  assert.equal(control.input.getAttribute('aria-activedescendant'), null);

  fireKey(control.input, 'Enter');
  assert.equal(fixture.select.value, '', 'Enter sem opção ativa não submete valor livre');

  type(control.input, 'CÁPSULA');
  assert.deepEqual(visibleRows(control.list), [], 'busca normalizada (caixa/diacríticos)');

  type(control.input, 'eda');
  assert.equal(control.empty.hidden, true);
  assert.equal(control.input.getAttribute('aria-describedby'), 'exam-type-guidance');
});

test('clique em opção confirma o valor; clique fora apenas fecha', () => {
  const combobox = loadCombobox();
  const document = createFakeDocument();
  const fixture = buildFixture(document);
  const control = combobox.enhance(fixture.select, { document: document });
  let changes = 0;
  fixture.select.addEventListener('change', () => {
    changes += 1;
  });

  control.input.dispatchEvent(new FakeEvent('click'));
  assert.equal(control.input.getAttribute('aria-expanded'), 'true');

  rowByValue(control.list, 'eda').dispatchEvent(new FakeEvent('click'));
  assert.equal(fixture.select.value, 'eda');
  assert.equal(changes, 1);
  assert.equal(control.input.getAttribute('aria-expanded'), 'false');

  control.input.dispatchEvent(new FakeEvent('click'));
  assert.equal(control.input.getAttribute('aria-expanded'), 'true');
  const outside = document.createElement('div');
  const outsideClick = new FakeEvent('click');
  outsideClick.target = outside;
  document.dispatchEvent(outsideClick);
  assert.equal(control.input.getAttribute('aria-expanded'), 'false');
  assert.equal(fixture.select.value, 'eda', 'clique fora não altera o valor');
  assert.equal(changes, 1);
});

test('mudança externa no select (re-render) reflete o label no combobox', () => {
  const combobox = loadCombobox();
  const document = createFakeDocument();
  const fixture = buildFixture(document);
  const control = combobox.enhance(fixture.select, { document: document });

  fixture.select.value = 'eda';
  fixture.select.dispatchEvent(new FakeEvent('change'));
  assert.equal(control.input.value, 'EDA');

  fixture.select.value = '';
  fixture.select.dispatchEvent(new FakeEvent('change'));
  assert.equal(control.input.value, '');
});
