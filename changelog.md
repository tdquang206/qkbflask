# Version 0.3.170126 (2026-01-17)

## Project Analysis & Summary
- Integrated Discord notifications directly into the exam workflow.
- Centralized configuration in a new Settings page.
- Polished UI with toast notifications and improved defaults.

## New Features
- **Discord Integration**:
  - Global "Settings" page to configure Webhook URL and content preferences.
  - "Auto-send" checkbox in `New Exam` and `Edit Exam` pages (checked by default).
  - Backend helper to format and send detailed exam reports to Discord (Date, Name, Drugs, Image, etc.).
- **UI Polish**:
  - Added global Toast Notifications for better feedback.
  - "Send to Discord" is now enabled by default.

# Version 0.2.260116 (2026-01-16)

## Project Analysis & Summary
- Refined "Manage Drugs" UI with a modern dark theme and improved layout.
- Debugged and resolved exam data mismatches and ID collisions.
- Standardized database access to prevent UTF-8 encoding errors on Windows.

## New Features
- **Enhanced Drug Screen UI**: 
  - Consolidated "Manage Drugs" title, "Add New Drug" button, and search box into a single, sticky row.
  - Redesigned "Add New Drug" modal with a vertical layout for better readability.
  - Improved contrast for search and input placeholders in dark mode.
  - Added modern styling for drug tables with highlighted prices and hover effects.

## Fix 
- **Exam Management**:
  - Fixed a critical bug in `edit_exam` that caused incorrect record updates due to ID mismatch.
  - Resolved `UnicodeDecodeError` in the exam list view by enforcing UTF-8 encoding across all database handles.
  - Improved `total_money` calculation logic to handle empty or malformed price strings robustly.
  - Fixed duplicate/missing exam IDs in the database for existing records.
- **System Stability**:
  - Implemented `shared_db.py` to centralize TinyDB initialization and prevent file handle conflicts.
- **Other**:
  - Fix "Print" vs "PDF" content mismatch in Exam page.
