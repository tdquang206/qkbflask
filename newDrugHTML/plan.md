# Drug Catalog HTML and Cloudflare Publishing Plan

## Goal

Create a mobile-friendly HTML drug list with a quick-subtotal calculator. The page should load the latest catalog from Cloudflare rather than relying on data embedded when the HTML was first generated.

## Catalog scope

Publish only:

- Drug name (`name`)
- Sell price (`sell`)
- Cost price (`cost`)

Do not include patient data, purchase history, stock, internal notes, or other database fields.

## Implemented design

1. The app builds the catalog from current drug data. Cost uses the latest recorded purchase unit price when available, otherwise the drug's stored buy price.
2. The app encrypts the catalog with PBKDF2-HMAC-SHA256 and AES-256-GCM using a fresh salt and nonce for every export.
3. An admin/pharmacist downloads the encrypted file and manually uploads/replaces `drug_catalog.enc.json` in a private Cloudflare R2 bucket.
4. Download the standalone calculator HTML once and send it directly to colleagues through a messaging app.
5. A read-only Cloudflare Worker serves the latest ciphertext from the private bucket.
6. The HTML downloads the ciphertext, prompts for the shared decryption password, and decrypts locally in the browser. The password is not sent to Cloudflare or embedded in the HTML/catalog.
7. The calculator keeps decrypted data in memory, displays the update timestamp, and does not persist the password or plaintext catalog.

The encrypted file may be readable by anyone who can reach the Worker, but it reveals no catalog contents without the password. Keep the R2 bucket private and have the Worker serve only the ciphertext.

## Publishing options

- **Initial/manual:** Generate the encrypted catalog and upload it using the Cloudflare dashboard.
- **Automated/later:** Add an authenticated upload endpoint to the Worker. Keep its upload token in the application/server environment, never in browser code. Restrict uploads to the expected catalog format and replace the published catalog atomically.

## Security and reliability notes

- Do not reuse the app's database-encryption key.
- Keep the decryption password separate from Cloudflare upload credentials and share it with colleagues through a separate channel.
- A shared password can be forwarded. Rotate it when access needs to be revoked; users who already decrypted a catalog may retain a copy.
- Anyone who can modify the hosted HTML could potentially capture a password entered into it. Protect Cloudflare account access and the publishing path.
- Consider cache behavior/versioning so that users can tell whether they have the latest catalog.
- Handle incorrect passwords, corrupt/tampered files, network errors, and unavailable catalog data explicitly.
- A password-protected PDF could be offered as a separate dated snapshot, but it is not suitable as the live data source for the calculator.

## Cloudflare setup

- Create/access the Cloudflare account that will own the project.
- Create a private R2 bucket, for example `qkb-drug-catalog`.
- Deploy `cloudflare-worker.js` and bind the bucket to the Worker as `CATALOG_BUCKET`.
- Set `CATALOG_URL` in `index.html` to the Worker URL before sending the HTML.
- Upload the downloaded encrypted file to the bucket with the exact object key `drug_catalog.enc.json`.
- No Pages site or upload API is needed for this manual-publish version.
- Do not share account credentials, API tokens, or the catalog password in source control or chat.

## Decisions and current status

- Publishing: **manual**, by replacing the encrypted JSON object in R2.
- HTML distribution: send the standalone HTML directly to colleagues through a messaging app.
- Catalog fields: **name, sell, cost**.
- The app export route, encryption utility, standalone calculator, and read-only Worker source are implemented.
- Remaining setup: create the R2 bucket, bind it to the Worker, deploy the Worker, set the calculator URL, upload the first catalog, and distribute the configured HTML.
- Test incorrect passwords, tampered files, catalog replacement/update time, and mobile browser behavior.