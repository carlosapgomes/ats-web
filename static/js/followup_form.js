/* ATS Web — Follow-up form: show/hide conditional cause fields by select.

   Puramente visual (design D6/R5): a validacao das regras condicionais de
   causa fica no servidor (apps/dashboard/forms.py + apps/cases/followup.py).
   Para cada procedimento:
   - o radio performed (proc_<id>-performed) controla a secao de causa
     (<fieldset data-followup-reason-section>): "Realizado" desabilita e
     limpa a causa; "Nao realizado" reabilita.
   - o select de causa (proc_<id>-non_performance_reason) revela o texto de
     other; as demais causas mantem o grupo condicional oculto.

   O controle de causa e localizado pelo sufixo de name (independe do tipo de
   input). Os valores 'yes'/'no' dos radios performed espelham
   FollowUpForm.performed.choices em apps/dashboard/forms.py (fonte unica da
   convencao).
*/
(function () {
  var blocks = document.querySelectorAll('[data-followup-proc-id]');
  if (!blocks.length) return;

  function reasonControl(block) {
    return block.querySelector('[name$="-non_performance_reason"]');
  }

  function hideConditionalGroups(block) {
    var groups = block.querySelectorAll('[data-followup-detail]');
    for (var i = 0; i < groups.length; i++) {
      groups[i].style.display = 'none';
    }
  }

  function refresh(block) {
    var control = reasonControl(block);
    var active = control ? control.value : '';
    var groups = block.querySelectorAll('[data-followup-detail]');
    for (var i = 0; i < groups.length; i++) {
      var group = groups[i];
      group.style.display = group.getAttribute('data-followup-detail') === active ? 'block' : 'none';
    }
  }

  function applyPerformedState(block) {
    var section = block.querySelector('[data-followup-reason-section]');
    if (!section) return;
    var performed = block.querySelector('input[name$="-performed"]:checked');
    if (performed && performed.value === 'yes') {
      // Realizado: desabilita a secao de causa, limpa a selecao e esconde os
      // grupos condicionais.
      section.disabled = true;
      var control = reasonControl(block);
      if (control) control.value = '';
      hideConditionalGroups(block);
    } else {
      // Nao realizado (ou nada marcado): reabilita e aplica o show/hide atual.
      section.disabled = false;
      refresh(block);
    }
  }

  for (let b = 0; b < blocks.length; b++) {
    // let/const por iteracao (P1-1): cada listener captura o bloco corrente.
    const block = blocks[b];
    const performedRadios = block.querySelectorAll('input[name$="-performed"]');
    for (let p = 0; p < performedRadios.length; p++) {
      performedRadios[p].addEventListener('change', function () {
        applyPerformedState(block);
      });
    }
    const control = reasonControl(block);
    if (control) {
      control.addEventListener('change', function () {
        refresh(block);
      });
    }
    // Estado inicial: mantém o estado correto no load e no re-render pós-erro.
    applyPerformedState(block);
    refresh(block);
  }
})();
