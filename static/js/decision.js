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
    var confirmModalTitle = document.getElementById('confirm-modal-title');
    var btnConfirmFinal = document.getElementById('btn-confirm-final');
    var btnRevisar = document.getElementById('btn-revisar');
    var btnBackToForm = document.getElementById('btn-back-to-form');
    var btnLeaveWithoutDecision = document.getElementById('btn-leave-without-decision');
    var btnSubmit = document.getElementById('btn-submit');

    var acceptOption = document.querySelector('.decision-option--accept');
    var denyOption = document.querySelector('.decision-option--deny');

    if (!form) return;

    var confirmModal = null;
    if (confirmModalEl) {
        confirmModal = new bootstrap.Modal(confirmModalEl);
    }

    // ── Card selection highlight ──────────────────────────────────────

    function updateDecisionCardHighlight() {
        if (acceptOption) acceptOption.classList.remove('is-selected');
        if (denyOption) denyOption.classList.remove('is-selected');
        if (acceptRadio && acceptRadio.checked && acceptOption) {
            acceptOption.classList.add('is-selected');
        } else if (denyRadio && denyRadio.checked && denyOption) {
            denyOption.classList.add('is-selected');
        }
    }

    function onDecisionCardClick(decision) {
        return function () {
            if (decision === 'accept' && acceptRadio) {
                acceptRadio.checked = true;
            } else if (decision === 'deny' && denyRadio) {
                denyRadio.checked = true;
            }
            toggleSections();
            updateDecisionCardHighlight();
        };
    }

    if (acceptOption) {
        acceptOption.addEventListener('click', onDecisionCardClick('accept'));
    }
    if (denyOption) {
        denyOption.addEventListener('click', onDecisionCardClick('deny'));
    }

    // ── Section toggling ──────────────────────────────────────────────

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
    updateDecisionCardHighlight();

    if (acceptRadio) acceptRadio.addEventListener('change', function () {
        toggleSections();
        updateDecisionCardHighlight();
    });
    if (denyRadio) denyRadio.addEventListener('change', function () {
        toggleSections();
        updateDecisionCardHighlight();
    });

    // ── Helpers ───────────────────────────────────────────────────────

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // Clear invalid states on input
    if (supportFlag) supportFlag.addEventListener('change', function () { supportFlag.classList.remove('is-invalid'); });
    if (admissionFlow) admissionFlow.addEventListener('change', function () { admissionFlow.classList.remove('is-invalid'); });
    if (denyReason) denyReason.addEventListener('input', function () { denyReason.classList.remove('is-invalid'); });

    // ── Pending validation ────────────────────────────────────────────

    function collectMissingItems() {
        var items = [];

        if (!acceptRadio.checked && !denyRadio.checked) {
            items.push('Escolha Aceitar ou Negar.');
            return items;
        }

        if (acceptRadio.checked) {
            if (!supportFlag || !supportFlag.value) {
                items.push('Selecione o Suporte Necessário.');
            }
            if (!admissionFlow || !admissionFlow.value) {
                items.push('Selecione o Fluxo de Admissão.');
            }
        }

        if (denyRadio.checked) {
            var reason = denyReason ? denyReason.value.trim() : '';
            if (!reason) {
                items.push('Informe o Motivo da Negativa.');
            }
        }

        return items;
    }

    function showPendingModal(items) {
        var listHtml = '<ul class="mb-0">';
        for (var i = 0; i < items.length; i++) {
            listHtml += '<li>' + escapeHtml(items[i]) + '</li>';
        }
        listHtml += '</ul>';

        confirmModalTitle.textContent = 'Decisão incompleta';
        confirmBody.innerHTML =
            '<div class="text-center mb-3"><span style="font-size:2rem;">&#9888;</span></div>' +
            '<p class="text-center mb-2">Preencha os campos abaixo antes de confirmar:</p>' +
            listHtml;

        btnRevisar.style.display = 'none';
        btnBackToForm.style.display = 'inline-block';
        btnLeaveWithoutDecision.style.display = 'inline-block';
        btnConfirmFinal.style.display = 'none';

        confirmModal.show();
    }

    function showFinalConfirmModal(decision, supportText, flowText, reason) {
        confirmModalTitle.textContent = 'Confirmar Decisão';

        if (decision === 'accept') {
            confirmBody.innerHTML =
                '<div class="text-center mb-3"><span style="font-size:3rem;">&#10003;</span></div>' +
                '<p class="text-center mb-1"><strong>ACEITAR</strong> &mdash; ' + escapeHtml(supportText) + ' &middot; ' + escapeHtml(flowText) + '</p>' +
                '<div class="alert alert-info small mb-0 mt-3">O caso será encaminhado automaticamente para agendamento.</div>';
        } else {
            confirmBody.innerHTML =
                '<div class="text-center mb-3"><span style="font-size:3rem;">&#10007;</span></div>' +
                '<p class="text-center mb-1"><strong>NEGAR</strong></p>' +
                '<div class="mt-3"><strong>Motivo:</strong> ' + escapeHtml(reason) + '</div>' +
                '<div class="alert alert-warning small mb-0 mt-3">O resultado será comunicado à recepção.</div>';
        }

        btnRevisar.style.display = 'inline-block';
        btnBackToForm.style.display = 'none';
        btnLeaveWithoutDecision.style.display = 'none';
        btnConfirmFinal.style.display = 'inline-block';

        confirmModal.show();
    }

    // ── Submit handler ────────────────────────────────────────────────

    var finalSubmitConfirmed = false;

    if (form && confirmModal) {
        form.addEventListener('submit', function (e) {
            if (finalSubmitConfirmed) return;

            e.preventDefault();

            var missingItems = collectMissingItems();
            if (missingItems.length > 0) {
                showPendingModal(missingItems);
                return;
            }

            // All valid — show final confirmation
            var decision = acceptRadio.checked ? 'accept' : 'deny';
            var supportText = supportFlag && supportFlag.selectedIndex >= 0
                ? supportFlag.options[supportFlag.selectedIndex].text : '';
            var flowText = admissionFlow && admissionFlow.selectedIndex >= 0
                ? admissionFlow.options[admissionFlow.selectedIndex].text : '';
            var reason = denyReason ? denyReason.value.trim() : '';

            showFinalConfirmModal(decision, supportText, flowText, reason);
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
