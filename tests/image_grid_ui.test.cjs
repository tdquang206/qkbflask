/* Exercise the production controller with DOM/Konva adapters, not a rendered browser. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(tag, doc) { this.tagName = tag; this.doc = doc; this.children = []; this.events = {}; this.dataset = {}; this.attrs = {}; this.hidden = false; this.disabled = false; this.checked = false; this.clientWidth = 900; this.clientHeight = 600; }
  set value(v) { this._value = String(v); }
  get value() { return this._value ?? (this.tagName === 'select' ? this.children[0]?.value || '' : ''); }
  get options() { return this.children; }
  append(...nodes) { nodes.forEach(n => { n.parent = this; this.children.push(n); }); }
  replaceChildren(...nodes) { this.children = []; this._value = undefined; this.append(...nodes); }
  setAttribute(key, value) { this.attrs[key] = String(value); if (key === 'id') this.id = value; if (key === 'value') this.value = value; if (key === 'hidden') this.hidden = true; }
  addEventListener(key, fn) { (this.events[key] ||= []).push(fn); }
  async fire(key, extra = {}) { for (const fn of this.events[key] || []) await fn({target: this, preventDefault() {}, ...extra}); }
  focus() { this.doc.activeElement = this; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  click() { this.doc.downloads.push(this.download); }
  remove() { this.parent.children = this.parent.children.filter(n => n !== this); }
  querySelectorAll(selector) {
    const checked = selector.endsWith(':checked');
    return this.children.flatMap(n => [...((selector.startsWith('.') ? n.className === selector.slice(1).replace(':checked', '') && (!checked || n.checked) : n.tagName === selector) ? [n] : []), ...n.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0]; }
  closest(selector) {
    if (selector === '.image-tools-dropdown' && this.className === 'image-tools-dropdown') return this;
    if (selector === '#imageToolsMenu button' && this.tagName === 'button' && this.parent?.id === 'imageToolsMenu') return this;
    return this.parent?.closest(selector) || null;
  }
  getContext() { return {drawImage: source => { this.source = source.src; }}; }
}
async function setup() {
  const doc = new Element('document'); doc.doc = doc; doc.downloads = [];
  doc.createElement = tag => new Element(tag, doc);
  doc.getElementById = id => {
    const walk = n => n.id === id ? n : n.children.map(walk).find(Boolean); return walk(doc);
  };
  doc.body = doc.createElement('body'); doc.append(doc.body);
  function add(tag, id, parent = doc.body) { const n = doc.createElement(tag); n.id = id; parent.append(n); return n; }
  add('section', 'patientExamHistory').dataset.comparisonUrl = '/patient/synthetic/comparisons';
  const dropdown = add('div', 'dropdown'); dropdown.className = 'image-tools-dropdown';
  add('button', 'imageToolsBtn', dropdown); const menu = add('div', 'imageToolsMenu', dropdown); menu.hidden = true;
  add('button', 'compareBtn', menu); add('button', 'imageGridBtn', menu); add('button', 'clearSelectionBtn');
  for (let i = 0; i < 3; i++) { const cb = add('input', `cb${i}`); cb.className = 'compare-checkbox'; cb.checked = true; cb.dataset.imageId = `image-${i}`; }
  const stack = [doc.body];
  for (const token of fs.readFileSync('templates/_image_grid_workspace.html', 'utf8').matchAll(/<\/?([a-z][\w-]*)([^>]*?)>/gi)) {
    const [whole, tag, attrs] = token;
    if (whole.startsWith('</')) { if (stack.at(-1).tagName === tag) stack.pop(); continue; }
    const node = doc.createElement(tag);
    for (const a of attrs.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) node.setAttribute(a[1], a[2] || '');
    stack.at(-1).append(node); if (!['link', 'input', 'br'].includes(tag)) stack.push(node);
  }
  const scene = {stages: [], exports: [], requests: [], confirms: 0, confirm: false, catalog: null};
  class Shape {
    constructor(attrs = {}) {
      this.attrs = {...attrs}; this.children = []; this.events = {}; this.visible = true;
      if (attrs.text !== undefined && attrs.width === undefined) this.attrs.width = Math.max(...attrs.text.split('\n').map(s => s.length)) * attrs.fontSize * .6 + 8;
    }
    add(...nodes) { this.children.push(...nodes); }
    on(key, fn) { this.events[key] = fn; }
    destroyChildren() { this.children = []; }
    destroy() { this.destroyed = true; }
    batchDraw() {}
    draw() {}
    hide() { this.visible = false; }
    show() { this.visible = true; }
    x(value) { if (value !== undefined) this.attrs.x = value; return this.attrs.x; }
    y(value) { if (value !== undefined) this.attrs.y = value; return this.attrs.y; }
    width(value) { if (value !== undefined) this.attrs.width = value; return this.attrs.width; }
    height() { return this.attrs.height || this.attrs.fontSize * 2; }
  }
  class Stage extends Shape {
    constructor(attrs) { super(attrs); this._scale = {x: 1, y: 1}; scene.stages.push(this); }
    size(value) { if (value) Object.assign(this.attrs, value); return {width: this.attrs.width, height: this.attrs.height}; }
    scale(value) { if (value) this._scale = {...value}; return {...this._scale}; }
    toCanvas(config) { scene.exports.push({size: this.size(), scale: this.scale(), uiVisible: this.children[1].visible, config}); return {toBlob: fn => fn({})}; }
  }
  scene.catalog = {images: Array.from({length: 3}, (_, i) => ({id: `image-${i}`, kind: 'original', date: `2026-10-0${i + 1}`, filename: `img${i}.jpg`, url: `/uploads/img${i}.jpg`}))};
  const context = vm.createContext({document: doc, console, URL: class extends URL { static createObjectURL() { return 'blob:synthetic'; } static revokeObjectURL() {} },
    window: {location: {href: 'http://localhost/patient/synthetic/exams', origin: 'http://localhost'}},
    Image: class {naturalWidth = 3000; naturalHeight = 2000; async decode() {}},
    ResizeObserver: class {observe() {}}, setTimeout() {},
    confirm: () => { scene.confirms++; return scene.confirm; }, alert: message => { throw Error(message); },
    fetch: async url => { scene.requests.push(url); if (scene.gate) await scene.gate; return {ok: true, json: async () => scene.catalog}; },
    Konva: {Stage, Layer: Shape, Group: Shape, Rect: Shape, Image: Shape, Text: Shape}});
  for (const name of ['image_grid_core', 'image_tools', 'image_grid']) vm.runInContext(fs.readFileSync(`static/${name}.js`, 'utf8'), context);
  await doc.fire('DOMContentLoaded');
  return {doc, scene, $: id => doc.getElementById(id)};
}

(async () => {
  const {$, doc, scene} = await setup();
  await $('imageToolsBtn').fire('click'); assert.equal($('imageToolsMenu').hidden, false);
  await $('imageToolsBtn').fire('keydown', {key: 'ArrowDown'}); assert.equal(doc.activeElement, $('compareBtn'));
  await $('imageGridBtn').fire('click');
  await doc.fire('click', {target: $('imageGridBtn')}); assert.equal($('imageToolsMenu').hidden, true);
  assert.equal($('imageGridDialog').open, true); assert.equal($('gridDownload').disabled, false);
  assert.equal($('gridRows').value, '2'); assert.equal($('gridColumns').value, '2');
  assert.equal(scene.requests.length, 1); // Reads the catalog; no save/upload requests.
  assert.equal($('gridCell').options.length, 4);
  const stage = scene.stages.at(-1), layer = stage.children[0];
  const firstSource = layer.children[1].children[1].attrs.image;
  assert.equal(firstSource.width, 1600); // Camera images are bounded in memory.
  $('gridColumns').value = '1'; await $('gridColumns').fire('change');
  assert.equal($('gridColumns').value, '2'); assert.ok($('imageGridStatus').textContent.includes('3'));
  $('gridSwapTarget').value = '3'; await $('gridSwap').fire('click');
  assert.equal(layer.children[1].children.length, 1); // Source moved into the empty fourth slot.
  assert.equal(layer.children[4].children[1].attrs.image, firstSource);
  $('gridCell').value = '3'; await $('gridCell').fire('change');
  $('gridImageZoom').value = '200'; await $('gridImageZoom').fire('input');
  assert.equal($('gridImageZoomValue').textContent, '200%');
  $('gridText').value = 'Trước điều trị\nNgày 02/10'; await $('gridAddText').fire('click');
  assert.equal(layer.children.at(-1).attrs.text, 'Trước điều trị\nNgày 02/10');
  $('gridAspect').value = 'portrait'; await $('gridAspect').fire('change');
  assert.equal(layer.children.at(-1).attrs.text, 'Trước điều trị\nNgày 02/10');
  $('gridViewZoom').value = '1.5'; await $('gridViewZoom').fire('change');
  const previewSize = stage.size(); await $('gridDownload').fire('click');
  assert.deepEqual(scene.exports[0].size, {width: 624, height: 824});
  assert.deepEqual(scene.exports[0].scale, {x: 1, y: 1}); assert.equal(scene.exports[0].uiVisible, false);
  assert.deepEqual(stage.size(), previewSize); assert.equal(doc.downloads.length, 1);
  await $('closeImageGrid').fire('click'); assert.equal($('imageGridDialog').open, true); // Declined discard preserves all edits.
  scene.confirm = true; await $('imageGridDialog').fire('cancel'); assert.equal($('imageGridDialog').open, false);
  assert.equal(stage.destroyed, true); assert.equal(doc.activeElement, $('imageToolsBtn'));
  await $('imageGridBtn').fire('click'); assert.equal($('gridTextSelection').options.length, 1); // Fresh session has no previous labels.
  assert.equal($('gridImageZoom').value, '100');
  await $('closeImageGrid').fire('click');
  scene.catalog.images[0].url = 'https://external.invalid/uploads/image.jpg';
  await $('imageGridBtn').fire('click'); assert.equal($('gridDownload').disabled, true);
  assert.ok($('imageGridStatus').textContent.includes('không hợp lệ')); // No external source is decoded.
  await $('closeImageGrid').fire('click');
  scene.catalog.images[0].url = '/uploads/img0.jpg';
  let release;
  scene.gate = new Promise(resolve => { release = resolve; });
  const stageCount = scene.stages.length;
  const pending = $('imageGridBtn').fire('click');
  await $('closeImageGrid').fire('click'); release(); await pending;
  assert.equal($('imageGridDialog').open, false);
  assert.equal(scene.stages.length, stageCount); // A late catalog response cannot resurrect a closed draft.
  console.log('Grid controller: Tools menu, load/cancel, lossless layout, swaps, zoom, text, export, close/reopen, and local source restrictions passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
