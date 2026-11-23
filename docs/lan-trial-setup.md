# Running the file-based LAN trial

Implemented 15 October 2026. The app continues using the existing encrypted TinyDB files. There is no SQLite/PostgreSQL migration, receptionist page or transfer workflow.

## Implemented behavior

- All doctors read shared history. Only the exam's `created_by_id` may change its clinical content, images or comparison destination. Administrator access does not override this rule.
- A changed saved exam displays **Edited / Đã chỉnh sửa**, with an encrypted before/after history and actor/time. Initial creation and unchanged saves do not count as edits. Clinical timestamps display in Vietnam time. Old records without a verifiable owner remain read-only; ownership is not guessed from names.
- Separate doctors create separate exam UUIDs, including on the same date. Patient movement is coordinated verbally, using the current exam forms.
- A common reentrant gate serializes non-static requests, including authentication, complete reads/updates, files, error handling and backup/restore. Individual exam revisions prevent stale forms from overwriting a newer version. Slow image/PDF work also occupies the gate in this conservative trial; measure actual wait times before expanding.
- Encrypted temporary files replace databases atomically. An encrypted before-image journal rolls back failed requests and unfinished operations on restart, including payment/ledger writes and tracked media changes. A process lock prevents opening the same database directory in another cooperating QKB process. Do not use external file editors or alternate writers.
- Clinical deletion retains a tombstone and history. Image removal retains the old bytes. Changing a patient phone copies assets to the new names while retaining old paths for historical versions. Storage grows with retained history; there is no clinical purge feature.
- Note edits preserve payment state. Package allocations are returned/recalculated during edits so an unchanged save does not consume another session. Mark-paid requests set an explicit state; retries do not toggle it back or insert another receipt. Setting a paid flag false is not a refund transaction and does not erase existing money received entries.
- New accounts require at least 12 characters and change their temporary password on first login. Existing short passwords require a change on next login. Accounts are deactivated, retaining authorship IDs. Admin password resets revoke sessions. Sessions expire after 30 minutes idle or 8 hours after login; failed logins are rate-limited per client address.
- CSRF protects logout and writes. Mutation failures return JSON without discarding the page's input. Audit logs allowlist metadata instead of request forms; clinical before/after text stays encrypted. Doctor-only media access, no-store responses, safer redirects and host checks are enabled.
- Discord delivery is disabled unless `QKB_ALLOW_DISCORD=1`. Plaintext exports/downloads are disabled unless `QKB_ALLOW_PLAINTEXT_EXPORTS=1`; use encrypted recovery sets for backups.

## Before starting

1. Stop the existing tray/server process before using this release. Preserve the four database files, `uploads/`, `files/`, `user_settings.json`, `exam_template.json` and the existing encryption key together. A Git push normally preserves code; the repository ignores clinical databases, patient files, keys and backups.
2. Keep the current `DB_ENCRYPTION_KEY`. Do not generate a replacement for existing encrypted data. Keep a recoverable copy separately from the backup device. Retain any old keys if you later rotate encryption.
3. Use Python 3.13 and the tested package lock:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
   ```

   The lock captures the tested environment; it is not a security-audit certificate. Keep OS/Python/dependency updates under a tested maintenance process. PDF generation also needs the existing wkhtmltopdf/Poppler binaries under the source directory.
4. Configure strong `SECRET_KEY` and the existing `DB_ENCRYPTION_KEY` through protected service environment settings or the ignored `.env`. Only a completely new empty installation needs `QKB_BOOTSTRAP_PASSWORD` (12+ characters); existing accounts are preserved. Remove the bootstrap setting after setup and change that account's password at login.
5. Review accounts in Admin. Assign clinical staff the `doctor` role, rather than the legacy generic `user` role. `cashier` can update payment state, `pharmacist` can maintain drugs/purchases, and `receptionist` can maintain demographics; the receptionist page itself is deferred. Review legacy exams' stored owner IDs before expecting them to be editable.
6. Encrypt the server/backup volumes and restrict filesystem access to the app service account and designated operators. Clinical files are decrypted when served to authorized doctors; disk encryption does not protect a running compromised account.

## HTTPS and startup

Use `server.py` for the headless LAN deployment, with a local HTTPS reverse proxy. `app.py` remains the loopback desktop/tray entry point. Do not run them concurrently against the same data.

Example protected `.env` additions, preserving existing key values:

```dotenv
QKB_LAN_MODE=1
QKB_TRUSTED_HOSTS=qkb.clinic.internal,localhost,127.0.0.1
QKB_PORT=5000
# Optional dedicated data directory; otherwise the source directory is used.
# QKB_DATA_DIR=D:/QKBData
# Choose an independent backup destination accessible to the service account.
# QKB_BACKUP_DIR=E:/QKBBackups
```

If selecting `QKB_DATA_DIR`, first stop the app and copy the complete recovery set there; keep the original intact until validation. The server changes its working directory to that location, while templates/static assets/PDF binaries come from the source directory. `.env` remains in the protected source directory and is deliberately excluded from clinical backup archives because it contains keys.

From the source directory:

```powershell
.\.venv\Scripts\python.exe server.py
```

The listener remains on `127.0.0.1:5000`. Copy [Caddyfile.example](../Caddyfile.example) to a protected Caddy configuration and use a reserved server address/internal DNS entry for `qkb.clinic.internal`. Caddy's `tls internal` issues a local certificate; distribute **only its root CA certificate**, never its private key, to trusted staff devices. See [Caddy TLS documentation](https://caddyserver.com/docs/caddyfile/directives/tls).

```powershell
caddy run --config Caddyfile
```

Staff open `https://qkb.clinic.internal`. Firewall port 443 to the actual staff subnet, exclude guest networks, and keep port 5000 inaccessible remotely. Caddy must be the sole proxy hop; the app trusts forwarded headers from that loopback deployment. Do not configure a public tunnel/router forwarding. Verify trusted certificates on each device.

