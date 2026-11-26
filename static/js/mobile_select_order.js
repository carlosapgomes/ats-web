/**
 * Ordem inversa das opções de um `<select>` em tela mobile — progressive
 * enhancement sobre o picker nativo (task
 * `tasks/quick-ui-admission-flow-mobile-order.md`). Vanilla JS, sem dependências.
 *
 * No desktop o dropdown abre logo abaixo do cursor: a primeira opção é a mais
 * próxima. No celular o picker é uma lista vertical centralizada (Android) ou
 * um menu ancorado que abre ACIMA do select quando ele está na metade inferior
 * da tela (iOS 16+, Safari e Chrome/WebKit): a primeira opção fica no ponto
 * mais distante do dedo. Por isso, só no mobile, as opções reais são listadas
 * em ordem inversa à do HTML.
 *
 * Contrato:
 * - somente selects marcados com `data-mobile-reverse-options`;
 * - a primeira opção (placeholder) permanece em primeiro;
 * - "mobile" = `matchMedia('(max-width: 767.98px)')` (mesmo corte de `md`/`d-md-none`);
 * - ao entrar/sair do corte (rotação, redimensionamento) a ordem é reaplicada
 *   ou restaurada a partir da ordem original capturada uma única vez;
 * - os nós são movidos (não recriados), preservando a opção `selected` — o
 *   valor submetido não muda;
 * - sem JavaScript ou sem `matchMedia`, o select segue na ordem do SSR.
 *
 * API pública (`window.MobileSelectOrder`) consumida pelo auto-init da página
 * e pelo teste `static/js/tests/mobile_select_order.test.js`.
 */
(function (global) {
  'use strict';

  var MOBILE_QUERY = '(max-width: 767.98px)';
  var MARKER_SELECTOR = 'select[data-mobile-reverse-options]';

  /** Copia os `<option>` atuais (a coleção ao vivo muda conforme os nós são movidos). */
  function snapshotOptions(select) {
    var options = [];
    for (var i = 0; i < select.options.length; i++) {
      options.push(select.options[i]);
    }
    return options;
  }

  /**
   * Reordena `select` conforme `mediaQueryList.matches` e passa a acompanhar o
   * corte. Retorna o aplicador (`apply()`) para reaplicação manual/testes.
   */
  function enhance(select, mediaQueryList) {
    var original = snapshotOptions(select); // original[0] = placeholder, fica em primeiro
    var rest = original.slice(1);

    function apply() {
      var ordered = mediaQueryList.matches ? rest.slice().reverse() : rest;
      for (var i = 0; i < ordered.length; i++) {
        select.appendChild(ordered[i]);
      }
    }

    apply();
    if (typeof mediaQueryList.addEventListener === 'function') {
      mediaQueryList.addEventListener('change', apply);
    } else if (typeof mediaQueryList.addListener === 'function') {
      mediaQueryList.addListener(apply); // Safari < 14
    }
    return apply;
  }

  /** Aplica em todos os selects marcados de `document` (auto-init da página). */
  function enhanceAll(document) {
    if (!document || typeof document.querySelectorAll !== 'function' || typeof global.matchMedia !== 'function') {
      return [];
    }
    var mediaQueryList = global.matchMedia(MOBILE_QUERY);
    var selects = document.querySelectorAll(MARKER_SELECTOR);
    var appliers = [];
    for (var i = 0; i < selects.length; i++) {
      appliers.push(enhance(selects[i], mediaQueryList));
    }
    return appliers;
  }

  global.MobileSelectOrder = {
    MOBILE_QUERY: MOBILE_QUERY,
    MARKER_SELECTOR: MARKER_SELECTOR,
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
