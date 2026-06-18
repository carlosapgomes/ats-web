/* Password visibility toggle — Vanilla JS
   Applies to elements with .toggle-password button and data-target attribute.
   Used only on login and password reset confirm pages.
*/
(function () {
  'use strict';

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
      icon.textContent = isPassword ? '🙈' : '👁';
    }

    toggle.setAttribute('aria-label', isPassword ? 'Ocultar senha' : 'Mostrar senha');
  });
})();
