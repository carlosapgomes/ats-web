/**
 * Upload de PDF com drag & drop — Vanilla JS.
 * Slice 3: Upload de PDF + Criação do Caso.
 */
(function () {
  'use strict';

  var uploadZone = document.getElementById('upload-zone');
  var fileInput = document.getElementById('file-input');
  var uploadBtn = document.getElementById('btn-upload');
  var preview = document.getElementById('upload-preview');
  var previewName = document.getElementById('preview-name');
  var previewSize = document.getElementById('preview-size');

  if (!uploadZone || !fileInput) return;

  // Click na zone → trigger file input
  uploadZone.addEventListener('click', function () {
    fileInput.click();
  });

  // Drag events
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
    if (files.length > 0) handleFile(files[0]);
  });

  // File input change
  fileInput.addEventListener('change', function () {
    if (fileInput.files.length > 0) handleFile(fileInput.files[0]);
  });

  function handleFile(file) {
    // Validar tipo
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      alert('Apenas arquivos PDF são aceitos.');
      fileInput.value = '';
      return;
    }

    // Validar tamanho (20 MB)
    var maxSize = 20 * 1024 * 1024;
    if (file.size > maxSize) {
      alert('O arquivo excede o limite de 20 MB.');
      fileInput.value = '';
      return;
    }

    // Atualizar UI
    uploadZone.querySelector('.upload-zone__text').textContent = file.name;
    uploadZone.querySelector('.upload-zone__hint').textContent = formatSize(file.size);

    if (preview && previewName && previewSize) {
      previewName.textContent = file.name;
      previewSize.textContent = formatSize(file.size);
      preview.classList.remove('d-none');
    }

    if (uploadBtn) uploadBtn.disabled = false;
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }
})();
