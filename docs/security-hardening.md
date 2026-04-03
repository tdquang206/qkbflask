# Security Hardening Notes

## API Error Handling
- Do not return raw exception text to clients.
- Return generic error messages in JSON responses.
- Log detailed exception information on the server side.

## Path and Filename Safety
- Sanitize all dynamic filename/path segments before using os.path.join.
- Use allowlisted characters (or secure_filename) for user-derived tokens.
- Validate that final resolved paths stay inside expected directories.

## Upload Safety
- Restrict upload extensions to an allowlist (for example: .jpg, .jpeg, .png, .webp).
- Reject files with invalid or unexpected extensions.
- Build storage filenames from sanitized tokens only.

## Frontend XSS Prevention
- Avoid injecting user-influenced values with innerHTML.
- Prefer DOM APIs with textContent and explicit element creation.
- Use hidden input value assignments instead of HTML string interpolation.

## Runtime Configuration
- Do not use fixed default secret keys.
- Enable debug mode only when explicitly requested via environment variables.

---

## XSS: Server Values Injected into `<script>` Blocks

**Risk:** Embedding a Flask/Jinja2 variable directly inside a JS string literal can break
out of the string if the value contains `"`, `'`, `</script>`, or newlines.

```html
<!-- WRONG — breaks on quotes or </script> in the value -->
<script>
  const phone = "{{ patient.phone }}";
</script>

<!-- RIGHT — |tojson produces a safe JSON-encoded value -->
<script>
  window._pageData = {{ {'phone': patient.phone, 'id': patient.id} | tojson }};
</script>
```

**Rule:** Any Flask/Jinja2 variable placed inside a `<script>` block **must** use
`| tojson`. Bundle all per-page values into a single `window._pageData` object.

---

## XSS: Jinja2 Values in HTML `onclick` / `on*` Attributes

**Risk:** Inline event handlers that call JS functions with Jinja2-interpolated
arguments are broken by any value containing a single quote or backslash:

```html
<!-- WRONG -->
<button onclick="openModal('{{ group.tag }}', '{{ group.time }}')">…</button>

<!-- RIGHT — Jinja2 auto-escapes attribute values; JS reads via dataset -->
<button data-tag="{{ group.tag }}" data-dt="{{ group.display_time }}"
        onclick="openModal(this)">…</button>
```

```js
// In JS — read safely from element attributes
function openModal(el) {
  const tag = el.dataset.tag;
  const dt  = el.dataset.dt;
  …
}
```

---

## XSS: `innerHTML` with API / Database Data

**Risk:** Building HTML strings from `fetch` responses or DB field values allows stored
XSS — a patient name or filename containing `<script>` will execute.

```js
// WRONG — any row.name containing < or > injects HTML
tbody.innerHTML = rows.map(r => `<tr><td>${r.name}</td></tr>`).join('');

// RIGHT — textContent never parses HTML
rows.forEach(function (r) {
  const tr = document.createElement('tr');
  const td = document.createElement('td');
  td.textContent = r.name;
  tr.appendChild(td);
  tbody.appendChild(tr);
});
```

**Rule:** Use `createElement` / `textContent` / `appendChild` for all API-driven
rendering. Reserve `innerHTML` only for fully static, hard-coded markup.

---

## Logic: Array Index Drift in Plan-Execute Pipelines

**Risk:** Using a counter that increments only on successful steps as an array
index drifts when any step is skipped, corrupting subsequent writes.

```python
# WRONG — counter drifts if a step is skipped
counter[exam_id] = counter.get(exam_id, 0) + 1
images[counter[exam_id] - 1]['filename'] = new_name   # wrong element

# RIGHT — capture original index at plan-build time; use it at execute time
for img_idx, img in enumerate(images):
    plan.append({'image_idx': img_idx, …})

# … later during execution:
img_idx = step['image_idx']
images[img_idx]['filename'] = new_name   # always the right element
```

---

## Client/Server Input Normalization Alignment

**Risk:** If the JS normalization function does not exactly match the server-side
Python function, the client may compute "no change" when the server would treat
the value as changed, bypassing confirmation guards.

```js
// WRONG — misses / \ and control characters that the server strips
function normalizeInput(v) { return v.trim().replace(/\s+/g, '_'); }

// RIGHT — mirrors _normalize_phone_input() exactly
function normalizeInput(v) {
  let s = String(v || '').trim();
  s = s.replace(/\s+/g, '_');
  s = s.replace(/[/\\]/g, '_');
  s = s.replace(/[\x00-\x1f]/g, '');
  return s;
}
```

---

## Inline Script Extraction

Long `<script>` blocks in templates are harder to audit for XSS and cannot be
covered by a strict Content-Security-Policy.

**Rule:** Inline `<script>` blocks longer than ~30 lines should be extracted to
`static/<page>.js`. The template injects only a `window._pageData` object with
`| tojson`-escaped values. The external script reads from that object on load.

