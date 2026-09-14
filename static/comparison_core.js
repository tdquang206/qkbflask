/* Pure helpers shared by the comparison UI and regression tests. */
(() => {
  const defaults = () => ({brightness: 0, contrast: 1, crop: null, patch: null});
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  function adjust(data, transform) {
    const output = new Uint8ClampedArray(data);
    for (let i = 0; i < output.length; i += 4) {
      for (let c = 0; c < 3; c++) output[i + c] = clamp(Math.floor(
        (data[i + c] - 128) * transform.contrast + 128 + transform.brightness * 255 + .5), 0, 255);
    }
    return output;
  }
  function stats(pixels, width, height, patch) {
    const [x, y, w, h] = patch;
    let sum = 0, squares = 0, count = 0;
    for (let row = Math.floor(y * height); row < Math.floor((y + h) * height); row++) {
      for (let col = Math.floor(x * width); col < Math.floor((x + w) * width); col++) {
        const i = (row * width + col) * 4;
        const luma = .2126 * pixels[i] + .7152 * pixels[i + 1] + .0722 * pixels[i + 2];
        sum += luma; squares += luma * luma; count++;
      }
    }
    if (!count) throw new Error('Vùng tham chiếu quá nhỏ.');
    const mean = sum / count;
    return {mean, deviation: Math.sqrt(Math.max(0, squares / count - mean * mean))};
  }
  function suggest(source, reference) {
    const contrast = source.deviation > 3 ? clamp(reference.deviation / source.deviation, .75, 1.25) : 1;
    const brightness = clamp((reference.mean - ((source.mean - 128) * contrast + 128)) / 255, -.2, .2);
    return {contrast: Math.round(contrast * 100) / 100, brightness: Math.round(brightness * 100) / 100};
  }
  const graders = {mmasi: (region, values) => region.weight * values.area * values.darkness};
  function score(method, inputs) {
    const gradeRegion = graders[method.id];
    if (!gradeRegion) return null;
    let total = 0;
    for (const region of method.regions) {
      const values = inputs[region.id] || {};
      for (const field of method.fields) {
        if (!Number.isInteger(values[field.id]) || values[field.id] < 0 || values[field.id] >= field.options.length) return null;
      }
      total += gradeRegion(region, values);
    }
    return Math.round(total * 100) / 100;
  }
  function fitSize(width, height, viewportWidth, viewportHeight, zoom = 1) {
    const scale = Math.min(viewportWidth / width, viewportHeight / height) * zoom;
    return {width: Math.max(1, width * scale), height: Math.max(1, height * scale)};
  }
  function projectPatch(patch, crop = [0, 0, 1, 1]) {
    if (!patch) return null;
    const x = Math.max(patch[0], crop[0]), y = Math.max(patch[1], crop[1]);
    const right = Math.min(patch[0] + patch[2], crop[0] + crop[2]);
    const bottom = Math.min(patch[1] + patch[3], crop[1] + crop[3]);
    if (right <= x || bottom <= y) return null;
    return [(x - crop[0]) / crop[2], (y - crop[1]) / crop[3], (right - x) / crop[2], (bottom - y) / crop[3]];
  }
  function patchCandidates(pixels, width, height) {
    const candidates = [], size = .14;
    for (let row = 0; row < 6; row++) for (let col = 0; col < 6; col++) {
      const patch = [.03 + col * .16, .03 + row * .16, size, size];
      const sample = stats(pixels, width, height, patch);
      if (sample.mean < 35 || sample.mean > 220 || sample.deviation > 28) continue;
      let clipped = 0, count = 0;
      for (let y = Math.floor(patch[1] * height); y < Math.floor((patch[1] + size) * height); y += 2) {
        for (let x = Math.floor(patch[0] * width); x < Math.floor((patch[0] + size) * width); x += 2) {
          const i = (y * width + x) * 4;
          if (Math.min(pixels[i], pixels[i + 1], pixels[i + 2]) < 5 || Math.max(pixels[i], pixels[i + 1], pixels[i + 2]) > 250) clipped++;
          count++;
        }
      }
      if (!count || clipped / count > .03) continue;
      candidates.push({patch, rank: sample.deviation + Math.abs(sample.mean - 128) * .03});
    }
    candidates.sort((a, b) => a.rank - b.rank);
    const selected = [];
    for (const candidate of candidates) {
      if (selected.every(p => Math.hypot(p[0] - candidate.patch[0], p[1] - candidate.patch[1]) > .25)) selected.push(candidate.patch);
      if (selected.length === 3) break;
    }
    return selected;
  }
  globalThis.QKBComparisonCore = {defaults, adjust, stats, suggest, score, fitSize, projectPatch, patchCandidates};
})();
