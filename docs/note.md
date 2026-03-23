# Flow
1. When creating a new exam:
Backend returns redirect URL to edit page with that new exam id at exam.py:415.
Frontend uses that URL and navigates there at new_exam.html:509.
So flow is: save new exam => redirect to /exam/edit_exam/<same_exam_id>.
2. When updating an existing exam on edit page:
The form already posts to the current edit URL at edit_exam.html:6.
Submit is handled by fetch/AJAX at edit_exam.html:573.
There is no redirect or reload after success in this handler (it just updates UI/toast) around edit_exam.html:627.
So flow is: save on edit page => stay on same page URL (same exam id), usually without full reload.

---

# Architecture Notes

## How the codebase is laid out
- `app.py` — thin wiring only: Flask app init, blueprint registration, login manager setup. No route handlers.
- `routes/` — one Blueprint per feature area. Global hooks (login guard, backup) live in `routes/core.py`.
- `utils/` — pure helpers with no Flask globals (except where `url_for` is needed inside a request context).
- `shared_db.py` — single source of truth for all TinyDB table handles. Import from here; never open `db.json` elsewhere.
- `static/` — one JS file per feature; no inline `<script>` blocks in templates.
- `static/style.css` — single stylesheet; append new sections at the bottom with a comment header.

## Databases
- All `.json` DB files are AES-GCM encrypted. Always open them with `EncryptedJSONStorage`:
  ```python
  from tinydb import TinyDB
  from utils.storage import EncryptedJSONStorage
  db = TinyDB('db_mua_thuoc.json', storage=EncryptedJSONStorage)
  ```
- `db.json` — patients (with nested exams), drugs, users. Accessed via `shared_db.py`.
- `db_mua_thuoc.json` — drug purchase orders. Opened directly in routes/utils that need it.
- `db_services.json` — services/departments. Accessed via `shared_db.services_table`.
- `money_log.json` — payment ledger entries. Accessed via `shared_db.money_log_table`.
- Backups are written weekly (triggered by any POST/PUT/DELETE) to `backups/`.

## Patient & Exam data model
- Exams are **nested** inside the patient record (`patient['exams']`), not in a separate top-level table.
  The `exams_table` in `shared_db` is a separate (currently unused) table — do not rely on it for patient exams.
- Patient IDs are UUIDs (string). Older records may have integer IDs — handle both.
- Exam IDs are also UUIDs. Short display ID = first 8 chars with hyphens removed.

## Omni-search
- Entry point: `GET /api/omni-search?q=<query>` — defined in `routes/core.py`.
- All logic: `utils/omni_search.py` (normalisation, scoring, per-table searchers).
- Frontend: `static/omni_search.js` (debounce 500ms, AbortController, grouped rendering).
- Minimum query length: 3 characters (after diacritic normalisation). Below that, returns empty immediately.
- Scoring tiers: exact (240+) > digit-exact (235+) > substring (190+) > fuzzy partial/token (threshold 74). Score 0 = excluded.
- The purchase history map is built once per request, shared between drug and purchase searchers.
- At current DB size (~30–100 records) this is not resource-intensive. If records grow into thousands, consider precomputing a normalised search index field on write.

## Dev rules (from .agent/rules/guide.md)
- Always activate `.venv` before running anything: `.venv/Scripts/activate.ps1`.
- No hard-coded white backgrounds on input fields.
- No CDN — download JS libraries for offline use and put in `static/`.
- No long `<script>` or `<style>` blocks inside HTML templates.
- No new route handlers directly in `app.py` — add to an existing Blueprint or create a new one.
- Debug scripts go in `debug/` and must call `load_dotenv()` at the top.
- Add `encoding='utf-8'` when opening files.
- Comment non-trivial logic.