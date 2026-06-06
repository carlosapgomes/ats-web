/* ATS Web — Post-Schedule Issue Form: toggle sections by action */

(function () {
  var actionRadios = document.querySelectorAll('input[name="psi_action"]');
  if (!actionRadios.length) return;

  var sections = {
    cancel: document.getElementById('psi-cancel-deny-section'),
    deny: document.getElementById('psi-cancel-deny-section'),
    reschedule: document.getElementById('psi-reschedule-section'),
    maintain: document.getElementById('psi-maintain-section'),
  };

  function toggleSections(value) {
    Object.entries(sections).forEach(function (_ref) {
      var action = _ref[0];
      var el = _ref[1];
      if (el) {
        el.style.display = action === value ? 'block' : 'none';
      }
    });
    // cancel and deny both use the cancel-deny section
    if (value === 'cancel' || value === 'deny') {
      var cdSection = document.getElementById('psi-cancel-deny-section');
      if (cdSection) cdSection.style.display = 'block';
    }
  }

  for (var i = 0; i < actionRadios.length; i++) {
    actionRadios[i].addEventListener('change', function () {
      toggleSections(this.value);
    });
  }

  // Initialize on page load
  var checked = document.querySelector('input[name="psi_action"]:checked');
  if (checked) {
    toggleSections(checked.value);
  }

  // ── Fix: disable hidden psi_response_message fields before submit ──
  // The template has three <textarea name="psi_response_message"> (one per section).
  // When the form is submitted, the browser sends ALL of them. Django uses the
  // LAST value, which is always the empty "maintain" section field, overwriting
  // whatever the user typed in the visible section.
  // Solution: disable hidden textareas so they are excluded from the POST data.
  var psiForm = document.getElementById('psi-form');
  if (psiForm) {
    psiForm.addEventListener('submit', function () {
      var allMessages = document.querySelectorAll('textarea[name="psi_response_message"]');
      for (var j = 0; j < allMessages.length; j++) {
        var textarea = allMessages[j];
        var section = textarea.closest('.psi-section');
        if (section && section.style.display === 'none') {
          textarea.disabled = true;
        }
      }
    });
  }
})();
