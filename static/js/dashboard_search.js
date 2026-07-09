/**
 * Busca dinâmica progressiva para o dashboard.
 *
 * Melhoria progressiva: sem JavaScript, o formulário tradicional continua
 * funcionando. Com JavaScript ativo, a lista de casos é atualizada via
 * fetch SSR parcial (X-ATS-Partial: case-list) sem recarregar a página.
 *
 * Requisitos:
 * - Debounce de 400 ms entre a digitação e a requisição.
 * - Mínimo de 3 caracteres para disparar busca.
 * - Campo vazio também dispara fetch para limpar a busca.
 * - AbortController para cancelar respostas antigas (evita race condition).
 * - Preserva outros filtros (status, date_from, date_to, attention).
 * - Atualiza history.replaceState para refletir search na URL.
 */

(function () {
  'use strict';

  var DASHBOARD_SEARCH_DEBOUNCE_MS = 400;
  var DASHBOARD_SEARCH_MIN_CHARS = 3;

  var container = document.querySelector('[data-dashboard-search-target]');
  if (!container) {
    // Não estamos no dashboard, sair silenciosamente
    return;
  }

  var searchInput = document.getElementById('search');
  if (!searchInput) {
    // Dashboard sem campo de busca? Sair silenciosamente.
    return;
  }

  // Controle de requisições
  var currentController = null;
  var debounceTimer = null;

  /**
   * Retorna os parâmetros atuais do formulário de filtros como URLSearchParams.
   * Preserva status, date_from, date_to, attention e metrics_date.
   */
  function getFilterParams() {
    var params = new URLSearchParams();
    var statusSelect = document.querySelector('select[name="status"]');
    var dateFromInput = document.querySelector('input[name="date_from"]');
    var dateToInput = document.querySelector('input[name="date_to"]');
    var attentionLink = document.querySelector('a[href*="attention=1"]');
    var metricsDateInput = document.querySelector('input[name="metrics_date"]');

    if (statusSelect && statusSelect.value) {
      params.set('status', statusSelect.value);
    }
    if (dateFromInput && dateFromInput.value) {
      params.set('date_from', dateFromInput.value);
    }
    if (dateToInput && dateToInput.value) {
      params.set('date_to', dateToInput.value);
    }
    // Atenção ativa? Verifica se o link tem btn-warning (ativo)
    if (attentionLink && attentionLink.classList.contains('btn-warning')) {
      params.set('attention', '1');
    }
    if (metricsDateInput && metricsDateInput.value) {
      params.set('metrics_date', metricsDateInput.value);
    }

    return params;
  }

  /**
   * Atualiza a URL do navegador com o termo de busca atual.
   */
  function updateUrl(term) {
    try {
      var url = new URL(window.location.href);
      if (term) {
        url.searchParams.set('search', term);
      } else {
        url.searchParams.delete('search');
      }
      window.history.replaceState({}, '', url.toString());
    } catch (_e) {
      // Falha silenciosa ao manipular URL
    }
  }

  /**
   * Cancela qualquer requisição anterior em andamento.
   */
  function cancelPreviousRequest() {
    if (currentController) {
      currentController.abort();
      currentController = null;
    }
  }

  /**
   * Dispara o fetch SSR parcial para atualizar a lista de casos.
   */
  function fetchCaseList(searchTerm) {
    // Cancela requisição anterior para evitar resposta fora de ordem
    cancelPreviousRequest();

    // Cria novo AbortController para esta requisição
    currentController = new AbortController();
    var signal = currentController.signal;

    // Monta a URL com search + filtros existentes
    var params = getFilterParams();
    if (searchTerm) {
      params.set('search', searchTerm);
    }

    var url = '/dashboard/?' + params.toString();

    fetch(url, {
      headers: {
        'X-ATS-Partial': 'case-list'
      },
      signal: signal
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Erro HTTP ' + response.status);
        }
        return response.text();
      })
      .then(function (html) {
        // Verifica se esta requisição não foi cancelada
        if (signal.aborted) {
          return;
        }
        container.innerHTML = html;
        currentController = null;
      })
      .catch(function (err) {
        if (err.name === 'AbortError') {
          // Requisição cancelada intencionalmente, ignorar
          return;
        }
        // Erro silencioso: o submit tradicional continua funcionando
        currentController = null;
      });
  }

  /**
   * Handler principal do input de busca.
   */
  function onSearchInput() {
    var term = searchInput.value.trim();
    var termLength = term.length;

    // Limpa timer de debounce anterior
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }

    // Campo vazio: atualiza URL e dispara fetch imediato para limpar
    if (termLength === 0) {
      updateUrl('');
      cancelPreviousRequest();
      fetchCaseList('');
      return;
    }

    // 1 ou 2 caracteres: não dispara fetch (aguarda mais digitação)
    if (termLength < DASHBOARD_SEARCH_MIN_CHARS) {
      cancelPreviousRequest();
      updateUrl(term);
      return;
    }

    // 3+ caracteres: aguarda debounce e dispara fetch
    updateUrl(term);
    debounceTimer = setTimeout(function () {
      fetchCaseList(term);
    }, DASHBOARD_SEARCH_DEBOUNCE_MS);
  }

  // Registra evento de input no campo de busca
  searchInput.addEventListener('input', onSearchInput);

})();
