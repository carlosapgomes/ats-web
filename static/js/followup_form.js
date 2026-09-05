/* ATS Web — Follow-up form: show/hide conditional cause fields by radio.

   Puramente visual (design D6/R5): a validacao das regras condicionais de
   causa fica no servidor (apps/dashboard/forms.py + apps/cases/followup.py).
   Para cada procedimento, o radio de causa (proc_<id>-non_performance_reason)
   revela o submotivo de resource_shortage ou o texto de other; os demais
   grupos condicionais permanecem ocultos.
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

  for (let b = 0; b < blocks.length; b++) {
    // let/const por iteração (P1-1): cada listener captura o bloco corrente.
    const block = blocks[b];
    const reasonRadios = block.querySelectorAll('input[name$="-non_performance_reason"]');
    for (let r = 0; r < reasonRadios.length; r++) {
      reasonRadios[r].addEventListener('change', function () {
        refresh(block);
      });
    }
    // Estado inicial: mantém o grupo visível quando há re-render pós-erro.
    refresh(block);
  }
})();
