# QKB Feature List

This list summarizes the user-facing and operational features recorded in [changelog.md](./changelog.md).

## Patient and Exam Management

- Create, edit, and manage patient records.
- Normalize and validate patient phone numbers.
- Detect duplicate patient phone numbers before saving changes.
- Store multiple exam records for each patient.
- Create and edit exams with department, doctor, visit date, notes, drugs, and services.
- Preserve separate same-day exams for each department.
- View patient exam history with drug details, service details, and service totals.
- Assign and display departments and exam creators for historical and current exams.
- Assign legacy exams to a recognized doctor record.
- Edit exam notes while preserving payment status and prepaid-package allocations.
- Display **Edited** status for modified exam records and retain encrypted change history.
- Preserve removed exams and attachments in history.
- Protect referenced images and exams from unsafe deletion.
- Mark exams as paid or unpaid and keep payment status synchronized across views.
- Prevent duplicate payment receipts during payment retries.
- Add manual exam total overrides and respect override/package discounts in billing and PDFs.

## Drug and Inventory Management

- Add, edit, search, and manage drugs.
- Record drug cost and selling prices without silently clearing decimal values.
- Use recorded purchase unit prices as drug cost, with purchase-total/quantity fallback.
- View all-time purchase history for a drug.
- View prescribed quantities and calculated inventory for a drug.
- Calculate inventory from purchases and patient exam prescriptions while excluding opening stock, returns, and adjustments.
- Sort purchase history by date and match normalized exact drug names.
- Prevent similarly named drug strengths from being combined in stock calculations.
- Preserve existing manual inventory and quantity fields.
- Manage purchase orders and purchase statuses.
- Use the omni-search dashboard to find drugs and inspect recent purchase details.
- Calculate suggested stock using sales, purchase, and lead-time data.
- Compare drugs sold with drugs purchased over a selected period.
- Generate a standalone mobile drug-list HTML with a quick-subtotal calculator.
- Export only drug name, sell price, and cost price as a password-encrypted catalog for manual Cloudflare R2 publishing.
- Load the latest encrypted catalog through a read-only Cloudflare Worker and decrypt it locally in the calculator.
- Accept natural-language and optional voice input for quick drug quantity estimates.
- Support fallback searchable product selection for unresolved subtotal items.

## Services and Prepaid Packages

- Maintain a service and department database.
- Create, edit, and delete departments and services.
- Select multiple services while creating or editing an exam.
- Calculate service totals and exam totals in real time.
- Apply manual total overrides.
- Store prepaid packages on patient records.
- Create and manage prepaid package purchases and remaining sessions.
- Tie packages to a specific service and package price.
- Automatically apply a matching package and decrement remaining sessions during exam billing.
- Allocate package sessions proportionally across drug, service, and exam billing where applicable.
- View package usage history.
- Include services and package-adjusted totals in generated PDFs.

## Image and PDF Workflow

- Upload multiple exam images and resize them before storage.
- Preview selected and existing images.
- View, enlarge, delete, and protect exam images.
- Normalize image paths for Windows and maintain safe unique upload names.
- Batch rename patient image folders, image filenames, PDFs, and exam references when a phone number changes.
- Preview old and new patient asset names before applying a phone-based rename.
- Open renamed images and PDFs in in-app preview dialogs.
- Download and export exam-related documents.
- Compare a selected patient image with a lighting reference and baseline visit.
- Adjust original or adjusted images with brightness, contrast, crop, zoom, and pan controls.
- Add and toggle normalized reference-patch overlays.
- Generate optional numbered patch suggestions and require clinician selection.
- Create and label comparison sheets.
- Save and reopen image-comparison work.
- Append a previewed comparison summary to a selected exam note.
- Preserve original images while creating optional edited JPEG copies.
- Export comparison work as a ZIP containing metadata and attachments.
- Open a fitted, polished desktop image-comparison workspace with adjustment, grading, and save tabs.
- Use modular mMASI v1 regional scoring with validation and baseline comparison.
- Keep POSAS available as a paper-attachment workflow.
- Open the selected-image Tools menu with comparison and image-grid actions.
- Create 1-6 row and 1-6 column image grids with up to 36 originals.
- Configure square, landscape, or portrait cells.
- Configure spacing, background, cell swap, independent zoom/pan, fit/fill, and movable custom text.
- Download grid exports as PNG without altering or automatically saving originals.

