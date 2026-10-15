# QKBFlask LAN trial plan

Revised: 15 October 2026, incorporating the owner's feedback. Planning document only; application code and production data are unchanged.

## 1. Agreed scope

- Up to 10 doctors; every doctor may read every patient's clinical history across departments.
- A doctor may change only that doctor's own exam records. Changed clinical records display **Edited**, and prior versions are retained in edit history.
- One patient can have two separate exams on the same date, for example Eye / Doctor A and Nutrition / Doctor B. The consultations take place sequentially.
- Staff can verbally redirect a patient who goes to the wrong room. No electronic transfer, acceptance, referral or routing record is required for this trial.
- A receptionist page is a later feature to design separately. Do not make queues, arrival registration or a separate parent visit record prerequisites for the trial.
- Keep the existing file-based databases on the central server for the trial. Do not require PostgreSQL or another database server first.
- Security implementation choices are delegated to the developer. Use the controls below without repeatedly asking the owner to choose technical settings. Clinic operational policies and legal retention requirements still need the responsible owner's input where unspecified.

Storage clarification: this checkout uses AES-GCM-encrypted **TinyDB** files (`db.json`, `db_services.json`, `money_log.json`, `db_mua_thuoc.json`), not SQLite. Interpret “keep current sqlite file on server” as retaining those existing file-based databases for now. No SQLite conversion is included. SQLite or PostgreSQL can be evaluated later using trial results.

## 2. Patient workflow for the trial

```text
Find existing patient / add patient
                 |
      Doctor A starts Eye exam
                 |
      Doctor A saves and completes exam A
                 |
          Home OR another room
                          |
             Doctor B starts Nutrition exam
                          |
             Doctor B saves and completes exam B
                          |
                         Home
```

- Preserve the existing patient UUID and exam UUIDs. Phone numbers and dates are not unique record identifiers.
- Show both exams separately in shared history, each with its department, author, date and time. Grouping by day is presentation only; never merge two exams because their dates match.
- The patient physically sees A, then B. Retain the current exam creation/editing flow; no new Start/Finish buttons, patient lock or live consultation-state system are required for the trial. Staff coordinate the order verbally.
- Going to another room verbally does not create a record by itself. B creates a separate exam when providing care; no transfer action or destination selection is needed.
- Do not infer actual consultation start/end times from form save times, or treat historical note editing as a live consultation. A doctor may finish documentation after the patient has moved on, so overlapping browser activity does not prove simultaneous care.
- Keep clinical completion and payment separate. Saving or completing an exam must preserve existing receipts, payment state and package balances.
- A failed save retains the browser draft and shows a clear failure. Do not present an unsaved note as saved, or silently store sensitive drafts on shared devices.

## 3. Ownership, Edited label and history

### Doctor access

- All doctors can search/read all patients, exams, images and relevant clinical history, as requested.
- Only the author identified by the exam's stable `created_by_id` may change that exam's clinical content. Do not infer ownership from doctor name, department, the browser or a form-supplied user ID.
- Enforce this in every write path: exam editing, image upload/removal, comparison saves/removals, appended summaries, clinical deletion and any API that changes the owning exam. Cross-department images can be read as comparison sources; the destination exam must belong to the current doctor.
- Creation sets ownership from the authenticated account on the server. Owner identity is immutable during ordinary editing. Administrator status alone must not bypass clinical ownership, including the existing admin exam-info tool.
- Preserve legacy owner IDs and resolve them against stable accounts. Deactivate accounts rather than recycling their IDs. Legacy exams with missing/unverifiable ownership remain readable and read-only until an explicit, audited owner-reconciliation process establishes ownership. Do not guess from a matching display name.
- Keep billing permissions separate from clinical ownership. Staff changing receipts must not gain permission to rewrite another doctor's clinical note.

### Visible edit tracking

