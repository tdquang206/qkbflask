/* Local-only grid composition using the patient-owned catalog and vendored Konva. */
document.addEventListener('DOMContentLoaded', () => {
  const $ = id => document.getElementById(id);
  const dialog = $('imageGridDialog');
  if (!dialog) return;
  const C = QKBImageGridCore;
  let stage, layer, ui, slots = [], texts = [], geometry, selectedCell = 0, selectedText = null;
  let generation = 0, textSequence = 0, previousFocus, dirty = false, loading = false;
  const status = message => { $('imageGridStatus').textContent = message; };
  const controls = enabled => {
    $('imageGridControls').inert = !enabled;
    $('gridDownload').disabled = !enabled;
    $('gridViewZoom').disabled = !enabled;
  };
  function options(id, rows, value) {
    $(id).replaceChildren(...rows.map(([key, label]) => {
      const option = document.createElement('option'); option.value = key; option.textContent = label; return option;
    }));
    $(id).value = value;
  }
  function cellLabels() {
    return slots.map((item, i) => [String(i), `Ô ${i + 1} · ${item ? item.source.date + ' · ' + item.source.filename : 'Trống'}`]);
  }
  function syncCellControls() {
    const rows = cellLabels();
    options('gridCell', rows, String(selectedCell));
    options('gridSwapTarget', rows.filter(([key]) => Number(key) !== selectedCell), String(selectedCell === 0 ? 1 : 0));
    $('gridSwap').disabled = slots.length < 2;
    const item = slots[selectedCell];
    for (const id of ['gridFitMode', 'gridImageZoom', 'gridImageZoomIn', 'gridImageZoomOut', 'gridResetImage']) $(id).disabled = !item;
    $('gridFitMode').value = item?.fit || 'contain';
    $('gridImageZoom').value = Math.round((item?.zoom || 1) * 100);
    $('gridImageZoomValue').textContent = `${$('gridImageZoom').value}%`;
  }
  function syncTextControls() {
    options('gridTextSelection', [['', 'Chữ mới'], ...texts.map(t => [t.id, t.text.slice(0, 40) || '(Trống)'])], selectedText || '');
    const text = texts.find(t => t.id === selectedText);
    $('gridText').value = text?.text || '';
    $('gridTextSize').value = text?.size || 28;
    $('gridTextColor').value = text?.color || '#111111';
    $('gridDeleteText').disabled = !text;
  }
  function selectCell(index) {
    selectedCell = index; selectedText = null;
    syncCellControls(); syncTextControls(); drawSelection();
  }
  function drawSelection() {
    ui.destroyChildren();
    if (!geometry || selectedText !== null) { ui.batchDraw(); return; }
    ui.add(new Konva.Rect({x: geometry.gap + (selectedCell % geometry.columns) * (geometry.cellWidth + geometry.gap),
      y: geometry.gap + Math.floor(selectedCell / geometry.columns) * (geometry.cellHeight + geometry.gap),
      width: geometry.cellWidth, height: geometry.cellHeight, stroke: '#1689ff', strokeWidth: 4, listening: false}));
    ui.batchDraw();
  }
  function previewScale() {
    if (!stage || !geometry) return;
    const viewport = $('gridViewport');
    const scale = $('gridViewZoom').value === 'fit' ? Math.max(.05, Math.min(1,
      (viewport.clientWidth - 24) / geometry.width, (viewport.clientHeight - 24) / geometry.height)) : Number($('gridViewZoom').value);
    stage.size({width: Math.ceil(geometry.width * scale), height: Math.ceil(geometry.height * scale)});
    stage.scale({x: scale, y: scale}); stage.batchDraw();
  }
  function render() {
    layer.destroyChildren();
    layer.add(new Konva.Rect({width: geometry.width, height: geometry.height, fill: $('gridBackground').value, listening: false}));
    slots.forEach((item, index) => {
      const cw = geometry.cellWidth, ch = geometry.cellHeight;
      const group = new Konva.Group({x: geometry.gap + (index % geometry.columns) * (cw + geometry.gap),
        y: geometry.gap + Math.floor(index / geometry.columns) * (ch + geometry.gap), clipX: 0, clipY: 0, clipWidth: cw, clipHeight: ch});
      layer.add(group);
      const hitArea = new Konva.Rect({width: cw, height: ch, fill: $('gridBackground').value});
      group.add(hitArea);
      group.on('click tap', () => selectCell(index));
      if (!item) return;
      const position = C.placement(item.image.width, item.image.height, cw, ch, item);
      const node = new Konva.Image({image: item.image, ...position, draggable: true});
      group.add(node);
      node.on('dragstart', () => selectCell(index));
      node.on('dragmove', () => {
        node.x(C.clamp(node.x(), Math.min(0, cw - node.width()), Math.max(0, cw - node.width())));
        node.y(C.clamp(node.y(), Math.min(0, ch - node.height()), Math.max(0, ch - node.height())));
      });
      node.on('dragend', () => {
        C.rememberPosition(item, node.x(), node.y(), node.width(), node.height(), cw, ch); dirty = true;
      });
    });
    texts.forEach(text => {
      const node = new Konva.Text({text: text.text, x: text.x * geometry.width, y: text.y * geometry.height,
        fontSize: text.size, fontFamily: 'Arial', fill: text.color, draggable: true, padding: 4});
      // Short labels can reach the right edge; long labels wrap within the canvas.
      node.width(Math.min(node.width(), geometry.width));
      layer.add(node);
      node.x(C.clamp(node.x(), 0, Math.max(0, geometry.width - node.width())));
      node.y(C.clamp(node.y(), 0, Math.max(0, geometry.height - node.height())));
      text.x = node.x() / geometry.width; text.y = node.y() / geometry.height;
      node.on('click tap dragstart', () => { selectedText = text.id; syncTextControls(); drawSelection(); });
      node.on('dragmove', () => {
        node.x(C.clamp(node.x(), 0, Math.max(0, geometry.width - node.width())));
        node.y(C.clamp(node.y(), 0, Math.max(0, geometry.height - node.height())));
      });
      node.on('dragend', () => { text.x = node.x() / geometry.width; text.y = node.y() / geometry.height; dirty = true; });
    });
    drawSelection(); previewScale();
    $('gridDimensions').textContent = `${geometry.width} × ${geometry.height} px`;
  }
  async function loadImage(source) {
    const url = new URL(source.url, window.location.href);
    if (url.origin !== window.location.origin || !url.pathname.startsWith('/uploads/')) throw Error('Đường dẫn ảnh không hợp lệ.');
    const image = new Image(); image.src = url.href;
    try { await image.decode(); } catch { throw Error(`Không tải được ảnh ${source.filename}. Thử lại hoặc kiểm tra đăng nhập.`); }
    if (!image.naturalWidth || !image.naturalHeight) throw Error('Ảnh nguồn không hợp lệ.');
    // A 1600px source covers a 400px cell at the maximum 4x zoom, while
    // bounding retained image memory for grids of up to 36 camera photographs.
    const ratio = Math.min(1, 1600 / Math.max(image.naturalWidth, image.naturalHeight));
    const pixels = document.createElement('canvas');
    pixels.width = Math.max(1, Math.round(image.naturalWidth * ratio));
    pixels.height = Math.max(1, Math.round(image.naturalHeight * ratio));
    pixels.getContext('2d').drawImage(image, 0, 0, pixels.width, pixels.height);
    return {source, image: pixels, fit: 'contain', zoom: 1, dx: 0, dy: 0};
  }
  $('imageGridBtn').addEventListener('click', async () => {
    const ids = [...document.querySelectorAll('.compare-checkbox:checked')].map(cb => cb.dataset.imageId);
    if (ids.length < 1 || ids.length > 36) { alert('Chọn từ 1 đến 36 ảnh để tạo lưới.'); return; }
    previousFocus = $('imageToolsBtn');
    dialog.showModal(); $('closeImageGrid').focus();
    const token = ++generation; loading = true; controls(false); dirty = false;
    stage?.destroy(); stage = null; slots = []; texts = []; selectedCell = 0; selectedText = null;
    $('gridCanvas').replaceChildren(); status('Đang tải ảnh…');
    try {
      if (typeof Konva === 'undefined') throw Error('Không tải được thư viện lưới ảnh. Tải lại trang để thử lại.');
      const response = await fetch($('patientExamHistory').dataset.comparisonUrl);
      if (!response.ok) throw Error('Không tải được ảnh. Kiểm tra đăng nhập rồi thử lại.');
      const catalog = await response.json();
      const sources = ids.map(id => catalog.images.find(img => img.id === id && img.kind === 'original'));
      if (sources.some(source => !source)) throw Error('Ảnh đã bị xóa hoặc không còn trong hồ sơ. Tải lại trang.');
      // Load sequentially so large selections do not decode all full-resolution files at once.
      const loaded = [];
      for (const source of sources) {
        if (token !== generation) return;
        loaded.push(await loadImage(source));
      }
      if (token !== generation) return;
      const columns = Math.ceil(Math.sqrt(ids.length)), rows = Math.ceil(ids.length / columns);
      $('gridRows').value = rows; $('gridColumns').value = columns;
      $('gridAspect').value = 'square'; $('gridGap').value = 8; $('gridBackground').value = '#ffffff'; $('gridViewZoom').value = 'fit';
      geometry = C.layout(rows, columns); slots = C.resizeSlots(loaded, geometry.capacity);
      stage = new Konva.Stage({container: 'gridCanvas', width: geometry.width, height: geometry.height});
      layer = new Konva.Layer(); ui = new Konva.Layer({listening: false}); stage.add(layer, ui);
      syncCellControls(); syncTextControls(); render(); controls(true);
      status(`${ids.length} ảnh đã sẵn sàng. Chọn ô để chỉnh hoặc đổi chỗ.`);
    } catch (error) { if (token === generation) status(error.message); }
    finally { if (token === generation) loading = false; }
  });
  function close() {
    if (dirty && !confirm('Đóng và bỏ bản lưới đang chỉnh? Hãy tải PNG trước nếu muốn giữ ảnh.')) return;
    generation++; loading = false; dirty = false; stage?.destroy(); stage = null;
    slots = []; texts = []; geometry = null; dialog.close(); previousFocus?.focus();
  }
  $('closeImageGrid').addEventListener('click', close);
  dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
  dialog.addEventListener('click', event => { if (event.target === dialog) {
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close();
  } });
  for (const id of ['gridRows', 'gridColumns', 'gridAspect', 'gridGap', 'gridBackground']) {
    $(id).addEventListener(id === 'gridGap' || id === 'gridBackground' ? 'input' : 'change', () => {
      if (!stage || loading) return;
      try {
        const next = C.layout(Number($('gridRows').value), Number($('gridColumns').value), $('gridAspect').value, Number($('gridGap').value));
        slots = C.resizeSlots(slots, next.capacity); geometry = next; selectedCell = Math.min(selectedCell, slots.length - 1);
        syncCellControls(); render(); dirty = true; status('');
      } catch (error) { $('gridRows').value = geometry.rows; $('gridColumns').value = geometry.columns; status(error.message); }
    });
  }
  $('gridCell').addEventListener('change', () => selectCell(Number($('gridCell').value)));
  $('gridSwap').addEventListener('click', () => {
    const target = Number($('gridSwapTarget').value);
    if (!Number.isInteger(target) || target < 0 || target >= slots.length || target === selectedCell) return;
    [slots[selectedCell], slots[target]] = [slots[target], slots[selectedCell]];
    syncCellControls(); render(); dirty = true;
  });
  function updateImage(reset = false) {
    const item = slots[selectedCell]; if (!item) return;
    item.fit = $('gridFitMode').value; item.zoom = C.clamp(Number($('gridImageZoom').value) / 100, .1, 4);
    if (reset) { item.zoom = 1; item.dx = 0; item.dy = 0; }
    syncCellControls(); render(); dirty = true;
  }
  $('gridFitMode').addEventListener('change', () => updateImage());
  $('gridImageZoom').addEventListener('input', () => updateImage());
  for (const [id, increment] of [['gridImageZoomIn', 10], ['gridImageZoomOut', -10]]) {
    $(id).addEventListener('click', () => { $('gridImageZoom').value = C.clamp(Number($('gridImageZoom').value) + increment, 10, 400); updateImage(); });
  }
  $('gridResetImage').addEventListener('click', () => updateImage(true));
  $('gridViewZoom').addEventListener('change', previewScale);
  new ResizeObserver(() => { if (dialog.open) previewScale(); }).observe($('gridViewport'));
  $('gridTextSelection').addEventListener('change', () => { selectedText = $('gridTextSelection').value || null; syncTextControls(); drawSelection(); });
  function textValues() {
    return {text: $('gridText').value.slice(0, 500), size: C.clamp(Number($('gridTextSize').value) || 28, 12, 100), color: $('gridTextColor').value};
  }
  $('gridAddText').addEventListener('click', () => {
    if (!stage) return;
    const values = textValues();
    if (!values.text.trim()) { status('Nhập nội dung chữ trước khi thêm.'); $('gridText').focus(); return; }
    if (texts.length >= 20) { status('Tối đa 20 chú thích.'); return; }
    const text = {...values, id: String(++textSequence), x: .03, y: Math.min(.85, .03 + texts.length * .05)};
    texts.push(text); selectedText = text.id; syncTextControls(); render(); dirty = true; status('Kéo chữ trên bản xem để đặt vị trí.');
  });
  for (const id of ['gridText', 'gridTextSize', 'gridTextColor']) $(id).addEventListener('input', () => {
    const text = texts.find(t => t.id === selectedText); if (!text) return;
    Object.assign(text, textValues()); render(); dirty = true;
    const option = [...$('gridTextSelection').options].find(o => o.value === text.id);
    if (option) option.textContent = text.text.slice(0, 40) || '(Trống)';
  });
  $('gridDeleteText').addEventListener('click', () => { texts = texts.filter(t => t.id !== selectedText); selectedText = null; syncTextControls(); render(); dirty = true; });
  $('gridDownload').addEventListener('click', () => {
    if (!stage || loading) return;
    const token = generation;
    let canvas;
    try {
      const oldSize = stage.size(), oldScale = stage.scale();
      try {
        ui.hide(); stage.scale({x: 1, y: 1}); stage.size({width: geometry.width, height: geometry.height}); stage.draw();
        canvas = stage.toCanvas({pixelRatio: 1});
      } finally { ui.show(); stage.scale(oldScale); stage.size(oldSize); stage.draw(); }
      $('gridDownload').disabled = true; status('Đang tạo PNG…');
      canvas.toBlob(blob => {
        if (token === generation) $('gridDownload').disabled = !stage;
        if (!blob) { if (token === generation) status('Không tạo được PNG. Thử bản lưới nhỏ hơn.'); return; }
        const url = URL.createObjectURL(blob), link = document.createElement('a');
        link.href = url; link.download = `luoi-anh-${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
        document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
        // Keep the close reminder: a download request is not proof the file was kept.
        if (token === generation) status('Đã tạo PNG để tải về.');
      }, 'image/png');
    } catch (error) { $('gridDownload').disabled = false; status(`Không tạo được PNG: ${error.message}`); }
  });
  controls(false);
});