## Exam List and Reports

- Display an exam list with department and creator tags.
- Show unpaid exams in a scrollable top panel across all history.
- Sort unpaid exams newest-first or oldest-first without a page reload.
- Filter exam data by one or more months.
- Revert to the latest three months when no month is selected.
- Show real-time totals for cases, received payments, outstanding payments, and expected payments.
- Synchronize payment changes across all exam-list views.
- Generate drug sold and purchase comparison reports.
- Provide a printable money-flow report with received amounts, dates, and users.
- Export reports and exam documents for browser printing or PDF output.

## Search and Navigation

- Use a mobile-first homepage with an omni-search panel.
- Search patients, exams, drugs, and purchase orders in one request.
- Trigger live search after three characters with debounce and Enter support.
- Abort stale search requests.
- Group and rank search results with Vietnamese-aware and fuzzy matching.
- Show relevant patient, exam, drug, and purchase previews with direct actions.
- Provide responsive navigation and mobile-friendly controls.

## Accounts and Security

- Require authentication for application routes.
- Use Flask-Login sessions and role-based access control.
- Bootstrap the initial administrator account securely.
- Change passwords and reset account passwords.
- Deactivate accounts and revoke active sessions.
- Apply login rate limits.
- Protect all mutable actions with global CSRF tokens.
- Protect logout with CSRF.
- Sanitize audit logs and prevent clear-text credential logging.
- Allowlist Discord webhook domains to prevent webhook SSRF.
- Reject invalid Discord webhook URLs at configuration and send time.
- Disable Discord sending and plaintext exports by default.
- Keep database encryption keys separate from encrypted database files.
- Support a separate, headless loopback server for LAN/Desktop use.
- Provide an HTTPS proxy example for LAN deployment.

## Encrypted Storage, Backup, and Recovery

- Encrypt TinyDB database files at rest with AES-GCM storage.
- Centralize shared database instances to reduce Windows file-lock conflicts.
- Use atomic writes and a recovery journal for coordinated LAN operations.
- Detect stale exam revisions during concurrent editing.
- Track before/after change history in encrypted form.
- Create database checkpoints before patient asset renames.
- Restore checkpoints through an admin-only interface.
- Preview checkpoint diffs with record-level, GitHub-style added/removed/changed lines.
- Create a pre-restore safety copy before overwriting live databases.
- Export or download encrypted and portable database backups.
- Include the payment ledger, patient files, and settings in verified backups.
- Reuse encrypted backup blobs for scheduled restore points.
- Retain backup history and support coordinated/offline restore workflows.
- Provide database decryption and export tools for administrators.
- Generate decrypted exports for download while displaying handling warnings.
- Detect database files dynamically for export.
- Save and decrypt backups safely for recovery operations.

## Administration and Settings

- Use an admin dashboard for user and role management.
- Add and edit users and assign departments.
- Remove departments and reset assigned users to an unassigned state.
- View database-management and checkpoint tools.
- Configure Discord webhook URL and notification preferences.
- Enable or disable automatic Discord sending for new and edited exams.
- Send formatted exam reports to Discord.
- Manage department and service settings.
- Configure application display and workflow settings.
- View changelog and project documentation from the application.

## Desktop, Mobile, and Offline Experience

- Provide a mobile-first, responsive interface.
- Use a premium offline-first client-side exam-list experience.
- Keep core image-comparison and grid-editing work local in the browser.
- Use touch-optimized controls and larger mobile targets.
- Support the Flask app through a desktop tray/startup path.
- Bundle image-grid/editor dependencies for offline use.
- Preserve existing exam functionality while remaining compatible with older records.