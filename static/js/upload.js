/**
 * Upload de múltiplos PDFs com drag & drop — Vanilla JS.
 * Slice 004: UI/JS de Upload Múltiplo com preview de lote e validação client-side.
 */
(function () {
  'use strict';

  var uploadZone = document.getElementById('upload-zone');
  var fileInput = document.getElementById('file-input');
  var uploadBtn = document.getElementById('btn-upload');
  var uploadPreview = document.getElementById('upload-preview');
  var fileList = document.getElementById('file-list');
  var batchCount = document.getElementById('batch-count');
  var batchTotalSize = document.getElementById('batch-total-size');
  var uploadAlert = document.getElementById('upload-alert');

  if (!uploadZone || !fileInput) return;

  // Limites (devem estar alinhados com os settings do backend)
  var MAX_FILES = 30;
  var MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB por arquivo
  var MAX_BATCH_SIZE = 600 * 1024 * 1024; // 600 MB total

  // Estado interno: lista de arquivos válidos
  var validFiles = [];

  // ── Eventos de clique ──────────────────────────────────────────────

  uploadZone.addEventListener('click', function () {
    fileInput.click();
  });

  // ── Eventos de drag & drop ─────────────────────────────────────────

  uploadZone.addEventListener('dragover', function (e) {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
  });

  uploadZone.addEventListener('dragleave', function () {
    uploadZone.classList.remove('drag-over');
  });

  uploadZone.addEventListener('drop', function (e) {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    var files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFiles(files);
    }
  });

  // ── Evento de seleção via input ────────────────────────────────────

  fileInput.addEventListener('change', function () {
    if (fileInput.files.length > 0) {
      handleFiles(fileInput.files);
    }
  });

  // ── Função principal: processar arquivos selecionados ──────────────

  function handleFiles(fileListRaw) {
    var newFiles = [];
    var errors = [];

    // Converter FileList para Array
    var filesArray = Array.prototype.slice.call(fileListRaw);

    // Limpar seleção anterior do input (permite re-selecionar o mesmo arquivo)
    fileInput.value = '';

    // Validar quantidade máxima no lote (considerando arquivos já existentes)
    var totalAfterAdd = validFiles.length + filesArray.length;
    if (totalAfterAdd > MAX_FILES) {
      showAlert('warning', 'Máximo de ' + MAX_FILES + ' arquivos por lote. Selecione no máximo ' + (MAX_FILES - validFiles.length) + ' arquivo(s) adicional(is).');
      return;
    }

    // Validar cada arquivo
    for (var i = 0; i < filesArray.length; i++) {
      var file = filesArray[i];
      var validation = validateFile(file);
      if (validation.valid) {
        newFiles.push(file);
      } else {
        errors.push(validation.error);
      }
    }

    // Exibir erros de validação individuais
    if (errors.length > 0) {
      showAlert('warning', errors);
    }

    if (newFiles.length === 0) {
      // Nenhum arquivo novo válido, mas pode haver arquivos válidos existentes
      updateUI();
      return;
    }

    // Validar tamanho total do lote
    var currentTotal = getTotalSize(validFiles);
    var newTotal = getTotalSize(newFiles);
    if (currentTotal + newTotal > MAX_BATCH_SIZE) {
      showAlert('warning', 'Tamanho total do lote excede o limite de ' + formatSize(MAX_BATCH_SIZE) + '.');
      return;
    }

    // Adicionar novos arquivos válidos à lista
    validFiles = validFiles.concat(newFiles);

    // Atualizar UI
    updateUI();

    // Só limpar alerta se não houve erros (preservar mensagens de inválidos)
    if (errors.length === 0) {
      clearAlert();
    }
  }

  // ── Validação de arquivo individual ────────────────────────────────

  function validateFile(file) {
    var fileName = file.name || '';
    var fileSize = file.size || 0;

    // Verificar extensão PDF
    if (!fileName.toLowerCase().endsWith('.pdf')) {
      return { valid: false, error: '"' + fileName + '" não é um arquivo PDF.' };
    }

    // Verificar tamanho máximo por arquivo
    if (fileSize > MAX_FILE_SIZE) {
      return {
        valid: false,
        error: '"' + fileName + '" excede o limite de ' + formatSize(MAX_FILE_SIZE) + ' (' + formatSize(fileSize) + ').'
      };
    }

    // Verificar se já foi adicionado (evitar duplicatas)
    for (var i = 0; i < validFiles.length; i++) {
      if (validFiles[i].name === fileName && validFiles[i].size === fileSize) {
        return { valid: false, error: '"' + fileName + '" já foi adicionado.' };
      }
    }

    return { valid: true, error: null };
  }

  // ── Atualização da UI ──────────────────────────────────────────────

  function updateUI() {
    if (validFiles.length === 0) {
      // Nenhum arquivo: esconder preview, desabilitar botão
      uploadPreview.classList.add('d-none');
      uploadBtn.disabled = true;

      // Resetar hint da zona de upload
      uploadZone.querySelector('.upload-zone__text').textContent = 'Arraste os PDFs aqui ou clique para selecionar';
      uploadZone.querySelector('.upload-zone__hint').textContent = 'Apenas arquivos PDF — até 20 MB cada';
      return;
    }

    // Mostrar preview
    uploadPreview.classList.remove('d-none');

    // Atualizar contagem do lote
    batchCount.textContent = validFiles.length + ' arquivo(s) selecionado(s)';

    // Atualizar tamanho total
    var totalBytes = getTotalSize(validFiles);
    batchTotalSize.textContent = formatSize(totalBytes);

    // Renderizar lista de arquivos
    renderFileList();

    // Habilitar botão de submit
    uploadBtn.disabled = false;

    // Atualizar hint da zona de upload
    var remainingSlots = MAX_FILES - validFiles.length;
    uploadZone.querySelector('.upload-zone__text').textContent =
      validFiles.length + ' arquivo(s) selecionado(s) — clique para adicionar mais';
    uploadZone.querySelector('.upload-zone__hint').textContent =
      'Ainda cabem ' + remainingSlots + ' arquivo(s) (máx. ' + MAX_FILES + ', ' + formatSize(MAX_BATCH_SIZE) + ' total)';
  }

  // ── Renderizar lista de arquivos ───────────────────────────────────

  function renderFileList() {
    fileList.replaceChildren();

    for (var i = 0; i < validFiles.length; i++) {
      var file = validFiles[i];
      var li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center py-2';
      li.setAttribute('role', 'listitem');

      // Informações do arquivo
      var infoSpan = document.createElement('span');
      infoSpan.className = 'd-flex align-items-center gap-2';

      var iconSpan = document.createElement('span');
      iconSpan.textContent = '📄';
      iconSpan.style.fontSize = '1.2rem';
      iconSpan.setAttribute('aria-hidden', 'true');

      var nameSpan = document.createElement('span');
      nameSpan.className = 'fw-semibold';
      nameSpan.textContent = file.name;

      var sizeSpan = document.createElement('span');
      sizeSpan.className = 'text-muted small';
      sizeSpan.textContent = formatSize(file.size);

      infoSpan.appendChild(iconSpan);
      infoSpan.appendChild(nameSpan);
      infoSpan.appendChild(sizeSpan);

      // Botão de remover
      var removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'btn btn-sm btn-outline-danger btn-remove-file';
      removeBtn.textContent = 'Remover';
      removeBtn.setAttribute('aria-label', 'Remover ' + file.name);
      removeBtn.setAttribute('data-index', String(i));

      // Usar closure para capturar o índice corretamente
      (function (idx) {
        removeBtn.addEventListener('click', function () {
          removeFile(idx);
        });
      })(i);

      li.appendChild(infoSpan);
      li.appendChild(removeBtn);
      fileList.appendChild(li);
    }
  }

  // ── Remover arquivo da lista ───────────────────────────────────────

  function removeFile(index) {
    if (index >= 0 && index < validFiles.length) {
      validFiles.splice(index, 1);
      updateUI();
      clearAlert();
    }
  }

  // ── Alertas ────────────────────────────────────────────────────────

  function showAlert(type, messages) {
    if (!uploadAlert) return;
    uploadAlert.className = 'alert alert-' + type + ' mb-3';
    uploadAlert.replaceChildren();

    // Aceita string única ou array de strings
    var list = Array.isArray(messages) ? messages : [messages];

    for (var i = 0; i < list.length; i++) {
      if (i > 0) {
        uploadAlert.appendChild(document.createElement('br'));
      }
      uploadAlert.appendChild(document.createTextNode(list[i]));
    }

    uploadAlert.classList.remove('d-none');
  }

  function clearAlert() {
    if (!uploadAlert) return;
    uploadAlert.classList.add('d-none');
    uploadAlert.replaceChildren();
  }

  // ── Utilitários ────────────────────────────────────────────────────

  function getTotalSize(files) {
    var total = 0;
    for (var i = 0; i < files.length; i++) {
      total += files[i].size || 0;
    }
    return total;
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
  }

  // ── Interceptar submit do formulário ───────────────────────────────
  // Garantir que apenas arquivos válidos sejam enviados

  var uploadForm = document.getElementById('upload-form');
  if (uploadForm) {
    uploadForm.addEventListener('submit', function (e) {
      if (validFiles.length === 0) {
        e.preventDefault();
        showAlert('warning', 'Nenhum arquivo válido selecionado.');
        return;
      }

      // Construir um novo DataTransfer com os arquivos válidos
      var dataTransfer = new DataTransfer();
      for (var i = 0; i < validFiles.length; i++) {
        dataTransfer.items.add(validFiles[i]);
      }
      fileInput.files = dataTransfer.files;

      // Desabilitar botão para evitar duplo clique
      uploadBtn.disabled = true;
      uploadBtn.textContent = 'Enviando...';
    });
  }
})();
