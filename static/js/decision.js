/* ATS Web — Decision Form JavaScript */

(function () {
    var acceptRadio = document.getElementById('decision-accept');
    var denyRadio = document.getElementById('decision-deny');
    var acceptSection = document.getElementById('accept-section');
    var denySection = document.getElementById('deny-section');
    var supportFlag = document.getElementById('support-flag');
    var admissionFlow = document.getElementById('admission-flow');
    var denyReason = document.getElementById('deny-reason');
    var form = document.getElementById('decision-form');
    var confirmModalEl = document.getElementById('confirm-modal');
    var confirmBody = document.getElementById('confirm-body');
    var btnConfirmFinal = document.getElementById('btn-confirm-final');
    var btnSubmit = document.getElementById('btn-submit');

    if (!form) return;

    var confirmModal = null;
    if (confirmModalEl) {
        confirmModal = new bootstrap.Modal(confirmModalEl);
    }

    function toggleSections() {
        if (acceptRadio && acceptRadio.checked) {
            acceptSection.classList.add('active');
            denySection.classList.remove('active');
            if (supportFlag) supportFlag.required = true;
            if (admissionFlow) admissionFlow.required = true;
            if (denyReason) denyReason.required = false;
        } else if (denyRadio && denyRadio.checked) {
            denySection.classList.add('active');
            acceptSection.classList.remove('active');
            if (supportFlag) supportFlag.required = false;
            if (admissionFlow) admissionFlow.required = false;
            if (denyReason) denyReason.required = true;
        } else {
            acceptSection.classList.remove('active');
            denySection.classList.remove('active');
        }
    }

    // Initialize state on page load
    toggleSections();

    if (acceptRadio) acceptRadio.addEventListener('change', toggleSections);
    if (denyRadio) denyRadio.addEventListener('change', toggleSections);

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // Clear invalid states on input
    if (supportFlag) supportFlag.addEventListener('change', function () { supportFlag.classList.remove('is-invalid'); });
    if (admissionFlow) admissionFlow.addEventListener('change', function () { admissionFlow.classList.remove('is-invalid'); });
    if (denyReason) denyReason.addEventListener('input', function () { denyReason.classList.remove('is-invalid'); });

    var finalSubmitConfirmed = false;

    if (form && confirmModal) {
        form.addEventListener('submit', function (e) {
            if (finalSubmitConfirmed) return;

            e.preventDefault();

            // Validate decision selected
            if (!acceptRadio.checked && !denyRadio.checked) {
                var decisionError = document.getElementById('decision-error');
                if (decisionError) decisionError.style.display = 'block';
                return;
            }
            var decisionError = document.getElementById('decision-error');
            if (decisionError) decisionError.style.display = 'none';

            var decision = acceptRadio.checked ? 'accept' : 'deny';
            var supportText = supportFlag && supportFlag.selectedIndex >= 0
                ? supportFlag.options[supportFlag.selectedIndex].text : '';
            var flowText = admissionFlow && admissionFlow.selectedIndex >= 0
                ? admissionFlow.options[admissionFlow.selectedIndex].text : '';
            var reason = denyReason ? denyReason.value.trim() : '';

            if (decision === 'accept') {
                if (!supportFlag || !supportFlag.value || !admissionFlow || !admissionFlow.value) {
                    if (supportFlag && !supportFlag.value) supportFlag.classList.add('is-invalid');
                    if (admissionFlow && !admissionFlow.value) admissionFlow.classList.add('is-invalid');
                    return;
                }
                confirmBody.innerHTML =
                    '<div class="text-center mb-3"><span style="font-size:3rem;">&#10003;</span></div>' +
                    '<p class="text-center mb-1"><strong>ACEITAR</strong> &mdash; ' + escapeHtml(supportText) + ' &middot; ' + escapeHtml(flowText) + '</p>' +
                    '<div class="alert alert-info small mb-0 mt-3">O caso será encaminhado automaticamente para agendamento.</div>';
            } else {
                if (!reason) {
                    if (denyReason) denyReason.classList.add('is-invalid');
                    return;
                }
                confirmBody.innerHTML =
                    '<div class="text-center mb-3"><span style="font-size:3rem;">&#10007;</span></div>' +
                    '<p class="text-center mb-1"><strong>NEGAR</strong></p>' +
                    '<div class="mt-3"><strong>Motivo:</strong> ' + escapeHtml(reason) + '</div>' +
                    '<div class="alert alert-warning small mb-0 mt-3">O resultado será comunicado à recepção.</div>';
            }

            confirmModal.show();
        });
    }

    if (btnConfirmFinal) {
        btnConfirmFinal.addEventListener('click', function () {
            if (confirmModal) confirmModal.hide();

            // Disable button and give visual feedback
            if (btnSubmit) {
                btnSubmit.textContent = '✓ Decisão Enviada';
                btnSubmit.classList.remove('btn-hospital');
                btnSubmit.classList.add('btn-success');
                btnSubmit.disabled = true;
            }

            // Submit the form through the browser's normal submit path.
            // Avoid HTMLFormElement.submit(): it bypasses the submit event path
            // and was observed in dev to produce an unauthenticated POST on
            // the medical decision form. requestSubmit() preserves the normal
            // form submission semantics while the confirmation guard above
            // prevents reopening the modal.
            finalSubmitConfirmed = true;
            setTimeout(function () {
                if (form.requestSubmit) {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            }, 500);
        });
    }
})();
