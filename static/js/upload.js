/**
 * Upload de múltiplos PDFs com drag & drop + anexos condicionais — Vanilla JS.
 * Slice 002: UX condicional de anexos com preview, validação e confirmação.
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

  // Attachment elements
  var attachmentSection = document.getElementById('attachment-section');
  var attachmentInput = document.getElementById('attachment-input');
  var attachmentPreview = document.getElementById('attachment-preview');
  var attachmentList = document.getElementById('attachment-list');
  var attachmentCount = document.getElementById('attachment-count');
  var attachmentTotalSize = document.getElementById('attachment-total-size');
  var attachmentConfirmSection = document.getElementById('attachment-confirm-section');
  var attachmentConfirm = document.getElementById('attachment-confirm');
  var attachmentGuidance = document.getElementById('attachment-single-pdf-message');

  if (!uploadZone || !fileInput) return;

  // Limits (must match backend settings)
  var MAX_FILES = 30;
  var MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB per file
  var MAX_BATCH_SIZE = 600 * 1024 * 1024; // 600 MB total

  // Attachment limits
  var MAX_ATTACHMENTS = parseInt((attachmentInput && attachmentInput.getAttribute('data-max-attachments')) || '10', 10);
  var MAX_ATTACHMENT_FILE_SIZE = parseInt((attachmentInput && attachmentInput.getAttribute('data-max-attachment-bytes')) || '20971520', 10);
  var MAX_ATTACHMENT_TOTAL_SIZE = parseInt((attachmentInput && attachmentInput.getAttribute('data-max-total-attachment-bytes')) || '209715200', 10);

  // Accepted attachment extensions
  var ATTACHMENT_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png'];

  // State
  var validFiles = [];        // main PDF files
  var validAttachments = [];  // attachment files

  // ── Initial UI setup ─────────────────────────────────────────────

  // Hide attachment section initially (no PDF selected yet)
  if (attachmentSection) {
    attachmentSection.style.display = 'none';
  }

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

  // ── Attachment input change ────────────────────────────────────────

  if (attachmentInput) {
    attachmentInput.addEventListener('change', function () {
      if (attachmentInput.files.length > 0) {
        handleAttachmentFiles(attachmentInput.files);
      }
    });
  }

  // ── Função principal: processar PDFs selecionados ─────────────────

  function handleFiles(fileListRaw) {
    var newFiles = [];
    var errors = [];

    var filesArray = Array.prototype.slice.call(fileListRaw);
    fileInput.value = '';

    // Validate max count
    var totalAfterAdd = validFiles.length + filesArray.length;
    if (totalAfterAdd > MAX_FILES) {
      showAlert('warning', 'Máximo de ' + MAX_FILES + ' arquivos por lote. Selecione no máximo ' + (MAX_FILES - validFiles.length) + ' arquivo(s) adicional(is).');
      return;
    }

    // Validate each file
    for (var i = 0; i < filesArray.length; i++) {
      var file = filesArray[i];
      var validation = validateFile(file);
      if (validation.valid) {
        newFiles.push(file);
      } else {
        errors.push(validation.error);
      }
    }

    if (errors.length > 0) {
      showAlert('warning', errors);
    }

    if (newFiles.length === 0) {
      updateUI();
      return;
    }

    // Validate total batch size
    var currentTotal = getTotalSize(validFiles);
    var newTotal = getTotalSize(newFiles);
    if (currentTotal + newTotal > MAX_BATCH_SIZE) {
      showAlert('warning', 'Tamanho total do lote excede o limite de ' + formatSize(MAX_BATCH_SIZE) + '.');
      return;
    }

    // Add new valid files
    validFiles = validFiles.concat(newFiles);

    updateUI();

    if (errors.length === 0) {
      clearAlert();
    }
  }

  // ── Validação de PDF individual ───────────────────────────────────

  function validateFile(file) {
    var fileName = file.name || '';
    var fileSize = file.size || 0;

    if (!fileName.toLowerCase().endsWith('.pdf')) {
      return { valid: false, error: '"' + fileName + '" não é um arquivo PDF.' };
    }

    if (fileSize > MAX_FILE_SIZE) {
      return {
        valid: false,
        error: '"' + fileName + '" excede o limite de ' + formatSize(MAX_FILE_SIZE) + ' (' + formatSize(fileSize) + ').'
      };
    }

    for (var i = 0; i < validFiles.length; i++) {
      if (validFiles[i].name === fileName && validFiles[i].size === fileSize) {
        return { valid: false, error: '"' + fileName + '" já foi adicionado.' };
      }
    }

    return { valid: true, error: null };
  }

  // ── Attachment handling ──────────────────────────────────────────────

  function handleAttachmentFiles(fileListRaw) {
    var newAttachments = [];
    var errors = [];

    var filesArray = Array.prototype.slice.call(fileListRaw);
    attachmentInput.value = '';

    // Validate max count
    var totalAfterAdd = validAttachments.length + filesArray.length;
    if (totalAfterAdd > MAX_ATTACHMENTS) {
      showAlert('warning', 'Máximo de ' + MAX_ATTACHMENTS + ' anexos. Selecione no máximo ' + (MAX_ATTACHMENTS - validAttachments.length) + ' arquivo(s) adicional(is).');
      return;
    }

    // Validate each attachment file
    for (var i = 0; i < filesArray.length; i++) {
      var file = filesArray[i];
      var validation = validateAttachmentFile(file);
      if (validation.valid) {
        newAttachments.push(file);
      } else {
        errors.push(validation.error);
      }
    }

    if (errors.length > 0) {
      showAlert('warning', errors);
    }

    if (newAttachments.length === 0) {
      updateAttachmentUI();
      return;
    }

    // Validate total attachment size
    var currentTotal = getTotalSize(validAttachments);
    var newTotal = getTotalSize(newAttachments);
    if (currentTotal + newTotal > MAX_ATTACHMENT_TOTAL_SIZE) {
      showAlert('warning', 'Tamanho total dos anexos excede o limite de ' + formatSize(MAX_ATTACHMENT_TOTAL_SIZE) + '.');
      return;
    }

    validAttachments = validAttachments.concat(newAttachments);
    updateAttachmentUI();

    if (errors.length === 0) {
      clearAlert();
    }
  }

  function validateAttachmentFile(file) {
    var fileName = file.name || '';
    var fileSize = file.size || 0;
    var ext = (fileName.toLowerCase().split('.').pop()) || '';
    ext = '.' + ext;

    // Extension check
    if (ATTACHMENT_EXTENSIONS.indexOf(ext) === -1) {
      return { valid: false, error: '"' + fileName + '" formato não aceito. Use PDF, JPEG ou PNG.' };
    }

    // File size check
    if (fileSize > MAX_ATTACHMENT_FILE_SIZE) {
      return {
        valid: false,
        error: '"' + fileName + '" excede o limite de ' + formatSize(MAX_ATTACHMENT_FILE_SIZE) + ' (' + formatSize(fileSize) + ').'
      };
    }

    // Duplicate check
    for (var i = 0; i < validAttachments.length; i++) {
      if (validAttachments[i].name === fileName && validAttachments[i].size === fileSize) {
        return { valid: false, error: '"' + fileName + '" já foi adicionado.' };
      }
    }

    return { valid: true, error: null };
  }

  function removeAttachment(index) {
    if (index >= 0 && index < validAttachments.length) {
      validAttachments.splice(index, 1);
      updateAttachmentUI();
      clearAlert();
    }
  }

  // ── Attachment thumbnail/preview ─────────────────────────────────────

  function createAttachmentThumbnail(file) {
    var ext = (file.name.toLowerCase().split('.').pop()) || '';

    if (ext === 'pdf') {
      // PDF icon (no thumbnail)
      var span = document.createElement('span');
      span.textContent = '📄';
      span.style.fontSize = '1.5rem';
      span.setAttribute('aria-hidden', 'true');
      return span;
    }

    if (ext === 'jpg' || ext === 'jpeg' || ext === 'png') {
      // Try to create image thumbnail via FileReader
      var img = document.createElement('img');
      img.style.width = '40px';
      img.style.height = '40px';
      img.style.objectFit = 'cover';
      img.style.borderRadius = '4px';
      img.style.border = '1px solid #dee2e6';
      img.alt = file.name;

      var reader = new FileReader();
      reader.onload = (function (imageElement) {
        return function (e) {
          imageElement.src = e.target.result;
        };
      })(img);
      reader.readAsDataURL(file);

      return img;
    }

    // Fallback icon
    var span = document.createElement('span');
    span.textContent = '📎';
    span.style.fontSize = '1.5rem';
    span.setAttribute('aria-hidden', 'true');
    return span;
  }

  // ── UI Update ────────────────────────────────────────────────────────

  function updateUI() {
    if (validFiles.length === 0) {
      uploadPreview.classList.add('d-none');
      uploadBtn.disabled = true;

      uploadZone.querySelector('.upload-zone__text').textContent = 'Arraste os PDFs aqui ou clique para selecionar';
      uploadZone.querySelector('.upload-zone__hint').textContent = 'Apenas arquivos PDF — até 20 MB cada';

      // Hide attachment section when no PDFs
      if (attachmentSection) {
        attachmentSection.style.display = 'none';
      }
      return;
    }

    uploadPreview.classList.remove('d-none');
    batchCount.textContent = validFiles.length + ' arquivo(s) selecionado(s)';

    var totalBytes = getTotalSize(validFiles);
    batchTotalSize.textContent = formatSize(totalBytes);

    renderFileList();

    // Enable submit if we have PDFs
    uploadBtn.disabled = false;

    var remainingSlots = MAX_FILES - validFiles.length;
    uploadZone.querySelector('.upload-zone__text').textContent =
      validFiles.length + ' arquivo(s) selecionado(s) — clique para adicionar mais';
    uploadZone.querySelector('.upload-zone__hint').textContent =
      'Ainda cabem ' + remainingSlots + ' arquivo(s) (máx. ' + MAX_FILES + ', ' + formatSize(MAX_BATCH_SIZE) + ' total)';

    // ── Conditional attachment section ──────────────────────────────
    updateAttachmentSectionVisibility();
  }

  function updateAttachmentSectionVisibility() {
    if (!attachmentSection) return;

    var pdfCount = countPdfFiles(validFiles);

    if (pdfCount === 1) {
      // Exactly 1 PDF: show and enable attachments
      attachmentSection.style.display = 'block';
      attachmentInput.disabled = false;
      if (attachmentGuidance) {
        attachmentGuidance.style.display = 'block';
        attachmentGuidance.textContent = 'Anexos habilitados — você pode adicionar documentos complementares.';
      }
    } else {
      // 0 or >1 PDF: hide attachments and clear selection
      attachmentSection.style.display = 'none';
      attachmentInput.disabled = true;
      clearAttachments();
    }
  }

  function countPdfFiles(files) {
    var count = 0;
    for (var i = 0; i < files.length; i++) {
      var name = files[i].name || '';
      if (name.toLowerCase().endsWith('.pdf')) {
        count++;
      }
    }
    return count;
  }

  function clearAttachments() {
    if (validAttachments.length > 0) {
      validAttachments = [];
      updateAttachmentUI();
    }
  }

  // ── Attachment UI ────────────────────────────────────────────────────

  function updateAttachmentUI() {
    if (!attachmentPreview) return;

    if (validAttachments.length === 0) {
      attachmentPreview.classList.add('d-none');
      if (attachmentConfirmSection) {
        attachmentConfirmSection.classList.add('d-none');
      }
      if (attachmentConfirm) {
        attachmentConfirm.checked = false;
      }
      return;
    }

    attachmentPreview.classList.remove('d-none');

    attachmentCount.textContent = validAttachments.length + ' anexo(s)';

    var totalBytes = getTotalSize(validAttachments);
    attachmentTotalSize.textContent = formatSize(totalBytes);

    renderAttachmentList();

    // Show confirmation checkbox when attachments are present
    if (attachmentConfirmSection) {
      attachmentConfirmSection.classList.remove('d-none');
    }
  }

  function renderAttachmentList() {
    if (!attachmentList) return;
    attachmentList.replaceChildren();

    for (var i = 0; i < validAttachments.length; i++) {
      var file = validAttachments[i];
      var li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center py-2';
      li.setAttribute('role', 'listitem');

      // Thumbnail + info
      var infoSpan = document.createElement('span');
      infoSpan.className = 'd-flex align-items-center gap-2';

      var thumb = createAttachmentThumbnail(file);

      var nameSpan = document.createElement('span');
      nameSpan.className = 'fw-semibold small';
      nameSpan.textContent = file.name;

      var sizeSpan = document.createElement('span');
      sizeSpan.className = 'text-muted small';
      sizeSpan.textContent = formatSize(file.size);

      infoSpan.appendChild(thumb);
      infoSpan.appendChild(nameSpan);
      infoSpan.appendChild(sizeSpan);

      // Remove button
      var removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'btn btn-sm btn-outline-danger btn-remove-attachment';
      removeBtn.textContent = 'Remover';
      removeBtn.setAttribute('aria-label', 'Remover anexo ' + file.name);
      removeBtn.setAttribute('data-attachment-index', String(i));

      (function (idx) {
        removeBtn.addEventListener('click', function () {
          removeAttachment(idx);
        });
      })(i);

      li.appendChild(infoSpan);
      li.appendChild(removeBtn);
      attachmentList.appendChild(li);
    }
  }

  // ── Renderizar lista de arquivos PDF ───────────────────────────────

  function renderFileList() {
    fileList.replaceChildren();

    for (var i = 0; i < validFiles.length; i++) {
      var file = validFiles[i];
      var li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center py-2';
      li.setAttribute('role', 'listitem');

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

      var removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'btn btn-sm btn-outline-danger btn-remove-file';
      removeBtn.textContent = 'Remover';
      removeBtn.setAttribute('aria-label', 'Remover ' + file.name);
      removeBtn.setAttribute('data-index', String(i));

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

  // ── Remover arquivo PDF ───────────────────────────────────────────

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

  var uploadForm = document.getElementById('upload-form');
  if (uploadForm) {
    uploadForm.addEventListener('submit', function (e) {
      if (validFiles.length === 0) {
        e.preventDefault();
        showAlert('warning', 'Nenhum arquivo válido selecionado.');
        return;
      }

      // If there are attachments, require confirmation checkbox
      if (validAttachments.length > 0) {
        if (!attachmentConfirm || !attachmentConfirm.checked) {
          e.preventDefault();
          showAlert('warning', 'Confirme que revisou os anexos e que pertencem ao mesmo paciente/caso.');
          return;
        }
      }

      // Build DataTransfer for PDF files
      var dataTransfer = new DataTransfer();
      for (var i = 0; i < validFiles.length; i++) {
        dataTransfer.items.add(validFiles[i]);
      }
      fileInput.files = dataTransfer.files;

      // Build DataTransfer for attachment files
      if (attachmentInput && validAttachments.length > 0) {
        var attDataTransfer = new DataTransfer();
        for (var j = 0; j < validAttachments.length; j++) {
          attDataTransfer.items.add(validAttachments[j]);
        }
        attachmentInput.files = attDataTransfer.files;
      }

      uploadBtn.disabled = true;
      uploadBtn.textContent = 'Enviando...';
    });
  }
})();