- Initial creation is version 1 and is not labelled Edited. After a successful change to saved clinical content or attachments, increment its revision, set the edit timestamp and show **Edited** alongside the exam. A no-change save does not create a revision.
- Show “Edited by [doctor] at [time]” and a View edit history action. Administrative/payment events are separate audit events; they do not alone imply edited clinical content.
- History records stable exam ID, revision, actor ID/name, server timestamp, changed fields and before/after values or complete prior clinical snapshots. Preserve referenced attachment versions so history remains useful after image changes. Capture an optional correction reason.
- Save the clinical change and its history together in the same encrypted database update. A history-write failure must fail the edit as a whole. Exclude nested history itself when snapshotting to avoid recursive copies.
- History is append-only through ordinary application routes. All doctors can view clinical edit history under the shared-reading policy; ordinary users cannot rewrite or delete it. Local server administrators remain a separate trust boundary.
- An attempted unauthorized or stale edit must not change either the note or its history. Render old/new text safely rather than injecting it as HTML.
- Clinical removal uses a retained, attributed tombstone/history entry, not permanent destruction of previous versions. Restoring an older version is a new edit, not erasure of intervening history. Do not physically purge required attachments during the trial.

Receptionist permissions/page will be designed later. For now, expose only the existing operations required by each account; administrator tools, bulk exports, settings and billing require explicit permissions.

## 4. Server layout and security

```text
Staff browsers -- HTTPS/443 --> LAN reverse proxy
                                     |
                            Waitress on loopback
                                     |
                           One Flask process
                                     |
                     Encrypted TinyDB + patient files
                        on server-local storage

Coordinated backup job --> separate encrypted destination
                      --> offline/off-site recovery copy
```

- Use a dedicated server with a fixed address/internal DNS name, UPS, restricted physical access and disk encryption. Staff use browsers; they never open live database files over a shared folder. No cloud migration is required.
- Run one supervised app instance as a restricted service account, with fixed absolute data paths, startup after reboot, restart on failure and sanitized error logs. Prevent accidental launch of a second tray/service process against the same files.
- Use HTTPS with a certificate trusted by staff devices and monitored renewal. Keep Waitress's port private on loopback; permit HTTPS only from authorized staff networks and block guest Wi-Fi. Configure trusted proxy headers explicitly. No router port forwarding.
- Replace `admin/admin` startup with secure one-time bootstrap. Give staff individual accounts, password change/reset, deactivation, failed-login rate limits and session revocation on reset/disable. Use MFA for administrators where feasible.
- Keep debug off, enforce CSRF, use Secure/HttpOnly/SameSite cookies, set idle/absolute session expiry, and validate same-origin login redirects. Protect logout and other mutable actions with CSRF. Expired sessions must not produce false save success.
- Fix the raw-form audit logging before LAN use: `routes/core.py` nests form fields inside `form`, while `utils/db_logger.py` redacts only top-level secret keys. Passwords can therefore remain in plaintext logs. Replace raw payloads with allowlisted events; inspect existing logs under controlled access and rotate exposed credentials if found.
- General audit events include actor, action, record ID, timestamp, outcome and revision. Store clinical before/after values only in protected encrypted edit history, not plaintext request/error/access logs. Avoid search text, tokens, full clinical notes and patient-identifying URL parameters in general logs where possible.
- Apply authorization to APIs, files/PDFs, previews, search, exports, settings, drug administration, payments and restore. Image paths must resolve to a record the user is authorized to read. The reverse proxy must not serve uploads directly around these checks.
- Keep upload byte/pixel limits, real image validation and path containment; harden XSS, response headers and cache controls for patient pages/downloads. Add tested dependency pinning and an update process. Keep required browser assets local.
- Restrict Discord configuration to authorized administrators and disable clinical delivery for the LAN trial by default. Keep any later outbound disclosure subject to an explicit clinic sharing policy.
- Restrict plaintext decrypted exports and require reauthentication for sensitive admin actions. Encrypt/restrict uploads, PDFs, logs and backups as well as the TinyDB files. Keep recoverable copies of encryption keys separately protected; never print secrets during checks.

