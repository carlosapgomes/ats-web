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
})();