Configure both processes under the clinic's service supervisor or Windows Task Scheduler: start at boot, run under a restricted account whether logged on or not, use the correct working directory, restart after failure, prevent overlapping instances and disable automatic time-limit termination. Task Scheduler's Python action is the absolute path to `.venv\Scripts\python.exe`, with the absolute `server.py` path as its argument. No firewall, certificate trust, scheduled tasks or Windows services were changed automatically by this code update.

## Backups

The desktop server and `server.py` start a backup scheduler. It attempts a coordinated, verified recovery point every 15 minutes, starting at launch. A complete encrypted set is made on the first successful backup of each Vietnam calendar day; subsequent points reuse encrypted content blobs for unchanged files.

- The configured destination contains `qkb_*.qkb` manifests/full archives and a `blobs/` directory. **Copy the entire destination tree** when replicating scheduled backups. An incremental `.qkb` alone is incomplete without its referenced blobs.
- Admin -> **Sao lưu đầy đủ** creates a manual self-contained backup and lists recovery points. Its download always builds a self-contained encrypted `.qkb`, including any shared blobs, suitable for copying to a disconnected/off-site device.
- Recovery sets contain all four databases (or an explicit uninitialized marker), uploads, generated files, configuration/templates and logs. The encryption key and source-code release are separate recovery requirements. Keep the matching application release/package lock with the deployment records.
- Every point authenticates encrypted entries and checks hashes before publication. The scheduler retains 48 hours of frequent points, 30 daily points and 12 monthly points, then collects unreferenced blobs. This is backup rotation, not permission to purge clinical history.
- Check the backup page daily. It displays failures and a warning when the last automatic success is over 20 minutes old. The status is stored in `backups/status.json`. If the service itself is down, this page cannot alert you: independent process/backup-age monitoring remains an operator responsibility.
- Snapshots and verification hold the shared gate, so response times may increase with large images or a slow backup device. The 15-minute recovery-point / 4-hour recovery-time objectives require measurement on real hardware. Daily off-site copies alone can lose up to a day's work in a site-wide incident.
- Use independent storage with restricted credentials and an offline/off-site copy. A backup directory on the live disk protects neither disk failure nor a compromised server. The app cannot make a permanently mounted writable backup ransomware-proof.

## Restore and rehearsal

Prefer an isolated spare machine/directory first. Keep the matching application release, keys and required binaries available. The browser restore requires an administrator password and the exact confirmation `RESTORE`, creates a safety backup, blocks other requests while replacing files and revokes all login sessions. Staff should stop taking new work before an operator begins a real restore.

For an offline recovery, with the app stopped and the encryption key available:

```powershell
.\.venv\Scripts\python.exe tools/restore_backup.py E:/QKBBackups/example.qkb --data-dir D:/QKBRecovery --verify-only
.\.venv\Scripts\python.exe tools/restore_backup.py E:/QKBBackups/example.qkb --data-dir D:/QKBRecovery --confirm
```

Use the actual downloaded filename in place of `example.qkb`. Scheduled incremental points require their original sibling `blobs/` folder. Verification authenticates the full set before any data changes. Offline restore refuses a directory held by a running cooperating QKB process, creates a safety backup of existing databases, journals replacements and revokes old sessions.

Check patient/exam IDs, ownership/history, receipts/package balances and sampled images/PDFs. Compare paper records and anything entered since the selected backup. Use a new strong session secret for a replacement server, retain the correct database key, review restored accounts/passwords and keep outbound Discord disabled during the drill. Only then redirect staff clients to the recovered service. No real restore was performed during development.

## Validation and remaining acceptance

Automated tests use synthetic encrypted data in disposable directories; no live database is opened by the test suite. Coverage includes concurrent independent edits, stale conflicts, ownership bypass attempts, history rollback, payment retry/rollback, unchanged package allocation, retained attachments, complete/tampered backups, process locking, session revocation and CSRF. Existing comparison/grid suites remain applicable.

Rendered browser acceptance could not run because no browser was connected. Physical LAN/firewall/TLS checks, server reboot supervision, real PDF tooling, actual ten-doctor responsiveness, independent backup replication and a timed spare-machine restore remain deployment acceptance tasks. The developer has not claimed these checks passed.

The [agreed plan](lan-rollout-plan.md) records the broader design. Start with a small doctor group after the setup checks, then expand based on measured results.
