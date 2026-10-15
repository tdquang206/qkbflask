const assert = require('node:assert/strict');
const C = require('../static/image_grid_core.js');

assert.deepEqual(C.layout(2, 3, 'landscape', 10), {
  rows: 2, columns: 3, gap: 10, cellWidth: 400, cellHeight: 300, capacity: 6, width: 1240, height: 630,
});
for (const rows of [0, 7, 1.5, NaN]) assert.throws(() => C.layout(rows, 2));
assert.throws(() => C.layout(1, 2, 'bad'));
assert.throws(() => C.layout(1, 2, 'square', Infinity));
const a = {id: 'a'}, b = {id: 'b'};
assert.throws(() => C.resizeSlots([a, b], 1));
assert.deepEqual(C.resizeSlots([null, a, null, b], 2), [a, b]);
assert.deepEqual(C.resizeSlots([a, null, b], 4), [a, null, b, null]);
assert.deepEqual(C.resizeSlots([a, null, b, null], 3), [a, null, b]);
const item = {fit: 'contain', zoom: 1, dx: 0, dy: 0};
assert.deepEqual(C.placement(200, 400, 400, 400, item), {x: 100, y: 0, width: 200, height: 400});
item.fit = 'cover';
assert.deepEqual(C.placement(200, 400, 400, 400, item), {x: 0, y: -200, width: 400, height: 800});
item.zoom = 2; item.dx = -100; item.dy = 100;
assert.deepEqual(C.placement(200, 400, 400, 400, item), {x: -400, y: 0, width: 800, height: 1600});
C.rememberPosition(item, -100, -500, 800, 1600, 400, 400);
assert.deepEqual(C.placement(200, 400, 400, 400, item), {x: -100, y: -500, width: 800, height: 1600});
// Moving to another equally sized cell keeps framing; the preview scale never enters the calculation.
const swapped = [item, a]; [swapped[0], swapped[1]] = [swapped[1], swapped[0]];
assert.equal(swapped[1], item);
assert.equal(C.placement(200, 400, 400, 400, swapped[1]).y, -500);
console.log('Grid geometry: layout bounds, lossless resize, fit/cover, zoom, pan limits, and framing retention passed.');
