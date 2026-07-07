/* ATS Web — Scheduler Confirm Form JavaScript */

(function () {
    var confirmRadio = document.getElementById('sched-confirm');
    var denyRadio = document.getElementById('sched-deny');
    var confirmSection = document.getElementById('confirm-section');
    var denySection = document.getElementById('deny-section');
    var schedDate = document.getElementById('sched-date');
    var schedTime = document.getElementById('sched-time');
    var denyReason = document.getElementById('deny-reason');
    var form = document.getElementById('schedule-form');
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
        if (confirmRadio && confirmRadio.checked) {
            confirmSection.classList.add('active');
            denySection.classList.remove('active');
            if (schedDate) schedDate.required = true;
            if (schedTime) schedTime.required = true;
            if (denyReason) denyReason.required = false;
        } else if (denyRadio && denyRadio.checked) {
            denySection.classList.add('active');
            confirmSection.classList.remove('active');
            if (schedDate) schedDate.required = false;
            if (schedTime) schedTime.required = false;
            if (denyReason) denyReason.required = true;
        } else {
            confirmSection.classList.remove('active');
            denySection.classList.remove('active');
        }
    }

    // Initialize state on page load
    toggleSections();

    if (confirmRadio) confirmRadio.addEventListener('change', toggleSections);
    if (denyRadio) denyRadio.addEventListener('change', toggleSections);

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function formatDateBR(dateStr, timeStr) {
        var d = new Date(dateStr + 'T' + (timeStr || '00:00'));
        return d.toLocaleString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    }

    // Clear invalid states on input
    if (schedDate) schedDate.addEventListener('change', function () { schedDate.classList.remove('is-invalid'); });
    if (schedTime) schedTime.addEventListener('change', function () { schedTime.classList.remove('is-invalid'); });
    if (denyReason) denyReason.addEventListener('input', function () { denyReason.classList.remove('is-invalid'); });

    if (form && confirmModal) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();

            // Validate decision selected
            if (!confirmRadio.checked && !denyRadio.checked) {
                var decisionError = document.getElementById('sched-decision-error');
                if (decisionError) decisionError.style.display = 'block';
                return;
            }
            var decisionError = document.getElementById('sched-decision-error');
            if (decisionError) decisionError.style.display = 'none';

            if (confirmRadio.checked) {
                if (!schedDate.value || !schedTime.value) {
                    if (!schedDate.value) schedDate.classList.add('is-invalid');
                    if (!schedTime.value) schedTime.classList.add('is-invalid');
                    return;
                }
                var dateFormatted = formatDateBR(schedDate.value, schedTime.value);
                confirmBody.innerHTML =
                    '<div class="text-center mb-3"><span style="font-size:3rem;">&#10003;</span></div>' +
                    '<p class="text-center mb-1"><strong>Agendamento Confirmado</strong></p>' +
                    '<p class="text-center mb-1">Data: <strong>' + dateFormatted + '</strong></p>' +
                    '<p class="text-center text-muted small">Caso ' + (document.getElementById('case-id-display') ? document.getElementById('case-id-display').value : '') + '</p>' +
                    '<div class="alert alert-info small mb-0 mt-3">O resultado será comunicado automaticamente à recepção.</div>';
            } else {
                var reason = denyReason.value.trim();
                if (!reason) {
                    denyReason.classList.add('is-invalid');
                    return;
                }
                confirmBody.innerHTML =
                    '<div class="text-center mb-3"><span style="font-size:3rem;">&#10007;</span></div>' +
                    '<p class="text-center mb-1"><strong>Agendamento Negado</strong></p>' +
                    '<p class="text-center text-muted small">Caso ' + (document.getElementById('case-id-display') ? document.getElementById('case-id-display').value : '') + '</p>' +
                    '<div class="mt-3"><strong>Motivo:</strong> ' + escapeHtml(reason) + '</div>' +
                    '<div class="alert alert-warning small mb-0 mt-3">O caso retornará para reavaliação. A recepção será notificada.</div>';
            }

            confirmModal.show();
        });
    }

    if (btnConfirmFinal) {
        btnConfirmFinal.addEventListener('click', function () {
            if (confirmModal) confirmModal.hide();

            // Disable button and give visual feedback
            if (btnSubmit) {
                btnSubmit.textContent = '✓ Enviado';
                btnSubmit.classList.remove('btn-hospital');
                btnSubmit.classList.add('btn-success');
                btnSubmit.disabled = true;
            }

            // Signal the work_lock guard that a protected submit is in progress.
            // HTMLFormElement.submit() does NOT fire the submit event, so the
            // guard in work_lock.js cannot intercept this path via addEventListener.
            window.ATS_WORK_LOCK_SUBMITTING = true;

            // Submit the form to the server
            setTimeout(function () {
                form.submit();
            }, 500);
        });
    }
})();
