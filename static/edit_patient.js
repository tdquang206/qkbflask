(function () {
    'use strict';

    const { phone: originalPhone, patient_id: patientId } = window._editPatientData;

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

    // Mirrors _normalize_phone_input() on the server exactly.
    function normalizeInput(value) {
        let s = String(value || '').trim();
        s = s.replace(/\s+/g, '_');
        s = s.replace(/[/\\]/g, '_');
        s = s.replace(/[\x00-\x1f]/g, '');
        return s;
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
        if (url.toLowerCase().endsWith('.pdf')) {
            previewPdf.src = url;
            previewPdf.style.display = 'block';
        } else {
            previewImage.src = url;
            previewImage.style.display = 'block';
        }
        fileModal.classList.add('is-active');
    }

    // Returns a DOM element — no innerHTML, safe against stored XSS.
    function buildViewButton(url, exists) {
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

    // Builds a table row using DOM APIs — no innerHTML injection.
    function buildPreviewRow(row) {
        const tr = document.createElement('tr');
        [row.kind || '', row.old_name || '', row.new_name || ''].forEach(function (text) {
            const td = document.createElement('td');
            td.textContent = text;
            tr.appendChild(td);
        });
        const tdOld = document.createElement('td');
        tdOld.appendChild(buildViewButton(row.old_url, row.old_exists));
        tr.appendChild(tdOld);
        const tdNew = document.createElement('td');
        tdNew.appendChild(buildViewButton(row.new_url, row.new_exists));
        tr.appendChild(tdNew);
        return tr;
    }

    // Builds the duplicate warning fragment using DOM APIs.
    function buildDuplicateWarning(duplicates) {
        const frag = document.createDocumentFragment();
        const strong = document.createElement('strong');
        strong.textContent = 'Phát hiện trùng SĐT/Mã với bệnh nhân khác:';
        frag.appendChild(strong);
        const ul = document.createElement('ul');
        duplicates.forEach(function (d) {
            const li = document.createElement('li');
            li.textContent = [d.kid_name, d.parent_name, d.phone].filter(Boolean).join(' - ');
            ul.appendChild(li);
        });
        frag.appendChild(ul);
        const note = document.createElement('p');
        note.className = 'mt-2';
        note.textContent = 'Placeholder hiện tại: hệ thống chặn lưu để tránh ghi đè nhầm dữ liệu.';
        frag.appendChild(note);
        return frag;
    }

    function setPreviewBodyMessage(msg) {
        previewBody.replaceChildren();
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.setAttribute('colspan', '5');
        td.textContent = msg;
        tr.appendChild(td);
        previewBody.appendChild(tr);
    }

    async function loadPreview() {
        const normalizedPhone = normalizeInput(phoneInput.value);
        const normalizedOriginal = normalizeInput(originalPhone);
        renameConfirmedInput.value = '0';
        didPreviewCurrentValue = false;

        if (normalizedPhone === normalizedOriginal) {
            setPreviewBodyMessage('Không đổi SĐT/Mã, không có file cần rename.');
            duplicateWarnBox.style.display = 'none';
            hasDuplicate = false;
            openPreviewModal();
            didPreviewCurrentValue = true;
            return;
        }

        setPreviewBodyMessage('Đang tải...');
        duplicateWarnBox.style.display = 'none';
        hasDuplicate = false;
        openPreviewModal();

        try {
            const response = await fetch(
                '/api/patient/' + encodeURIComponent(patientId) + '/phone-rename-preview',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ new_phone: phoneInput.value }),
                }
            );
            const data = await response.json();
            if (!response.ok || data.status !== 'success') {
                throw new Error(data.message || 'Preview failed');
            }

            hasDuplicate = !!data.duplicate;
            didPreviewCurrentValue = true;

            if (hasDuplicate) {
                duplicateWarnText.replaceChildren(buildDuplicateWarning(data.duplicates || []));
                duplicateWarnBox.style.display = '';
                confirmPreviewBtn.disabled = true;
            } else {
                duplicateWarnBox.style.display = 'none';
                confirmPreviewBtn.disabled = false;
            }

            const rows = data.rows || [];
            previewBody.replaceChildren();
            if (!rows.length) {
                setPreviewBodyMessage('Không có file cần đổi tên.');
                return;
            }
            rows.forEach(function (row) {
                previewBody.appendChild(buildPreviewRow(row));
            });

        } catch (err) {
            setPreviewBodyMessage('Lỗi xem trước: ' + err.message);
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
        if (!btn) return;
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
        if (!submitter || submitter.value !== 'update') return;

        const normalizedPhone = normalizeInput(phoneInput.value);
        const normalizedOriginal = normalizeInput(originalPhone);
        if (normalizedPhone === normalizedOriginal) return;

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