Flask documents Waitress as a multi-threaded server, so one process alone is not adequate write coordination: [Waitress deployment](https://flask.palletsprojects.com/en/stable/deploying/waitress/). Related repository guidance: [security hardening](security-hardening.md), [comparison files](image-comparison.md) and [change history](../changelog.md).

## 5. Safe file-based trial

TinyDB does not supply general concurrent access or ACID transaction guarantees; the trial needs application-level protections. See [TinyDB limitations](https://tinydb.readthedocs.io/en/latest/intro.html). These measures are planned work, not capabilities already present.

1. Centralize database access, including the separately opened purchases databases in drug/search routes. Use shared instances and defined cache invalidation/reload behavior; forbid external writers, parallel app instances and unsupervised migration scripts.
2. Use one common reentrant coordination mechanism for database reads and complete read-modify-write operations across all routes, authentication loading, background jobs, phone/file renames, backup and restore. A lock around only the final `write()` call cannot prevent stale decisions. Replace isolated feature locks with a consistent lock order to prevent deadlocks.
3. Use per-exam revisions and reread the latest patient under that coordination before updating the specific exam. Preserve other exams in the nested array. Include patient-level revisions where the operation touches demographics/packages. Two browser forms editing different exams must not replace each other's data.
4. Reject stale saves with a conflict response and retain the draft for comparison/re-entry. Check ownership again at commit. Use repeat-request protection for exam creation, payment and other non-idempotent actions.
5. Replace direct truncating file writes with encrypted temporary-file writes on the same volume, flush/sync, and atomic replacement with tested Windows failure handling. Never silently initialize a blank database after decryption, corruption or incomplete-write errors. Atomic replacement protects one file; it does not make several files transactional.
6. Save an exam's change, revision and encrypted edit-history event together. Preserve all existing UUIDs, author IDs, image references, comparisons, purchases, balances and unrelated fields. Add new fields with legacy defaults; do not rewrite historical meanings.
7. For operations spanning database files or media, stage changes and maintain a protected recovery journal/safety snapshots. Define startup reconciliation and rollback before allowing routine use. Test interruption between the exam paid flag and ledger write, and between media rename and database-reference updates. A common lock does not make a crash across these steps atomic.
8. Prepare expensive PDF/image work outside the critical section using an immutable input snapshot, then revalidate permissions/revision before committing generated references. Protect referenced file versions while jobs run. All actual writes must still participate in coordination.
9. Put backup/restore behind maintenance coordination, drain in-flight operations and reload all database instances after restore. Monitor lock waits, save latency, database/media size, failed writes and free disk space. Bound/reject overload clearly rather than falsely reporting a save.

Even though a patient sees only one doctor at a time, different patients can be treated simultaneously. Sequential consultations do not remove the shared-database concurrency risk.

Expand to 10 doctors only after representative concurrency and crash-recovery tests pass. If acceptable latency/recovery cannot be achieved, keep the pilot small and use its measurements to choose server-local SQLite or PostgreSQL later. Database-server migration is not a prerequisite for beginning the protected pilot.

## 6. Backup and recovery

Current weekly backups copy `db*.json` after write requests. They omit `money_log.json`, uploads, generated files and settings/templates, and do not create a coordinated recovery point. Replace that routine for the LAN trial.

### Complete recovery set

- All four encrypted databases: `db.json`, `db_services.json`, `money_log.json`, `db_mua_thuoc.json`, including new clinical edit history.
- `uploads/` including comparison sources, edited copies and sheets; `files/pdf/`, `files/jpeg/`; retained attachment versions; recovery journals and any other persistent data found during the storage inventory.
- `user_settings.json`, `exam_template.json`, required audit logs, application release ID, tested dependencies/PDF tooling, service/proxy configuration and restore instructions.
- Separately secured recoverable encryption/backup/disk keys and required credentials. Record key versions in backup metadata without putting plaintext keys in the manifest.
- Browser-only unsaved drafts and downloaded grid exports are not server records. Staff must attach required clinical output to the record to include it in server backup.

### Proposed schedule and targets

| Item | Trial proposal |
| --- | --- |
| Complete consistent recovery point | Every 15 minutes while operating, plus before updates; coordinate/drain writers and capture matching databases/files |
| Nightly recovery set | Verified full set or restorable full-plus-incremental chain; alert on missing files/failure |
| Separate destination | Encrypted backup on an independent device, protected from deletion by normal app credentials |
| Offline/off-site copy | Rotate at least daily; store keys separately |
| Starting retention | 48 hours of frequent points, 30 daily points, 12 monthly points; review storage and clinic retention obligations |
| Verification | Each run checks required files, integrity/checksums, age and free space |
| Full restore drill | Before pilot, monthly initially and after material storage/deployment changes |

Proposed targets: no more than 15 minutes of lost committed work after server failure and service restored within 4 hours. They are targets to prove, not guarantees. Frequent backups must include associated attachments and edit history, not just databases. Capture manifests under a coordinated pause or supported snapshot method, then copy/verify immutable snapshot files outside the pause. Measure pause duration; if it disrupts care, redesign snapshot storage or revise the target explicitly.

Use three copies across two storage types, one off-site and offline/immutable. A second folder on the server disk is insufficient. Daily off-site rotation can lose up to a day after a whole-site incident; a 15-minute site-loss target needs equally frequent protected off-site recovery points. Four-hour recovery depends on available replacement hardware and keys. Backup rotation does not replace clinical record retention policy. See [CISA backup guidance](https://www.cisa.gov/stopransomware/ransomware-guide).

### Restore procedure

1. Block writers and use the downtime procedure; isolate a compromised server. Select a known-good complete recovery point.
2. Restore matching application/configuration, databases, media and keys to an isolated replacement. Keep outbound Discord delivery disabled.
3. Verify decryption/integrity, IDs/counts, financial totals, exam ownership/history and sampled images/PDFs. Reconcile any incomplete operation journal before care resumes.
4. Check doctor read/edit permissions, account/session safety and edits/payments made after the selected point using paper records. Do not silently discard new work.
5. Switch the LAN service only after validation. Reload/restart all data connections, monitor operation and record measured loss/recovery time.

The existing per-file restore UI needs maintenance blocking, whole-set prevalidation, a safety snapshot and coordinated rollback on failure before use on a busy service.

## 7. Delivery order and acceptance

| Stage | Result | Acceptance |
| --- | --- | --- |
| 1. Protect existing data | Complete inventory/backup, verified restore, fix secret logging/default credentials | Current records and attachments restore on a separate machine without plaintext secret leakage |
| 2. Make file access reliable | Central access/coordination, atomic writes, revisions, multi-file recovery | Concurrent changes, retries, interruption and recovery preserve clinical and financial data |
| 3. Apply clinical rules | Own-exam editing and Edited label/history using the existing exam flow | Two same-day department exams stay separate; direct unauthorized writes fail; staff can coordinate sequential care without transfer records |
| 4. Deploy protected LAN pilot | HTTPS, supervised service, firewall, individual accounts, scheduled backups/alerts | Real browsers/devices work; recovery drill and security boundaries pass |
| 5. Expand gradually | Small doctor group first, then up to 10 plus actual support users | Measured responsiveness and safe saves remain acceptable under representative work |

Required checks include:

- Doctor A and Doctor B both read all history. A can edit A's exam and see Edited/history; B cannot change A's record through forms, APIs, images, comparisons or the admin-info route.
- Two different patients and two different exams within one patient can be saved without lost updates; competing edits to the same exam produce a conflict. Client-supplied ownership/revisions cannot bypass checks.
- One patient sees Eye then Nutrition on the same date, producing two doctor-owned records. A may complete documentation after B begins care without merging or overwriting their records. Verbal redirection creates no transfer record.
- Initial creation and no-change saves do not show Edited. Subsequent clinical edits preserve prior values, actor/time and attachment versions; failed edits leave no partial history.
- Editing a note preserves receipts and package balances. Retried payments cannot create duplicates. Crash injection between multi-file steps yields a recoverable state.
- Network/session failure, app restart, disk-full and simulated interrupted replacement on disposable data never report false save success or erase records.
- Ten doctors plus expected support users can search/save/upload and read history with agreed latency. Browser/device acceptance is measured separately from automated checks.
- Guest access/direct backend access are blocked, certificates are trusted, protected files are authorized, and a separate machine restores the whole set within the measured target. Failed backups cause a visible alert.

Use synthetic/de-identified data for automated/load/crash tests. Existing data must be preserved through additive changes and a staged pilot; do not edit encrypted database files directly. After accepting new live work, rollback must retain/reconcile that work instead of simply restoring an older snapshot.

## 8. Later work and remaining operational details

- Receptionist page, queues/check-in and optional arrival tracking: design later with the owner.
- Formal transfer/referral workflow and mandatory signing/parent visit lifecycle: outside this trial's requirements.
- Database migration: evaluate only after trial results or demonstrated operational need; retain an access layer to make it feasible.
- Confirm actual departments/support users, payment responsibilities, server/UPS/backup hardware, backup operator/deputy, tolerated downtime/data loss and clinic retention/sharing policy as deployment details become available.

Next implementation slice: complete recovery coverage and fix secret logging/bootstrap, then protect file access and implement exam ownership/history. This revision changes the plan only.
