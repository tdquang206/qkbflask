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
