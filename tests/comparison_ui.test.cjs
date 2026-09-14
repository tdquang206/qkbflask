// Exercise the real controller against a small DOM adapter. This is not browser/layout QA.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Node {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.attrs = {}; this.dataset = {}; this.style = {};
    this.events = {}; this.hidden = false; this.checked = false; this.disabled = false; this.tabIndex = 0;
    this.clientWidth = 600; this.clientHeight = 400; this.scrollLeft = 0; this.scrollTop = 0;
    this.classList = {contains: c => this.className.split(' ').includes(c),
      add: c => { if (!this.classList.contains(c)) this.className += ' ' + c; },
      remove: c => { this.className = this.className.split(' ').filter(x => x !== c).join(' '); },
      toggle: (c, enabled) => enabled ? this.classList.add(c) : this.classList.remove(c)};
    this.className = '';
  }
  set value(v) { this._value = String(v); }
  get value() { return this._value ?? (this.tagName === 'select' ? this.children[0]?.value || '' : ''); }
  setAttribute(key, value) {
    value = String(value); this.attrs[key] = value;
    if (key.startsWith('data-')) this.dataset[key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value;
    if (key === 'id') this.id = value;
    if (key === 'class') this.className = value;
    if (key === 'value') this.value = value;
    if (key === 'tabindex') this.tabIndex = Number(value);
    if (key === 'content') this.content = value;
    if (key === 'hidden') this.hidden = true;
    if (key === 'checked') this.checked = true;
  }
  append(...nodes) { for (const node of nodes) { node.parent = this; this.children.push(node); } }
  replaceChildren(...nodes) { this.children = []; this._value = undefined; this.append(...nodes); }
  addEventListener(type, fn) { (this.events[type] ||= []).push(fn); }
  async fire(type, extra = {}) { for (const fn of this.events[type] || []) await fn({preventDefault() {}, target: this, ...extra}); }
  focus() { this.doc.activeElement = this; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  get nextElementSibling() { return this.parent.children[this.parent.children.indexOf(this) + 1]; }
  getClientRects() { return this.hidden || this.parent?.getClientRects().length === 0 ? [] : [{}]; }
  closest(selector) { return selector === '[inert]' && this.inert ? this : this.parent?.closest(selector); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    const matches = (node, part) => {
      const checked = part.endsWith(':checked'); part = part.replace(':checked', '');
      const enabled = part.includes(':not(:disabled)'); part = part.replace(':not(:disabled)', '');
      let match;
      if (part.startsWith('.')) match = node.classList.contains(part.slice(1));
      else if (part.startsWith('#')) match = node.id === part.slice(1);
      else if (part.startsWith('[')) match = Object.hasOwn(node.attrs, part.slice(1, -1));
      else if (part === 'meta[name="csrf-token"]') match = node.tagName === 'meta';
      else match = node.tagName === part;
      return match && (!checked || node.checked) && (!enabled || !node.disabled);
    };
    return this.children.flatMap(child => [
      ...(selector.split(',').some(s => matches(child, s.trim())) ? [child] : []), ...child.querySelectorAll(selector),
    ]);
  }
  getContext() { return {drawImage() {}, putImageData() {}, getImageData: () => ({data: new Uint8ClampedArray(this.width * this.height * 4).fill(128)})}; }
  setPointerCapture() {}
  getBoundingClientRect() { return {left: 0, top: 0, width: parseFloat(this.style.width) || 600, height: parseFloat(this.style.height) || 400}; }
}

async function setup() {
  const doc = new Node('document'); doc.doc = doc;
  doc.createElement = tag => { const node = new Node(tag); node.doc = doc; return node; };
  doc.createElementNS = (_, tag) => doc.createElement(tag);
  doc.createTextNode = text => { const node = doc.createElement('text'); node.textContent = text; return node; };
  doc.getElementById = id => doc.querySelector('#' + id);
  doc.documentElement = doc.createElement('html'); doc.append(doc.documentElement);
  const base = doc.documentElement;
  function add(tag, id, parent = base) { const node = doc.createElement(tag); node.setAttribute('id', id); parent.append(node); return node; }
  const meta = add('meta', 'csrf'); meta.content = 'test-token';
  add('section', 'patientExamHistory').dataset.comparisonUrl = '/patient/test/comparisons';
  for (const id of ['compareControls', 'compareCount', 'compareBtn', 'clearSelectionBtn']) add('button', id);
  const checkbox = add('input', 'selectedImage'); checkbox.className = 'compare-checkbox'; checkbox.checked = true; checkbox.dataset.imageId = 'image-1';
  // Read element structure/IDs from the actual template; ignore Jinja and text nodes.
  const stack = [base];
  const html = fs.readFileSync('templates/_comparison_workspace.html', 'utf8');
  const voidTags = new Set(['input', 'link', 'br']);
  for (const token of html.matchAll(/<\/?([a-z][\w-]*)([^>]*?)>/gi)) {
    const [whole, tag, attrs] = token;
    if (whole.startsWith('</')) { if (stack.at(-1).tagName === tag) stack.pop(); continue; }
    const node = doc.createElement(tag);
    for (const attr of attrs.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) node.setAttribute(attr[1], attr[2] || '');
    stack.at(-1).append(node); if (!voidTags.has(tag)) stack.push(node);
  }
  const method = {id: 'mmasi', version: 1, label: 'mMASI', maximum: 24, source: 'https://example.test', formula: 'test',
    regions: [{id: 'f', label: 'Forehead', weight: 1}], fields: [{id:'area',options:Array.from({length:7}, (_, i) => String(i))},{id:'darkness',options:Array.from({length:5}, (_, i) => String(i))}]};
  const catalog = {revision:'test', images:[{id:'image-1',kind:'original',exam_id:'exam-1',date:'2026-01-01',filename:'source.jpg',url:'/source.jpg'}],
    exams:[{id:'exam-1',date:'2026-01-01'}], records:[], methods:[method]};
  const network = {saves: [], fail: false, reloads: 0};
  const context = vm.createContext({document:doc, window:{addEventListener() {}},
    structuredClone, Uint8ClampedArray, ImageData: class {}, console,
    Image: class {naturalWidth=200; naturalHeight=400; async decode() {}},
    ResizeObserver: class {observe() {} disconnect() {}}, requestAnimationFrame: fn => fn(),
    location:{reload: () => network.reloads++}, alert: message => { throw Error(message); }, confirm: () => true,
    fetch: async (url, opts) => {
      if (!opts.method) return {ok:true,json:async()=>structuredClone(catalog)};
      if (url.endsWith('/summary')) return {ok:true,json:async()=>({summary:'Previewed note'})};
      network.saves.push(JSON.parse(opts.body));
      return {ok:!network.fail,json:async()=>network.fail ? {message:'Save failed'} : {record:{id:'saved'}}};
    }});
  vm.runInContext(fs.readFileSync('static/comparison_core.js','utf8'), context);
  vm.runInContext(fs.readFileSync('static/comparison.js','utf8'), context);
  await doc.fire('DOMContentLoaded');
  await doc.getElementById('compareBtn').fire('click');
  return {doc, network, $: id => doc.getElementById(id)};
}

(async () => {
  const {$, doc, network} = await setup();
  assert.equal($('comparisonLayout').dataset.view, 'adjust');
  const canvas = doc.querySelector('canvas');
  assert.equal(parseFloat(canvas.style.height), 396);
  assert.equal(parseFloat(canvas.style.width), 198);
  const imageButton = text => doc.querySelectorAll('button').find(b => b.textContent === text);
  await imageButton('Chọn vùng tham chiếu').fire('click');
  await canvas.fire('pointerdown', {clientX:20, clientY:20, pointerId:1});
  await canvas.fire('pointerup', {clientX:70, clientY:90, pointerId:1});
  const overlay = doc.querySelector('.comparison-overlay');
  assert.equal(overlay.querySelectorAll('rect').length, 1);
  await imageButton('Gợi ý vùng').fire('click');
  assert.ok(overlay.querySelectorAll('rect').length >= 3);
  await imageButton('Dùng vùng 1').fire('click');
  assert.equal(overlay.querySelectorAll('rect').length, 1);
  $('showReferencePatches').checked = false; await $('showReferencePatches').fire('change');
  assert.equal(overlay.querySelectorAll('rect').length, 0);
  $('showReferencePatches').checked = true; await $('showReferencePatches').fire('change');
  assert.equal(overlay.querySelectorAll('rect').length, 1);
  const sliders = doc.querySelectorAll('input').filter(n => n.type === 'range');
  sliders[0].value = '.12'; await sliders[0].fire('input');
  await $('comparisonTabGrade').fire('click');
  assert.equal($('comparisonGradeSection').hidden, false);
  assert.equal($('comparisonAdjustToolbar').hidden, true);
  await $('comparisonTabSave').fire('click');
  assert.equal($('comparisonImageStage').hidden, true);
  await $('comparisonTabAdjust').fire('click');
  assert.equal(sliders[0].value, '.12');
  await $('closeComparison').fire('click');
  assert.equal($('comparisonClosePrompt').open, true);
  await $('comparisonContinue').fire('click');
  assert.equal($('compareModal').classList.contains('is-active'), true);
  network.fail = true;
  await $('closeComparison').fire('click'); await $('comparisonSaveAndClose').fire('click');
  assert.equal($('compareModal').classList.contains('is-active'), true);
  assert.equal($('comparisonStatus').textContent, 'Save failed');
  assert.equal(network.saves[0].images[0].transform.brightness, .12);
  assert.equal(network.saves[0].images[0].transform.patch.length, 4);
  assert.equal(network.reloads, 0);
  await $('closeComparison').fire('click'); await $('comparisonDiscard').fire('click');
  assert.equal($('compareModal').classList.contains('is-active'), false);
  assert.equal(network.saves.length, 1);

  const second = await setup();
  second.$('appendComparisonNote').checked = true; await second.$('appendComparisonNote').fire('input');
  await second.$('closeComparison').fire('click'); await second.$('comparisonSaveAndClose').fire('click');
  assert.equal(second.network.saves.length, 0);
  assert.equal(second.$('comparisonLayout').dataset.view, 'save');
  await second.$('previewComparisonNote').fire('click'); await second.$('saveComparison').fire('click');
  assert.equal(second.network.reloads, 1);
  assert.equal(second.network.saves[0].append_note, true);
  console.log('UI controller: fitted opening, tabs, retained edits, close choices, failed save, note preview, and save/close passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
