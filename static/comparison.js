/* Local comparison editor. Save requests contain references/settings, never image URLs. */
document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('patientExamHistory');
  if (!root) return;
  const api = root.dataset.comparisonUrl;
  const $ = id => document.getElementById(id);
  const C = QKBComparisonCore;
  let catalog, session, dirty = false, busy = false, ready = false, generation = 0, previousFocus, previewKey;
  const status = text => { $('comparisonStatus').textContent = text; };
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  async function request(url, body) {
    const response = await fetch(url, body === undefined ? {} : {
      method: 'POST', headers: {'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content}, body: JSON.stringify(body),
    });
    let data;
    try { data = await response.json(); } catch { throw new Error('Không đọc được phản hồi. Kiểm tra đăng nhập rồi tải lại trang.'); }
    if (!response.ok) throw new Error(data.message || 'Không thể thực hiện yêu cầu.');
    return data;
  }
  function options(select, rows, selected) {
    select.replaceChildren();
    for (const [value, label] of rows) {
      const option = el('option', label); option.value = value; select.append(option);
    }
    if (selected !== undefined) select.value = selected;
  }
  function changed(adjustment = false) {
    dirty = true; previewKey = null; $('comparisonNotePreview').hidden = true;
    $('comparisonSaveState').textContent = 'Có thay đổi chưa lưu';
    if (adjustment) {
      for (const rating of Object.values(session.assessments)) rating.reviewed = false;
      document.querySelectorAll('.grading-reviewed').forEach(input => { input.checked = false; });
      updateScores();
    }
  }
  function switchView(view) {
    $('comparisonLayout').dataset.view = view;
    $('comparisonImageStage').hidden = view === 'save';
    $('comparisonAdjustToolbar').hidden = view !== 'adjust';
    $('comparisonGradeSection').hidden = view !== 'grade';
    $('comparisonSaveSection').hidden = view !== 'save';
    document.querySelectorAll('[data-comparison-view]').forEach(button => {
      const active = button.dataset.comparisonView === view;
      button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1;
    });
    requestAnimationFrame(() => session?.images.forEach(item => { if (item.canvas) layoutImage(item); }));
  }
  const tabs = [...document.querySelectorAll('[data-comparison-view]')];
  tabs.forEach((button, index) => {
    button.addEventListener('click', () => switchView(button.dataset.comparisonView));
    button.addEventListener('keydown', event => {
      const direction = {ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1}[event.key];
      if (!direction && !['Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1) : tabs[(index + direction + tabs.length) % tabs.length];
      switchView(next.dataset.comparisonView); next.focus();
    });
  });
  function payload() {
    return {
      revision: catalog.revision,
      images: session.images.map(item => ({image_id: item.id, transform: item.transform})),
      reference_image_id: $('referenceImage').value, baseline_exam_id: $('baselineExam').value,
      target_exam_id: $('targetExam').value,
      assessments: $('enableGrading').checked ? session.assessments : {},
      comment: $('comparisonComment').value,
      save_copies: $('saveEditedCopies').checked, save_sheet: $('saveComparisonSheet').checked,
      append_note: $('appendComparisonNote').checked,
    };
  }
  function selectionChanged() {
    const count = document.querySelectorAll('.compare-checkbox:checked').length;
    $('compareControls').style.display = count ? 'flex' : 'none';
    $('compareCount').textContent = count;
  }
  document.querySelectorAll('.compare-checkbox').forEach(cb => cb.addEventListener('change', selectionChanged));
  $('clearSelectionBtn').addEventListener('click', () => {
    document.querySelectorAll('.compare-checkbox').forEach(cb => { cb.checked = false; }); selectionChanged();
  });
  $('compareBtn').addEventListener('click', () => openComparison(
    [...document.querySelectorAll('.compare-checkbox:checked')].map(cb => cb.dataset.imageId)));
  document.querySelectorAll('.reopen-comparison').forEach(button => {
    button.addEventListener('click', () => openComparison(null, button.dataset.comparisonId));
  });
  document.querySelectorAll('.delete-comparison').forEach(button => {
    button.addEventListener('click', async () => {
      if (!confirm('Xóa bản so sánh này? Ảnh đính kèm và ghi chú sẽ được giữ lại.')) return;
      button.disabled = true;
      try { await request(`${api}/${encodeURIComponent(button.dataset.comparisonId)}/delete`, {}); location.reload(); }
      catch (error) { alert(error.message); button.disabled = false; }
    });
  });
  async function openComparison(ids, recordId) {
    if (busy) return;
    if (ids && (ids.length < 1 || ids.length > 8)) { alert('Chọn từ 1 đến 8 ảnh.'); return; }
    previousFocus = document.activeElement;
    const token = ++generation;
    $('compareModal').classList.add('is-active');
    document.documentElement.classList.add('is-clipped');
    $('closeComparison').focus();
    session?.images.forEach(item => item.resizeObserver?.disconnect()); session = null;
    $('saveComparison').disabled = true; busy = true; dirty = false; ready = false;
    $('comparisonLayout').inert = true;
    $('comparisonSaveState').textContent = 'Chưa có thay đổi';
    switchView('adjust');
    $('compareGrid').replaceChildren(); $('gradingPanel').replaceChildren();
    status('Đang tải ảnh…');
    try {
      catalog = await request(api);
      const record = recordId ? catalog.records.find(r => r.id === recordId) : null;
      if (recordId && !record) throw new Error('Bản so sánh đã bị xóa.');
      if (record && (record.schema_version !== 1 || record.transform_version !== 1)) throw new Error('Phiên bản so sánh chưa được hỗ trợ.');
      if (record) ids = record.images.map(i => i.image_id);
      const images = ids.map(id => {
        const image = catalog.images.find(i => i.id === id && i.kind === 'original');
        if (!image) throw new Error('Ảnh nguồn đã bị xóa hoặc đổi. Tải lại trang để kiểm tra.');
        const saved = record?.images.find(i => i.image_id === id);
        return {...image, transform: structuredClone(saved?.transform || C.defaults())};
      });
      const visits = catalog.exams.filter(e => images.some(i => i.exam_id === e.id)).sort((a, b) => a.date.localeCompare(b.date));
      session = {images, visits, assessments: structuredClone(record?.assessments || {})};
      options($('referenceImage'), images.map(i => [i.id, `${i.date} · ${i.filename}`]), record?.reference_image_id || images[0].id);
      options($('baselineExam'), visits.map(e => [e.id, `${e.date} · ${e.id.slice(0, 8)}`]), record?.baseline_exam_id || visits[0].id);
      options($('targetExam'), catalog.exams.map(e => [e.id, `${e.date} · ${e.id.slice(0, 8)}`]), record?.target_exam_id || visits.at(-1).id);
      options($('gradingMethod'), catalog.methods.map(m => [m.id, `${m.label} v${m.version}`]));
      $('enableGrading').checked = Object.keys(session.assessments).length > 0;
      $('comparisonComment').value = record?.comment || '';
      $('showOriginal').checked = false;
      $('showReferencePatches').checked = true;
      for (const key of ['saveEditedCopies', 'saveComparisonSheet', 'appendComparisonNote']) $(key).checked = false;
      $('comparisonNotePreview').hidden = true; previewKey = null;
      await Promise.all(images.map(loadImage));
      if (token !== generation) return;
      images.forEach(buildCard); buildGrading();
      ready = true;
      status(record ? 'Đã mở bản lưu. Thay đổi sẽ được lưu thành phiên bản mới.' : 'Chọn ảnh chuẩn, kiểm tra vùng so sánh và điều chỉnh nếu cần.');
      $('saveComparison').disabled = false;
    } catch (error) { status(error.message); }
    finally { busy = false; $('comparisonLayout').inert = false; }
  }
  async function loadImage(item) {
    const image = new Image(); image.src = item.url;
    await image.decode();
    const scale = Math.min(1, 1000 / Math.max(image.naturalWidth, image.naturalHeight));
    item.raw = document.createElement('canvas');
    item.raw.width = Math.max(1, Math.round(image.naturalWidth * scale));
    item.raw.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const ctx = item.raw.getContext('2d', {willReadFrequently: true});
    ctx.drawImage(image, 0, 0, item.raw.width, item.raw.height);
    item.pixels = ctx.getImageData(0, 0, item.raw.width, item.raw.height);
    item.adjusted = document.createElement('canvas');
    item.adjusted.width = item.raw.width; item.adjusted.height = item.raw.height;
  }
  function render(item) {
    const canvas = item.canvas, transform = item.transform;
    canvas.classList.toggle('is-selecting', ['patch', 'crop'].includes(item.selectionMode));
    const raw = $('showOriginal').checked || item.selectionMode;
    const crop = item.selectionMode ? null : transform.crop;
    const [x, y, w, h] = crop || [0, 0, 1, 1];
    const sx = Math.floor(x * item.raw.width), sy = Math.floor(y * item.raw.height);
    const sw = Math.max(1, Math.floor((x + w) * item.raw.width) - sx);
    const sh = Math.max(1, Math.floor((y + h) * item.raw.height) - sy);
    canvas.width = sw; canvas.height = sh;
    if (!raw) item.adjusted.getContext('2d').putImageData(new ImageData(
      C.adjust(item.pixels.data, transform), item.raw.width, item.raw.height), 0, 0);
    canvas.getContext('2d').drawImage(raw ? item.raw : item.adjusted, sx, sy, sw, sh, 0, 0, sw, sh);
    item.card.classList.toggle('is-reference', item.id === $('referenceImage').value);
    item.caption.textContent = `${raw ? 'Ảnh gốc' : 'Đã hiệu chỉnh'}${crop ? ' · Đã cắt vùng' : ''}${transform.patch ? ' · Có vùng tham chiếu' : ''}`;
    if (transform.patch && crop && !C.projectPatch(transform.patch, crop)) item.caption.textContent += ' (ngoài vùng cắt)';
    layoutImage(item);
    drawOverlays(item);
  }
  function layoutImage(item) {
    if (!item.viewport.clientWidth || !item.canvas.width) return;
    // Reserve a few pixels so fractional sizes cannot create scrollbars at Fit.
    const size = C.fitSize(item.canvas.width, item.canvas.height,
      Math.max(1, item.viewport.clientWidth - 4), Math.max(1, item.viewport.clientHeight - 4), item.zoom || 1);
    item.canvas.style.width = `${size.width}px`; item.canvas.style.height = `${size.height}px`;
    item.stack.style.width = `${size.width}px`; item.stack.style.height = `${size.height}px`;
    if ((item.zoom || 1) === 1) { item.viewport.scrollLeft = 0; item.viewport.scrollTop = 0; }
  }
  function drawOverlays(item, draft = null) {
    const width = item.canvas.width, height = item.canvas.height;
    const unit = width / (parseFloat(item.canvas.style.width) || width);
    item.overlay.replaceChildren(); item.overlay.setAttribute('viewBox', `0 0 ${width} ${height}`);
    const crop = item.selectionMode ? [0, 0, 1, 1] : item.transform.crop || [0, 0, 1, 1];
    const draw = (patch, text, color, dashed) => {
      const rect = C.projectPatch(patch, crop); if (!rect) return;
      const [x, y, w, h] = [rect[0] * width, rect[1] * height, rect[2] * width, rect[3] * height];
      const shape = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      for (const [key, value] of Object.entries({x, y, width: w, height: h, fill: 'none', stroke: color, 'stroke-width': 2, 'vector-effect': 'non-scaling-stroke'})) shape.setAttribute(key, value);
      if (dashed) shape.setAttribute('stroke-dasharray', '8 5');
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', x + 4 * unit); label.setAttribute('y', y + 16 * unit); label.setAttribute('fill', color);
      label.setAttribute('font-size', 13 * unit); label.setAttribute('paint-order', 'stroke'); label.setAttribute('stroke', '#101418'); label.setAttribute('stroke-width', 3 * unit); label.textContent = text;
      item.overlay.append(shape, label);
    };
    if ($('showReferencePatches').checked) draw(item.transform.patch, 'Tham chiếu', '#67ffe0', false);
    (item.candidates || []).forEach((patch, index) => draw(patch, String(index + 1), '#ffcf70', true));
    if (draft) draw(draft, 'Đang chọn', '#ffffff', true);
  }
  function fitImage(item) {
    item.zoom = 1; item.zoomInput.value = 100; item.zoomOutput.textContent = '100%';
    layoutImage(item);
  }
  function buildCard(item) {
    item.card = el('article', undefined, 'comparison-card');
    const title = el('strong', `${item.date} · ${item.filename}`); title.title = `${item.date} · ${item.filename}`; item.card.append(title);
    item.caption = el('p', '', 'help'); item.card.append(item.caption);
    const viewport = item.viewport = el('div', undefined, 'comparison-viewport');
    item.canvas = el('canvas'); item.canvas.setAttribute('aria-label', 'Ảnh so sánh ' + item.date);
    const surface = el('div', undefined, 'comparison-surface');
    item.stack = el('div', undefined, 'comparison-canvas-stack');
    item.overlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    item.overlay.classList.add('comparison-overlay'); item.overlay.setAttribute('preserveAspectRatio', 'none'); item.overlay.setAttribute('aria-hidden', 'true');
    item.stack.append(item.canvas, item.overlay); surface.append(item.stack); viewport.append(surface); item.card.append(viewport);
    for (const [key, labelText, min, max, step] of [
      ['brightness', 'Độ sáng', -.3, .3, .01], ['contrast', 'Tương phản', .5, 1.5, .01],
    ]) {
      const label = el('label', labelText), input = el('input'), output = el('output');
      input.type = 'range'; input.min = min; input.max = max; input.step = step; input.value = item.transform[key];
      output.textContent = input.value; item[key + 'Input'] = input;
      input.addEventListener('input', () => {
        const repaint = $('showOriginal').checked ? [...session.images] : [item];
        item.transform[key] = Number(input.value); output.textContent = input.value;
        $('showOriginal').checked = false;
        changed(true); requestAnimationFrame(() => repaint.forEach(render));
      });
      label.append(input, output); item.card.append(label);
    }
    const zoomLabel = el('label', 'Phóng to'), zoom = el('input');
    zoom.type = 'range'; zoom.min = 100; zoom.max = 300; zoom.value = 100;
    item.zoomInput = zoom; item.zoomOutput = el('output', '100%'); item.zoom = 1;
    zoom.addEventListener('input', () => { item.zoom = Number(zoom.value) / 100; item.zoomOutput.textContent = zoom.value + '%'; layoutImage(item); });
    zoomLabel.append(zoom, item.zoomOutput); item.card.append(zoomLabel);
    const buttons = el('div', undefined, 'buttons');
    for (const [text, action] of [
      ['Vừa khung', () => fitImage(item)],
      ['Chọn vùng tham chiếu', () => selectMode('patch')],
      ['Gợi ý vùng', () => suggestPatches(item)],
      ['Xóa vùng tham chiếu', () => { item.transform.patch = null; clearCandidates(item); item.selectionMode = null; changed(true); render(item); }],
      ['Cắt vùng so sánh', () => selectMode('crop')],
      ['Bỏ cắt', () => { item.transform.crop = null; item.selectionMode = null; changed(true); render(item); }],
      ['Đặt lại', () => { item.transform = C.defaults(); item.selectionMode = null; clearCandidates(item); syncSliders(item); changed(true); render(item); fitImage(item); }],
    ]) { const button = el('button', text, 'button'); button.type = 'button'; button.addEventListener('click', action); buttons.append(button); }
    function selectMode(mode) {
      clearCandidates(item); item.selectionMode = mode; render(item); fitImage(item);
      item.canvas.classList.add('is-selecting');
      status(mode === 'patch' ? 'Kéo một hình chữ nhật trên ảnh gốc để chọn vùng tham chiếu.' : 'Kéo một hình chữ nhật trên ảnh gốc để chọn vùng cắt.');
    }
    item.card.append(buttons);
    item.suggestions = el('div', undefined, 'comparison-suggestions'); item.card.append(item.suggestions);
    let start, pan;
    const point = event => {
      const bounds = item.canvas.getBoundingClientRect();
      return [Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
              Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height))];
    };
    item.canvas.addEventListener('pointerdown', event => {
      if (!['patch', 'crop'].includes(item.selectionMode)) {
        pan = {x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop};
        item.canvas.setPointerCapture(event.pointerId); return;
      }
      start = point(event); item.canvas.setPointerCapture(event.pointerId);
    });
    item.canvas.addEventListener('pointermove', event => {
      if (pan) { viewport.scrollLeft = pan.left - event.clientX + pan.x; viewport.scrollTop = pan.top - event.clientY + pan.y; return; }
      if (!start) return;
      const end = point(event);
      drawOverlays(item, [Math.min(start[0], end[0]), Math.min(start[1], end[1]), Math.abs(start[0] - end[0]), Math.abs(start[1] - end[1])]);
    });
    item.canvas.addEventListener('pointerup', event => {
      if (pan) { pan = null; return; }
      if (!start) return;
      const end = point(event), rect = [Math.min(start[0], end[0]), Math.min(start[1], end[1]),
                                      Math.abs(start[0] - end[0]), Math.abs(start[1] - end[1])];
      start = null;
      if (rect[2] < .01 || rect[3] < .01) { status('Vùng quá nhỏ. Kéo lại để chọn vùng lớn hơn.'); render(item); return; }
      item.transform[item.selectionMode] = rect; item.selectionMode = null;
      item.canvas.classList.remove('is-selecting');
      $('showReferencePatches').checked = true;
      changed(true); render(item); status('Đã chọn vùng.');
    });
    item.canvas.addEventListener('pointercancel', () => { start = null; pan = null; render(item); });
    $('compareGrid').append(item.card); render(item);
    item.resizeObserver = new ResizeObserver(() => layoutImage(item)); item.resizeObserver.observe(viewport);
  }
  function clearCandidates(item) { item.candidates = []; item.suggestions?.replaceChildren(); }
  function suggestPatches(item) {
    item.selectionMode = 'suggest'; fitImage(item);
    try { item.candidates = C.patchCandidates(item.pixels.data, item.raw.width, item.raw.height); }
    catch { item.candidates = []; }
    item.suggestions.replaceChildren();
    item.suggestions.append(el('p', item.candidates.length ? 'Chọn vùng tương ứng trên các ảnh. Gợi ý chỉ dựa trên độ sáng/độ đều, không xác định da lành.' : 'Không có vùng phù hợp. Hãy tự chọn vùng tham chiếu.', 'help'));
    item.candidates.forEach((patch, index) => {
      const button = el('button', `Dùng vùng ${index + 1}`, 'button is-small'); button.type = 'button';
      button.addEventListener('click', () => {
        item.transform.patch = [...patch]; item.selectionMode = null; clearCandidates(item);
        $('showReferencePatches').checked = true; changed(true); render(item);
        status('Đã chọn vùng gợi ý. Kiểm tra vùng tương ứng trên ảnh còn lại.');
      }); item.suggestions.append(button);
    });
    const cancel = el('button', 'Ẩn gợi ý', 'button is-small'); cancel.type = 'button';
    cancel.addEventListener('click', () => { clearCandidates(item); item.selectionMode = null; render(item); }); item.suggestions.append(cancel);
    render(item);
  }
  function syncSliders(item) {
    for (const key of ['brightness', 'contrast']) {
      item[key + 'Input'].value = item.transform[key];
      item[key + 'Input'].nextElementSibling.textContent = item.transform[key];
    }
  }
  $('normalizeImages').addEventListener('click', () => {
    if (!session || busy) return;
    if (session.images.some(i => !i.transform.patch)) { status('Chọn vùng tham chiếu trên từng ảnh, bao gồm ảnh chuẩn.'); return; }
    try {
      const reference = session.images.find(i => i.id === $('referenceImage').value);
      const target = C.stats(C.adjust(reference.pixels.data, reference.transform), reference.raw.width, reference.raw.height, reference.transform.patch);
      $('showOriginal').checked = false;
      session.images.forEach(item => {
        if (item === reference) return;
        const stats = C.stats(item.pixels.data, item.raw.width, item.raw.height, item.transform.patch);
        Object.assign(item.transform, C.suggest(stats, target)); syncSliders(item);
      });
      session.images.forEach(render);
      changed(true); status('Đã gợi ý cân sáng. Kiểm tra ảnh gốc/đã chỉnh và xác nhận lại đánh giá trước khi lưu.');
    } catch (error) { status(error.message); }
  });
  $('referenceImage').addEventListener('change', () => { if (session) { changed(true); session.images.forEach(render); } });
  $('showOriginal').addEventListener('change', () => { if (session) session.images.forEach(render); });
  $('showReferencePatches').addEventListener('change', () => { if (session) session.images.forEach(item => drawOverlays(item)); });
  $('baselineExam').addEventListener('change', () => { changed(); updateScores(); });
  for (const id of ['targetExam', 'comparisonComment', 'saveEditedCopies', 'saveComparisonSheet', 'appendComparisonNote']) {
    $(id).addEventListener('input', () => changed());
  }
  $('enableGrading').addEventListener('change', () => {
    changed(); buildGrading();
    if ($('enableGrading').checked) { $('showOriginal').checked = true; session.images.forEach(render); }
  });
  $('gradingMethod').addEventListener('change', () => { session.assessments = {}; changed(); buildGrading(); });
  function buildGrading() {
    const panel = $('gradingPanel'); panel.replaceChildren(); panel.hidden = !$('enableGrading').checked;
    if (panel.hidden) { updateScores(); return; }
    const method = catalog.methods.find(m => m.id === $('gradingMethod').value);
    panel.append(el('p', 'Bác sĩ nhập quan sát. Để trống vùng chưa đánh giá; không suy ra toàn bộ khuôn mặt từ một ảnh cục bộ.', 'help'));
    panel.append(el('p', method.formula, 'help'));
    const link = el('a', 'Tài liệu phương pháp'); link.href = method.source; link.target = '_blank'; link.rel = 'noopener'; panel.append(link);
    session.visits.forEach(visit => {
      const rating = session.assessments[visit.id] ||= {method: method.id, version: method.version, inputs: {}, view: 'original', reviewed: false};
      const block = el('div', undefined, 'grading-visit'); block.dataset.examId = visit.id;
      block.append(el('strong', `${visit.date} · ${visit.id.slice(0, 8)}`));
      const viewLabel = el('label', ' Đánh giá dựa trên '), view = el('select', undefined, 'input');
      options(view, [['original', 'Ảnh gốc'], ['adjusted', 'Ảnh đã chỉnh']], rating.view);
      view.addEventListener('change', () => {
        rating.view = view.value; rating.reviewed = false; reviewed.checked = false;
        $('showOriginal').checked = view.value === 'original'; session.images.forEach(render);
        changed(); updateScores();
      });
      viewLabel.append(view); block.append(viewLabel);
      const table = el('table'), head = el('tr'); head.append(el('th', 'Vùng'));
      method.fields.forEach(f => head.append(el('th', f.label))); table.append(head);
      method.regions.forEach(region => {
        const row = el('tr'); row.append(el('td', region.label));
        const values = rating.inputs[region.id] ||= {};
        method.fields.forEach(field => {
          const cell = el('td'), select = el('select', undefined, 'input');
          select.setAttribute('aria-label', `${visit.date} ${region.label} ${field.label}`);
          options(select, [['', 'Chưa đánh giá'], ...field.options.map((label, i) => [String(i), label])], values[field.id] ?? '');
          select.addEventListener('change', () => {
            values[field.id] = select.value === '' ? null : Number(select.value);
            rating.reviewed = false; reviewed.checked = false; changed(); updateScores();
          });
          cell.append(select); row.append(cell);
        }); table.append(row);
      });
      block.append(table);
      const reviewLabel = el('label'), reviewed = el('input'); reviewed.type = 'checkbox'; reviewed.className = 'grading-reviewed'; reviewed.checked = rating.reviewed;
      reviewed.addEventListener('change', () => { rating.reviewed = reviewed.checked; changed(); updateScores(); });
      reviewLabel.append(reviewed, document.createTextNode(' Tôi đã kiểm tra đủ các vùng và xác nhận đánh giá này.'));
      block.append(reviewLabel, el('p', '', 'grading-result')); panel.append(block);
    });
    updateScores();
  }
  function updateScores() {
    if (!catalog || !session) return;
    const method = catalog.methods.find(m => m.id === $('gradingMethod').value);
    const base = session.assessments[$('baselineExam').value];
    const baseScore = base?.reviewed ? C.score(method, base.inputs) : null;
    const enabled = $('enableGrading').checked;
    const completed = Object.values(session.assessments).filter(r => r.reviewed && C.score(method, r.inputs) !== null).length;
    $('gradingTabStatus').textContent = !enabled ? 'Chưa chấm' : completed === session.visits.length ? 'Đã xác nhận' : 'Chưa hoàn tất';
    const baselineDate = session.visits.find(v => v.id === $('baselineExam').value)?.date || '';
    $('gradingBaselineStatus').textContent = !enabled ? 'Bật chấm điểm để so sánh điểm giữa các lần khám. Mốc điểm không thay đổi ánh sáng.' :
      baseScore === null ? `Mốc ${baselineDate}: chưa đủ điểm đã xác nhận để so sánh.` : `Mốc ${baselineDate}: ${method.label} ${baseScore}/${method.maximum}. So sánh với các lần đã xác nhận cùng loại ảnh.`;
    document.querySelectorAll('.grading-visit').forEach(block => {
      const rating = session.assessments[block.dataset.examId], score = C.score(method, rating.inputs);
      let text = score === null ? 'Chưa hoàn tất — thiếu quan sát.' : `${method.label}: ${score} / ${method.maximum}${rating.reviewed ? '' : ' — cần xác nhận'}`;
      if (score !== null && rating.reviewed && baseScore !== null && block.dataset.examId !== $('baselineExam').value) {
        if (rating.view === base.view) { const delta = Math.round((score - baseScore) * 100) / 100; text += ` · So với mốc: ${delta > 0 ? '+' : ''}${delta}`; }
        else text += ' · Khác loại ảnh đánh giá với mốc; không tính chênh lệch.';
      }
      block.querySelector('.grading-result').textContent = text;
    });
  }
  $('previewComparisonNote').addEventListener('click', async () => {
    if (!session || busy) return;
    const body = payload();
    try {
      const result = await request(api + '/summary', body);
      if (JSON.stringify(payload()) !== JSON.stringify(body)) return;
      $('comparisonNotePreview').textContent = result.summary; $('comparisonNotePreview').hidden = false;
      previewKey = JSON.stringify(body);
    } catch (error) { status(error.message); }
  });
  async function saveAndClose() {
    if (busy || !session || !ready) return;
    $('comparisonClosePrompt').close();
    const body = payload();
    if (body.append_note && previewKey !== JSON.stringify(body)) {
      switchView('save'); $('previewComparisonNote').focus();
      status('Bấm “Xem trước tóm tắt” và kiểm tra nội dung trước khi thêm vào ghi chú.'); return;
    }
    busy = true; $('saveComparison').disabled = true; $('comparisonLayout').inert = true; status('Đang lưu bản so sánh…');
    try { await request(api, body); dirty = false; location.reload(); }
    catch (error) { busy = false; $('comparisonLayout').inert = false; $('saveComparison').disabled = false; status(error.message); }
  }
  $('saveComparison').addEventListener('click', saveAndClose);
  $('comparisonSaveAndClose').addEventListener('click', saveAndClose);
  function discardAndClose() {
    if (busy) return;
    $('comparisonClosePrompt').close();
    session?.images.forEach(item => item.resizeObserver?.disconnect());
    generation++; $('compareModal').classList.remove('is-active'); document.documentElement.classList.remove('is-clipped');
    $('compareGrid').replaceChildren(); session = null; dirty = false; ready = false; previousFocus?.focus();
  }
  function close() {
    if (busy) { status('Vui lòng chờ thao tác hiện tại hoàn tất.'); return; }
    if (!session || !ready) { discardAndClose(); return; }
    $('comparisonCloseMessage').textContent = dirty ? 'Bạn có thay đổi chưa lưu. Chọn lưu hoặc bỏ các thay đổi của lần chỉnh này.' : 'Bạn có thể lưu một bản so sánh mới, hoặc đóng mà không lưu.';
    $('comparisonClosePrompt').showModal();
  }
  $('comparisonDiscard').addEventListener('click', discardAndClose);
  $('comparisonContinue').addEventListener('click', () => $('comparisonClosePrompt').close());
  $('closeComparison').addEventListener('click', close);
  $('compareModal').querySelector('.modal-background').addEventListener('click', close);
  document.addEventListener('keydown', event => {
    if (!$('compareModal').classList.contains('is-active')) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      if ($('comparisonClosePrompt').open) $('comparisonClosePrompt').close(); else close();
    }
    if (event.key === 'Tab') {
      const container = $('comparisonClosePrompt').open ? $('comparisonClosePrompt') : $('compareModal');
      const nodes = [...container.querySelectorAll('button:not(:disabled), input, select, textarea, a[href]')].filter(n => n.getClientRects().length && n.tabIndex >= 0 && !n.closest('[inert]'));
      if (event.shiftKey && document.activeElement === nodes[0]) { event.preventDefault(); nodes.at(-1).focus(); }
      else if (!event.shiftKey && document.activeElement === nodes.at(-1)) { event.preventDefault(); nodes[0].focus(); }
    }
  });
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
});
