# AGENTS

## Project overview
- QKBFlask is a Flask-based clinical management app for exams, patients, drugs, services, and receipts.
- It uses TinyDB with a custom AES-GCM encrypted storage layer (`utils/storage.py`) to protect database files at rest.
- The app is structured as a small blueprint-based Flask project: `app.py` wires blueprints, and most business logic lives under `routes/`.

## Key files
- `app.py`
  - Entry point for the app.
  - Sets up `Flask`, `CSRFProtect`, `Flask-Login`, and registers all blueprint modules.
  - Provides a tray icon / Waitress-based startup path for desktop usage.
- `shared_db.py`
  - Central TinyDB initialization and shared table aliases.
  - Defines `db.json`, `money_log.json`, and `db_services.json` with encrypted storage.
- `utils/storage.py`
  - Custom `EncryptedJSONStorage` implementation for TinyDB.
  - Reads/writes encrypted JSON files using the environment variable `DB_ENCRYPTION_KEY`.
- `routes/` directory
  - `core.py`: global login guard, audit/backup hooks, static file serving, and omni-search endpoint.
  - `auth.py`: login/logout, user loader, default admin setup.
  - `admin.py`: admin dashboard, database export/import pages, checkpoint restore, user management.
  - `patients.py`: patient CRUD, phone normalization, asset rename, and file path safety helpers.
  - `exam.py`: exam create/edit, image upload, service/package logic, Discord send helpers.
  - `drugs.py`: drug management, purchase handling, API support, Discord notifications.
  - `mua_thuoc.py`: purchase order management for medicine imports.
  - `settings.py`: Discord settings, department/service settings, changelog page.
  - `route_all_exams_page.py`: `/danh_sach_kham_benh` exam list page and `/api/mark_paid` payment toggle.
  - `reports.py`: reporting endpoints.

## Important conventions
- Do not edit encrypted TinyDB files directly. Use the app and environment variables instead.
- All mutable form actions are protected by CSRF and require authentication.
- `patients_table` stores nested exam records (`patient['exams']`) rather than a separate relational table.
- Discord webhook URLs are allowlisted to `https://discord.com/api/webhooks/` and `https://discordapp.com/api/webhooks/`.
- User settings persist in `user_settings.json`; database backups live in `backups/`; decrypted exports go to `decrypted_exports/`.

## Environment and run notes
- Required packages are listed in `requirements.txt`.
- The app expects these environment variables:
  - `SECRET_KEY` (required in non-debug mode)
  - `DB_ENCRYPTION_KEY` (Base64-encoded AES key for TinyDB storage)
  - `FLASK_DEBUG=1` to enable debug mode.
- Standard startup is `python app.py` or via `startQKB.bat`.

## How to use this file
- Use `app.py`, `shared_db.py`, and `utils/storage.py` to understand overall app startup and storage behavior.
- When modifying behavior, prefer the appropriate route module in `routes/` rather than adding logic to `app.py`.
- For feature questions, check `routes/<feature>.py` and link to `changelog.md` for historical context.

## Notes
- This repository did not previously include a root `AGENTS.md` or `.github/copilot-instructions.md` file.
- `docs/` contains supplemental route-specific documentation for deeper review.
