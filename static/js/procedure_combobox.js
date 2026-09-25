/**
 * Combobox pesquisável de procedimento — progressive enhancement sobre um
 * `<select>` canônico (design D9). Vanilla JS, sem dependências.
 *
 * O `<select>` marcado com `data-procedure-combobox` permanece o único valor
 * submetido: o combobox apenas espelha nele a opção escolhida e nunca aceita
 * texto livre. Sem JavaScript o select segue visível e funcional.
 *
 * Estrutura criada ao lado do select: `<input role="combobox">` com estado
 * ARIA, `<ul role="listbox">` com um `<li role="option">` por opção publicada
 * (id estável derivado do valor canônico) e mensagem textual de "sem
 * resultado". Estilos em `.procedure-combobox*` (`static/css/app.css`).
 *
 * A API pública (`window.ProcedureCombobox`) é consumida pelo auto-init da
 * página e pelo teste complementar
 * `static/js/tests/procedure_combobox.test.js`.
 */
(function (global) {
  'use strict';

  // Marcas de diacrítico separadas por String.normalize('NFD') (U+0300–U+036F).
  var COMBINING_MARKS = /[\u0300-\u036f]/g;

  /** Normaliza caixa e diacríticos para comparação de busca. */
  function normalizeSearch(value) {
    return String(value == null ? '' : value)
      .normalize('NFD')
      .replace(COMBINING_MARKS, '')
      .toLowerCase()
      .trim();
  }

  /** Texto pesquisável de uma opção: label + `data-search-aliases`. */
  function searchText(option) {
    return normalizeSearch(String(option.text || '') + ' ' + String(option.aliases || ''));
  }

  /**
   * Busca vazia mantém todas as opções; qualquer termo precisa corresponder ao
   * label canônico ou a um alias aprovado (nunca cria valor novo).
   */
  function matchesQuery(option, query) {
    var normalized = normalizeSearch(query);
    if (normalized === '') {
      return true;
    }
    return searchText(option).indexOf(normalized) !== -1;
  }

  /**
   * Índice da próxima opção ativa a partir de `rows` (objetos com `navigable`).
   * `delta` +1/-1 percorre circularmente e ignora opções desabilitadas; -1
   * quando nada é navegável.
   */
  function nextActiveIndex(rows, activeIndex, delta) {
    var navigable = [];
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].navigable) {
        navigable.push(i);
      }
    }
    if (navigable.length === 0) {
      return -1;
    }
    var position = navigable.indexOf(activeIndex);
    if (activeIndex < 0 || position === -1) {
      return delta > 0 ? navigable[0] : navigable[navigable.length - 1];
    }
    position += delta;
    if (position < 0) {
      position = navigable.length - 1;
    } else if (position >= navigable.length) {
      position = 0;
    }
    return navigable[position];
  }

  /** Id estável de uma opção derivado do valor canônico. */
  function optionRowId(baseId, value) {
    return baseId + '-option-' + String(value).replace(/[^a-z0-9]+/gi, '-').toLowerCase();
  }

  /** Um nó está contido em `ancestor` (para o fechamento ao clicar fora). */
  function containsNode(ancestor, node) {
    var current = node;
    while (current) {
      if (current === ancestor) {
        return true;
      }
      current = current.parentNode;
    }
    return false;
  }

  /** Dispara `change` no select para que o restante da página reaja. */
  function dispatchChange(element) {
    var EventConstructor = global.Event;
    if (typeof EventConstructor !== 'function') {
      return;
    }
    element.dispatchEvent(new EventConstructor('change', { bubbles: true }));
  }

  /**
   * Aprimora um `<select data-procedure-combobox>` em combobox pesquisável.
   * Idempotente (re-render/dupla carga não duplica o controle). Retorna
   * `{input, list, empty}` ou `null` quando não há o que aprimorar.
   */
  function enhance(select, settings) {
    if (!select || select.getAttribute('data-combobox-enhanced') === 'true') {
      return null;
    }
    var document = (settings && settings.document) || global.document;
    if (!document || !select.parentNode || !select.options) {
      return null;
    }

    var baseId = select.id || select.getAttribute('name') || 'procedure-combobox';
    var describedBy = select.getAttribute('aria-describedby');
    var listId = baseId + '-list';
    var emptyId = baseId + '-empty';

    select.classList.add('procedure-combobox__select');
    select.setAttribute('data-combobox-enhanced', 'true');
    // O select continua sendo o valor submetido, mas sai da árvore de
    // acessibilidade e da ordem de foco: o combobox expõe o mesmo estado e as
    // mesmas opções (sem controle duplicado para tecnologia assistiva).
    select.setAttribute('tabindex', '-1');
    select.setAttribute('aria-hidden', 'true');

    var wrapper = document.createElement('div');
    wrapper.setAttribute('class', 'procedure-combobox procedure-combobox--enhanced');
    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);

    var input = document.createElement('input');
    input.setAttribute('type', 'text');
    input.setAttribute('id', baseId + '-combobox');
    input.setAttribute('class', 'form-control procedure-combobox__input');
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-controls', listId);
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('autocomplete', 'off');
    if (describedBy) {
      input.setAttribute('aria-describedby', describedBy);
    }
    var labelledBy = select.getAttribute('aria-labelledby');
    if (labelledBy) {
      input.setAttribute('aria-labelledby', labelledBy);
    }
    if (select.getAttribute('aria-invalid')) {
      input.setAttribute('aria-invalid', 'true');
    }
    wrapper.appendChild(input);

    var list = document.createElement('ul');
    list.setAttribute('id', listId);
    list.setAttribute('class', 'procedure-combobox__list');
    list.setAttribute('role', 'listbox');
    list.hidden = true;
    wrapper.appendChild(list);

    var empty = document.createElement('p');
    empty.setAttribute('id', emptyId);
    empty.setAttribute('class', 'procedure-combobox__empty');
    empty.setAttribute('role', 'status');
    empty.hidden = true;
    wrapper.appendChild(empty);

    // Uma row por opção publicada; o placeholder (valor vazio) fica fora.
    var rows = [];
    for (var i = 0; i < select.options.length; i++) {
      var option = select.options[i];
      if (option.value === '') {
        continue;
      }
      var row = document.createElement('li');
      row.setAttribute('id', optionRowId(baseId, option.value));
      row.setAttribute('role', 'option');
      row.setAttribute('data-value', option.value);
      row.setAttribute('class', 'procedure-combobox__option');
      row.textContent = option.textContent;
      if (option.disabled) {
        row.setAttribute('aria-disabled', 'true');
        row.classList.add('procedure-combobox__option--disabled');
      }
      list.appendChild(row);
      rows.push({
        element: row,
        value: option.value,
        disabled: option.disabled === true,
        text: option.textContent,
        aliases: option.getAttribute('data-search-aliases') || '',
        navigable: false
      });
    }

    var activeIndex = -1;

    function isOpen() {
      return input.getAttribute('aria-expanded') === 'true';
    }

    function refreshNavigable() {
      for (var r = 0; r < rows.length; r++) {
        rows[r].navigable = rows[r].element.hidden !== true && !rows[r].disabled;
      }
    }

    function setActive(index) {
      activeIndex = index;
      for (var r = 0; r < rows.length; r++) {
        if (r === index) {
          rows[r].element.classList.add('procedure-combobox__option--active');
        } else {
          rows[r].element.classList.remove('procedure-combobox__option--active');
        }
      }
      if (index < 0) {
        input.removeAttribute('aria-activedescendant');
      } else {
        input.setAttribute('aria-activedescendant', rows[index].element.id);
      }
    }

    function setEmptyState(hasResults) {
      empty.hidden = hasResults;
      empty.textContent = hasResults ? '' : 'Nenhum procedimento encontrado para "' + input.value + '".';
      var ids = describedBy ? [describedBy] : [];
      if (!hasResults) {
        ids.push(emptyId);
      }
      if (ids.length) {
        input.setAttribute('aria-describedby', ids.join(' '));
      } else {
        input.removeAttribute('aria-describedby');
      }
    }

    function open() {
      if (isOpen()) {
        return;
      }
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      refreshNavigable();
      setActive(nextActiveIndex(rows, -1, 1));
    }

    function close() {
      if (!isOpen()) {
        return;
      }
      list.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      setActive(-1);
    }

    function filter(query) {
      for (var r = 0; r < rows.length; r++) {
        rows[r].element.hidden = !matchesQuery(rows[r], query);
      }
      refreshNavigable();
      var hasResults = false;
      for (var n = 0; n < rows.length; n++) {
        if (rows[n].navigable) {
          hasResults = true;
          break;
        }
      }
      setEmptyState(hasResults);
      setActive(isOpen() ? nextActiveIndex(rows, -1, 1) : -1);
    }

    function syncFromSelect() {
      var selected = null;
      for (var r = 0; r < rows.length; r++) {
        if (rows[r].value === select.value) {
          selected = rows[r];
        }
      }
      input.value = selected ? selected.text : '';
    }

    // Só a seleção de uma opção existente escreve no select (nunca texto livre).
    function commit(row) {
      if (!row || row.disabled) {
        return;
      }
      select.value = row.value;
      syncFromSelect();
      close();
      dispatchChange(select);
    }

    function moveActive(delta) {
      var index = nextActiveIndex(rows, activeIndex, delta);
      if (index !== -1) {
        setActive(index);
      }
    }

    function onKeyDown(event) {
      var key = event.key;
      if (key === 'ArrowDown' || key === 'ArrowUp') {
        event.preventDefault();
        if (isOpen()) {
          moveActive(key === 'ArrowDown' ? 1 : -1);
        } else {
          open();
        }
        return;
      }
      if (key === 'Home' || key === 'End') {
        if (!isOpen()) {
          return;
        }
        event.preventDefault();
        setActive(nextActiveIndex(rows, -1, key === 'Home' ? 1 : -1));
        return;
      }
      if (key === 'Enter') {
        if (!isOpen()) {
          return;
        }
        event.preventDefault();
        commit(activeIndex >= 0 ? rows[activeIndex] : null);
        return;
      }
      if (key === 'Escape') {
        if (!isOpen()) {
          return;
        }
        event.preventDefault();
        close();
        return;
      }
      if (key === 'Tab') {
        close();
      }
    }

    function bindRow(row) {
      row.element.addEventListener('click', function () {
        commit(row);
      });
    }
    for (var b = 0; b < rows.length; b++) {
      bindRow(rows[b]);
    }

    input.addEventListener('click', open);
    input.addEventListener('input', function () {
      filter(input.value);
      open();
    });
    input.addEventListener('keydown', onKeyDown);
    select.addEventListener('change', syncFromSelect);
    document.addEventListener('click', function (event) {
      if (isOpen() && !containsNode(wrapper, event.target)) {
        close();
      }
    });

    syncFromSelect();
    return { input: input, list: list, empty: empty };
  }

  /** Aprimora todos os selects publicados em `document` (auto-init da página). */
  function enhanceAll(document) {
    if (!document || typeof document.querySelectorAll !== 'function') {
      return;
    }
    var selects = document.querySelectorAll('select[data-procedure-combobox]');
    for (var i = 0; i < selects.length; i++) {
      enhance(selects[i], { document: document });
    }
  }

  global.ProcedureCombobox = {
    normalizeSearch: normalizeSearch,
    matchesQuery: matchesQuery,
    nextActiveIndex: nextActiveIndex,
    enhance: enhance,
    enhanceAll: enhanceAll
  };

  if (global.document && typeof global.document.addEventListener === 'function') {
    if (global.document.readyState === 'loading') {
      global.document.addEventListener('DOMContentLoaded', function () {
        enhanceAll(global.document);
      });
    } else {
      enhanceAll(global.document);
    }
  }
})(typeof window === 'undefined' ? this : window);
