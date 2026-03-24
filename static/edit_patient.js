// edit_patient.js - JS for the edit patient page
// Data (originalPhone, patientId) is injected by the template via window._editPatientData.
(function () {
    const data = window._editPatientData || {};
    const originalPhone = data.originalPhone || '';
    const patientId = data.patientId || '';

    const form = document.querySelector('form.box');
    const phoneInput = document.getElementById('phone_input');
    const renameConfirmedInput = document.getElementById('rename_confirmed');
    const previewBtn = document.getElementById('previewRenameBtn');

    const previewModal = document.getElementById('renamePreviewModal');
    const closePreviewBtn = document.getElementById('closeRenamePreview');
    const cancelPreviewBtn = document.getElementById('cancelRenameBtn');
    const confirmPreviewBtn = document.getElementById('confirmRenameBtn');
    const previewBody = document.getElementById('renamePreviewBody');
    const duplicateWarnBox = document.getElementById('duplicateWarnBox');
    const duplicateWarnText = document.getElementById('duplicateWarnText');

    const fileModal = document.getElementById('filePreviewModal');
    const closeFilePreviewBtn = document.getElementById('closeFilePreview');
    const previewImage = document.getElementById('filePreviewImage');
    const previewPdf = document.getElementById('filePreviewPdf');

    let hasDuplicate = false;
    let didPreviewCurrentValue = false;

    // Mirror server-side _normalize_phone_input: strip control chars, trim,
    // replace whitespace / '/' / '\' with underscores.
    function normalizeInput(value) {
        const str = String(value || '').replace(/[\x00-\x1F\x7F-\x9F]/g, '');
        return str.trim().replace(/[\s/\\]+/g, '_');
    }

    function closePreviewModal() {
        previewModal.classList.remove('is-active');
    }

    function openPreviewModal() {
        previewModal.classList.add('is-active');
    }

    function closeFileModal() {
        fileModal.classList.remove('is-active');
        previewImage.style.display = 'none';
        previewPdf.style.display = 'none';
        previewImage.src = '';
        previewPdf.src = '';
    }

    function openFileViewer(url) {
        if (!url) {
            alert('Không có đường dẫn để xem.');
            return;
        }
        const lower = url.toLowerCase();
        if (lower.endsWith('.pdf')) {
            previewPdf.src = url;
            previewPdf.style.display = 'block';
        } else {
            previewImage.src = url;
            previewImage.style.display = 'block';
        }
        fileModal.classList.add('is-active');
    }

    // Returns a DOM element (button or span) for viewing a file.
    function createViewButtonEl(url, exists) {
        if (!exists || !url) {
            const span = document.createElement('span');
            span.className = 'tag is-light';
            span.textContent = 'N/A';
            return span;
        }
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'button is-small is-info is-light view-file-btn';
        btn.dataset.url = url;
        btn.textContent = 'Xem';
        return btn;
    }

    // Build a single info row (colspan 5) using safe DOM APIs.
    function buildInfoRow(message) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 5;
        td.textContent = message;
        tr.appendChild(td);
        return tr;
    }

    async function loadPreview() {
        const normalizedPhone = normalizeInput(phoneInput.value);
        const normalizedOriginal = normalizeInput(originalPhone);
        renameConfirmedInput.value = '0';
        didPreviewCurrentValue = false;

        if (normalizedPhone === normalizedOriginal) {
            previewBody.textContent = '';
            previewBody.appendChild(buildInfoRow('Không đổi SĐT/Mã, không có file cần rename.'));
            duplicateWarnBox.style.display = 'none';
            hasDuplicate = false;
            openPreviewModal();
            didPreviewCurrentValue = true;
            return;
        }

        previewBody.textContent = '';
        previewBody.appendChild(buildInfoRow('Đang tải...'));
        duplicateWarnBox.style.display = 'none';
        hasDuplicate = false;
        openPreviewModal();

        try {
            const response = await fetch('/api/patient/' + encodeURIComponent(patientId) + '/phone-rename-preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_phone: phoneInput.value })
            });
            const responseData = await response.json();
            if (!response.ok || responseData.status !== 'success') {
                throw new Error(responseData.message || 'Preview failed');
            }

            hasDuplicate = !!responseData.duplicate;
            didPreviewCurrentValue = true;

            if (hasDuplicate) {
                // Build duplicate warning using safe DOM APIs to avoid XSS from stored fields.
                duplicateWarnText.textContent = '';
                const heading = document.createTextNode('Phát hiện trùng SĐT/Mã với bệnh nhân khác:');
                duplicateWarnText.appendChild(heading);
                (responseData.duplicates || []).forEach(function (d) {
                    duplicateWarnText.appendChild(document.createElement('br'));
                    duplicateWarnText.appendChild(
                        document.createTextNode((d.kid_name || '') + ' - ' + (d.parent_name || '') + ' - ' + (d.phone || ''))
                    );
                });
                duplicateWarnText.appendChild(document.createElement('br'));
                duplicateWarnText.appendChild(document.createElement('br'));
                duplicateWarnText.appendChild(document.createTextNode('Placeholder hiện tại: hệ thống chặn lưu.'));
                duplicateWarnBox.style.display = '';
                confirmPreviewBtn.disabled = true;
            } else {
                duplicateWarnBox.style.display = 'none';
                confirmPreviewBtn.disabled = false;
            }

            const rows = responseData.rows || [];
            previewBody.textContent = '';
            if (!rows.length) {
                previewBody.appendChild(buildInfoRow('Không có file cần đổi tên.'));
                return;
            }

            // Build preview rows using DOM APIs to avoid HTML injection from API fields.
            rows.forEach(function (row) {
                const tr = document.createElement('tr');

                const kindTd = document.createElement('td');
                kindTd.textContent = row.kind || '';
                tr.appendChild(kindTd);

                const oldNameTd = document.createElement('td');
                oldNameTd.textContent = row.old_name || '';
                tr.appendChild(oldNameTd);

                const newNameTd = document.createElement('td');
                newNameTd.textContent = row.new_name || '';
                tr.appendChild(newNameTd);

                const oldUrlTd = document.createElement('td');
                oldUrlTd.appendChild(createViewButtonEl(row.old_url, row.old_exists));
                tr.appendChild(oldUrlTd);

                const newUrlTd = document.createElement('td');
                newUrlTd.appendChild(createViewButtonEl(row.new_url, row.new_exists));
                tr.appendChild(newUrlTd);

                previewBody.appendChild(tr);
            });
        } catch (err) {
            previewBody.textContent = '';
            previewBody.appendChild(buildInfoRow('Lỗi xem trước: ' + (err && err.message ? err.message : '')));
            didPreviewCurrentValue = false;
        }
    }

    previewBtn.addEventListener('click', loadPreview);
    closePreviewBtn.addEventListener('click', closePreviewModal);
    cancelPreviewBtn.addEventListener('click', closePreviewModal);
    confirmPreviewBtn.addEventListener('click', function () {
        if (hasDuplicate) {
            alert('Đang bị trùng SĐT/Mã. Không thể xác nhận.');
            return;
        }
        renameConfirmedInput.value = '1';
        closePreviewModal();
        alert('Đã xác nhận. Bấm Update để lưu.');
    });

    previewBody.addEventListener('click', function (evt) {
        const btn = evt.target.closest('.view-file-btn');
        if (!btn) {
            return;
        }
        openFileViewer(btn.dataset.url);
    });

    closeFilePreviewBtn.addEventListener('click', closeFileModal);
    fileModal.querySelector('.modal-background').addEventListener('click', closeFileModal);

    phoneInput.addEventListener('input', function () {
        renameConfirmedInput.value = '0';
        didPreviewCurrentValue = false;
    });

    form.addEventListener('submit', function (evt) {
        const submitter = evt.submitter;
        if (!submitter || submitter.value !== 'update') {
            return;
        }

        const normalizedPhone = normalizeInput(phoneInput.value);
        const normalizedOriginal = normalizeInput(originalPhone);
        if (normalizedPhone === normalizedOriginal) {
            return;
        }

        if (!didPreviewCurrentValue) {
            evt.preventDefault();
            alert('Vui lòng bấm "Xem trước đổi tên file" trước khi lưu.');
            return;
        }
        if (renameConfirmedInput.value !== '1') {
            evt.preventDefault();
            alert('Vui lòng xác nhận trong cửa sổ xem trước trước khi bấm Update.');
            return;
        }
        if (hasDuplicate) {
            evt.preventDefault();
            alert('SĐT/Mã mới đang trùng với bệnh nhân khác. Placeholder hiện tại: chặn lưu.');
        }
    });
})();
