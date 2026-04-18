/* edit_exam_images.js — image gallery for edit_exam page
 * Reads page data from window._editExamData (injected by the template).
 * Exposes:
 *   window.closeImageModal()   — used by modal HTML onclick attributes
 *   window.hasPendingImages()  — called by the inline submit handler
 *   window.scrollToPendingImages() — called by the inline submit handler
 */
(function () {
  'use strict';

  // ── State ────────────────────────────────────────────────────────────────
  let pendingDT = new DataTransfer();

  // ── Data helpers ─────────────────────────────────────────────────────────
  function getExamData() {
    return window._editExamData || {};
  }

  // ── Thumbnail builders (DOM API only — no innerHTML with data) ───────────
  function buildUploadedThumb(filename, path) {
    path = path.replace(/\\/g, '/');

    const wrapper = document.createElement('div');
    wrapper.className = 'image-thumbnail-wrapper';
    wrapper.style.cssText = 'position:relative; display:inline-block;';
    wrapper.dataset.filename = filename;

    const img = document.createElement('img');
    img.src = '/' + path;
    img.style.cssText = 'height:150px; width:150px; object-fit:cover; cursor:pointer; border-radius:4px;';
    img.title = 'Click để phóng to';
    img.addEventListener('click', () => openImageModal('/' + path));

    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'delete is-small';
    delBtn.style.cssText = 'position:absolute; top:5px; right:5px;';
    delBtn.title = 'Xóa ảnh khỏi máy chủ';
    delBtn.addEventListener('click', (e) => { e.stopPropagation(); removeUploadedImage(filename); });

    wrapper.appendChild(img);
    wrapper.appendChild(delBtn);
    return wrapper;
  }

  function buildPendingThumb(file, dataUrl) {
    const wrapper = document.createElement('div');
    wrapper.className = 'image-thumbnail-wrapper pending-upload';
    wrapper.style.cssText = 'position:relative; display:inline-block;';
    wrapper.dataset.pendingName = file.name;

    const img = document.createElement('img');
    img.src = dataUrl;
    img.style.cssText = 'height:150px; width:150px; object-fit:cover; border-radius:4px; border:2px dashed #3298dc; cursor:pointer;';
    img.title = file.name + ' (Chờ tải lên) — click để phóng to';
    img.addEventListener('click', () => openImageModal(dataUrl));

    const badge = document.createElement('div');
    badge.style.cssText = 'position:absolute; bottom:5px; left:0; right:0; text-align:center; pointer-events:none;';
    const tag = document.createElement('span');
    tag.className = 'tag is-warning is-light is-small';
    tag.textContent = 'Chờ tải lên';
    badge.appendChild(tag);

    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'delete is-small';
    delBtn.style.cssText = 'position:absolute; top:5px; right:5px;';
    delBtn.title = 'Bỏ chọn ảnh này';
    delBtn.addEventListener('click', (e) => { e.stopPropagation(); removePendingFile(file.name, wrapper); });

    wrapper.appendChild(img);
    wrapper.appendChild(badge);
    wrapper.appendChild(delBtn);
    return wrapper;
  }

  // ── Pending file management ───────────────────────────────────────────────
  function addPendingFiles(fileList) {
    const gallery = document.getElementById('imageGallery');
    Array.from(fileList).forEach(function (file) {
      // Skip exact duplicates already in pending queue
      for (const existing of pendingDT.files) {
        if (existing.name === file.name && existing.size === file.size) return;
      }
      pendingDT.items.add(file);
      const reader = new FileReader();
      reader.onload = function (e) {
        gallery.appendChild(buildPendingThumb(file, e.target.result));
      };
      reader.readAsDataURL(file);
    });
    syncWarningBanner();
  }

  function removePendingFile(filename, wrapperEl) {
    const newDT = new DataTransfer();
    for (const f of pendingDT.files) {
      if (f.name !== filename) newDT.items.add(f);
    }
    pendingDT = newDT;
    if (wrapperEl) wrapperEl.remove();
    syncWarningBanner();
  }

  function clearAllPending() {
    pendingDT = new DataTransfer();
    document.querySelectorAll('.pending-upload').forEach(function (el) { el.remove(); });
    document.getElementById('lab_images').value = '';
    syncWarningBanner();
  }

  // ── Warning banner ────────────────────────────────────────────────────────
  function syncWarningBanner() {
    const banner = document.getElementById('pendingImagesBanner');
    if (!banner) return;
    if (pendingDT.files.length > 0) {
      banner.textContent = '\u26a0\ufe0f B\u1ea1n c\u00f3 ' + pendingDT.files.length +
        ' \u1ea3nh ch\u01b0a t\u1ea3i l\u00ean. Nh\u1ea5n \u201c\ud83d\udce4 T\u1ea3i l\u00ean\u201d ho\u1eb7c \u201c\ud83d\uddd1 X\u00f3a \u1ea3nh ch\u1ecdn\u201d tr\u01b0\u1edbc khi l\u01b0u.';
      banner.style.display = 'block';
    } else {
      banner.style.display = 'none';
    }
  }

  // ── Upload pending files to server ────────────────────────────────────────
  async function uploadPendingFiles() {
    if (pendingDT.files.length === 0) {
      alert('Vui lòng chọn ảnh trước');
      return;
    }
    const { patient_id, exam_id } = getExamData();
    if (!patient_id || !exam_id) {
      alert('Lỗi: Thiếu ID bệnh nhân hoặc lần khám');
      return;
    }

    const formData = new FormData();
    Array.from(pendingDT.files).forEach(function (f) { formData.append('lab_image', f); });

    const progressBar = document.getElementById('uploadProgress');
    progressBar.style.display = 'block';
    progressBar.value = 0;

    try {
      const response = await fetch('/exam/' + patient_id + '/' + exam_id + '/upload_images', {
        method: 'POST',
        body: formData
      });
      progressBar.value = 50;
      const data = await response.json();

      if (data.status === 'success') {
        progressBar.value = 100;
        clearAllPending();
        const gallery = document.getElementById('imageGallery');
        data.images.forEach(function (img) {
          gallery.appendChild(buildUploadedThumb(img.filename, img.path));
        });
        setTimeout(function () {
          progressBar.style.display = 'none';
          progressBar.value = 0;
        }, 1000);
      } else {
        throw new Error(data.message || 'Upload thất bại');
      }
    } catch (error) {
      console.error(error);
      alert('❌ Lỗi upload: ' + error.message);
      progressBar.style.display = 'none';
    }
  }

  // ── Delete an already-uploaded image from server ──────────────────────────
  async function removeUploadedImage(filename) {
    if (!confirm('Xóa ảnh này khỏi máy chủ?')) return;
    const { patient_id, exam_id } = getExamData();
    try {
      const response = await fetch(
        '/exam/' + patient_id + '/' + exam_id + '/delete_image/' + encodeURIComponent(filename),
        { method: 'DELETE' }
      );
      const data = await response.json();
      if (data.status === 'success') {
        const wrapper = document.querySelector('[data-filename="' + CSS.escape(filename) + '"]');
        if (wrapper) wrapper.remove();
      } else {
        throw new Error(data.message || 'Xóa thất bại');
      }
    } catch (error) {
      console.error(error);
      alert('❌ Lỗi xóa ảnh: ' + error.message);
    }
  }

  // ── Image modal ───────────────────────────────────────────────────────────
  function openImageModal(src) {
    document.getElementById('modalImage').src = src;
    document.getElementById('imageModal').classList.add('is-active');
  }

  function closeImageModal() {
    document.getElementById('imageModal').classList.remove('is-active');
    document.getElementById('modalImage').src = '';
  }

  // ── Public API (called from template HTML / inline submit handler) ─────────
  window.closeImageModal = closeImageModal;

  window.hasPendingImages = function () {
    return pendingDT.files.length > 0;
  };

  window.scrollToPendingImages = function () {
    const box = document.getElementById('imageBox');
    if (box) box.scrollIntoView({ behavior: 'smooth', block: 'center' });
    syncWarningBanner();
  };

  // ── Init on DOM ready ─────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    const { images } = getExamData();

    // Preload existing uploaded images
    if (images && images.length > 0) {
      const gallery = document.getElementById('imageGallery');
      images.forEach(function (img) {
        gallery.appendChild(buildUploadedThumb(img.filename, img.path));
      });
    }

    // "Chọn ảnh" button → opens file picker
    document.getElementById('lab_images').addEventListener('change', function () {
      if (this.files.length) addPendingFiles(this.files);
      this.value = ''; // reset so the same file can be re-added after removal
    });

    // "Tải lên" button
    document.getElementById('uploadImagesBtn').addEventListener('click', uploadPendingFiles);

    // "Xóa ảnh chọn" button (clears pending only, not uploaded)
    document.getElementById('clearPendingBtn').addEventListener('click', clearAllPending);

    // Modal — close on background click
    const modal = document.getElementById('imageModal');
    if (modal) {
      modal.querySelector('.modal-background').addEventListener('click', closeImageModal);
    }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeImageModal();
    });
  });

})();
