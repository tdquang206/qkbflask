/* Geometry is in export pixels, independent of the preview scale. */
(function (root) {
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  function layout(rows, columns, aspect = 'square', gap = 8) {
    if (![rows, columns].every(n => Number.isInteger(n) && n >= 1 && n <= 6)) throw Error('Chọn từ 1 đến 6 hàng và cột.');
    if (!['square', 'landscape', 'portrait'].includes(aspect) || !Number.isFinite(gap) || gap < 0 || gap > 40) throw Error('Bố cục không hợp lệ.');
    const cellWidth = aspect === 'portrait' ? 300 : 400;
    const cellHeight = aspect === 'landscape' ? 300 : 400;
    return {rows, columns, gap, cellWidth, cellHeight, capacity: rows * columns,
      width: columns * cellWidth + (columns + 1) * gap, height: rows * cellHeight + (rows + 1) * gap};
  }
  function resizeSlots(slots, capacity) {
    const occupied = slots.filter(Boolean);
    if (occupied.length > capacity) throw Error(`Cần ít nhất ${occupied.length} ô cho các ảnh đã chọn.`);
    if (slots.length <= capacity) return [...slots, ...Array(capacity - slots.length).fill(null)];
    // Keep positions when possible; compact only when shrinking past an occupied slot.
    const kept = slots.slice(capacity).some(Boolean) ? occupied : slots.slice(0, capacity);
    return [...kept, ...Array(capacity - kept.length).fill(null)];
  }
  function placement(iw, ih, cw, ch, item) {
    if (![iw, ih, cw, ch].every(n => Number.isFinite(n) && n > 0)) throw Error('Kích thước ảnh không hợp lệ.');
    const scale = (item.fit === 'cover' ? Math.max(cw / iw, ch / ih) : Math.min(cw / iw, ch / ih)) * clamp(item.zoom, .1, 4);
    const width = iw * scale, height = ih * scale;
    const x = clamp((cw - width) / 2 + item.dx * cw, Math.min(0, cw - width), Math.max(0, cw - width));
    const y = clamp((ch - height) / 2 + item.dy * ch, Math.min(0, ch - height), Math.max(0, ch - height));
    return {x, y, width, height};
  }
  function rememberPosition(item, x, y, width, height, cw, ch) {
    item.dx = (x - (cw - width) / 2) / cw;
    item.dy = (y - (ch - height) / 2) / ch;
  }
  const api = {clamp, layout, resizeSlots, placement, rememberPosition};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.QKBImageGridCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
