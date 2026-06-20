/* Password visibility toggle — Vanilla JS
   Applies to elements with .toggle-password button and data-target attribute.
   Used on login, password reset confirm, and password change pages.

   Icons are inline SVG (Bootstrap Icons "eye" / "eye-slash", MIT) so they are
   crisp vectors and consistent across platforms — no emoji and no icon-font
   dependency. The JS renders the icon matching each field's initial type, then
   swaps it on click.
*/
(function () {
  'use strict';

  var EYE_SVG =
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true">' +
    '<path d="M16 8s-3-5.5-8-5.5S0 8 0 8s3 5.5 8 5.5S16 8 16 8M1.5 8a6.5 6.5 0 1 1 13 0 6.5 6.5 0 0 1-13 0M8 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6"/></svg>';

  var EYE_SLASH_SVG =
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true">' +
    '<path d="M13.359 11.238C15.06 9.72 16 8 16 8s-3-5.5-8-5.5a7.028 7.028 0 0 0-2.79.588l.77.771A5.944 5.944 0 0 1 8 3.5c2.12 0 3.879 1.168 5.168 2.457A13.134 13.134 0 0 1 14.828 8c-.058.087-.122.183-.195.288-.335.48-.83 1.12-1.465 1.755-.165.165-.337.328-.517.486l.708.709z"/>' +
    '<path d="M11.297 9.176a3.5 3.5 0 0 0-4.474-4.474l.823.823a2.5 2.5 0 0 1 2.829 2.829l.823.822zm-2.943 1.299.822.822a3.5 3.5 0 0 1-4.474-4.474l.823.823a2.5 2.5 0 0 0 2.829 2.829z"/>' +
    '<path d="M3.35 5.47c-.18.16-.353.322-.518.487A13.134 13.134 0 0 0 1.172 8l.195.288c.335.48.83 1.12 1.465 1.755.165.165.337.328.517.486L5.49 10.51l-.708-.709a12.6 12.6 0 0 1-.517-.486 11.69 11.69 0 0 1-.81-.87C3.06 9.05 2.5 8.117 2.5 8c0-.117.56-1.05 1.345-2.04l.708-.709.797.797z"/>' +
    '<path d="M2.34 3.235a.5.5 0 0 1 .708-.708l11 11a.5.5 0 0 1-.708.708l-11-11z"/></svg>';

  function iconForType(type) {
    return type === 'password' ? EYE_SVG : EYE_SLASH_SVG;
  }

  function syncIcon(toggle) {
    var targetId = toggle.getAttribute('data-target');
    if (!targetId) return;
    var input = document.getElementById(targetId);
    if (!input) return;
    var icon = toggle.querySelector('.toggle-icon');
    if (icon) {
      icon.innerHTML = iconForType(input.getAttribute('type'));
    }
  }

  function initAll() {
    var toggles = document.querySelectorAll('.toggle-password');
    for (var i = 0; i < toggles.length; i++) {
      syncIcon(toggles[i]);
    }
  }

  // Render the correct initial icon for each toggle (the script loads at the
  // end of <body>, but guard readyState for safety).
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  document.addEventListener('click', function (e) {
    var toggle = e.target.closest('.toggle-password');
    if (!toggle) return;

    var targetId = toggle.getAttribute('data-target');
    if (!targetId) return;

    var input = document.getElementById(targetId);
    if (!input) return;

    var isPassword = input.getAttribute('type') === 'password';
    input.setAttribute('type', isPassword ? 'text' : 'password');

    var icon = toggle.querySelector('.toggle-icon');
    if (icon) {
      icon.innerHTML = iconForType(input.getAttribute('type'));
    }

    toggle.setAttribute('aria-label', isPassword ? 'Ocultar senha' : 'Mostrar senha');
  });
})();
