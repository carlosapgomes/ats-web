/* ATS Web — Follow-up form: show/hide conditional cause fields by radio.

   Puramente visual (design D6/R5): a validacao das regras condicionais de
   causa fica no servidor (apps/dashboard/forms.py + apps/cases/followup.py).
   Para cada procedimento:
   - o radio performed (proc_<id>-performed) controla a secao de causa
     (<fieldset data-followup-reason-section>): "Realizado" desabilita e
     desmarca a causa; "Nao realizado" reabilita.
   - o radio de causa (proc_<id>-non_performance_reason) revela o submotivo
     de resource_shortage ou o texto de other; os demais grupos
     condicionais permanecem ocultos.

   Os valores 'yes'/'no' dos radios performed espelham
   FollowUpForm.performed.choices em apps/dashboard/forms.py (fonte unica da
   convencao).
*/
(function () {
  var blocks = document.querySelectorAll('[data-followup-proc-id]');
  if (!blocks.length) return;

  function refresh(block) {
    var checked = block.querySelector('input[name$="-non_performance_reason"]:checked');
    var active = checked ? checked.value : '';
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
      // Realizado: desabilita radios de causa/submotivo e textarea, desmarca
      // a causa e esconde os grupos condicionais.
      section.disabled = true;
      var reasonRadios = block.querySelectorAll('input[name$="-non_performance_reason"]');
      for (var i = 0; i < reasonRadios.length; i++) {
        reasonRadios[i].checked = false;
      }
      var groups = block.querySelectorAll('[data-followup-detail]');
      for (var j = 0; j < groups.length; j++) {
        groups[j].style.display = 'none';
      }
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
    const reasonRadios = block.querySelectorAll('input[name$="-non_performance_reason"]');
    for (let r = 0; r < reasonRadios.length; r++) {
      reasonRadios[r].addEventListener('change', function () {
        refresh(block);
      });
    }
    // Estado inicial: mantém o estado correto no load e no re-render pós-erro.
    applyPerformedState(block);
    refresh(block);
  }
})();
