# V 0.15 plan:
## Package management UI
Pre-paid Packages: Partially Implemented
The feature is partially implemented — the backbone exists but package management UI is missing.

What EXISTS (Code that's implemented):
exam.py — Service/package logic:

_collect_services_from_form() function (lines 56-87) handles applying package discounts to services
When a service matches a patient's package, it uses the package's unit_price and decrements remaining_sessions
Packages are read from patient.get('packages', []) in both new_exam() and edit_exam() routes
edit_exam.html — Display only:

Shows available packages in read-only format (lines 173-180)
Displays: "X sessions of ServiceName (unit_price)"
Package data structure (stored in patient record):

What's MISSING (Not implemented):
❌ No package creation/edit UI — The changelog explicitly states:

"Package management (creation/edit) will be exposed on the patient profile page in an upcoming iteration." ✅ IMPLEMENTED

❌ No endpoint to create packages ✅ IMPLEMENTED
❌ No endpoint to edit/update packages ✅ IMPLEMENTED
❌ No UI on patient profile to manage packages ✅ IMPLEMENTED
❌ Packages can only exist if manually added to the database ✅ FIXED
Current State:
The feature is a "read-only" partial implementation — packages work if they exist in a patient's record, but there's no way to create them through the UI. This would require adding package management endpoints and UI to the patient profile page.

### My plans:
1. Endpoint to create packages: a button for each patient in patient list(/patients - in "Thao tac" column)
2. Edit / Update / Remove: same at ppoint 1 - add new or edit existing package
3. In Thao Tac column, there is a view for usage
I think a table - Pakage buy date - Service 1 (total quantity) - Service 2 (quantity) -...
list:
Date - Service 1 (number / total)
4. A separate total service use, so I can track which is the most use service

### Draft
Draft implementation plan
This is a good structure: keep the existing service add/search UI, and add a second “Existing package” table that can push selected package usage into the service table.

1. Data model changes
Add package fields
Extend patient.packages to include:

service_id
service_name
unit_price
remaining_sessions
expires_at (optional)
purchase_date or created_at (optional)
Example:

If expires_at is missing, treat the package as unlimited.

2. Files to modify
new_exam.html
Add a new package section above or beside the service selector.
Show a table with:
service name
total sessions purchased
used / available
expiry date
“Use” button
Render packages from the route context like currently done in edit_exam.html.
edit_exam.html
Mirror the same package UI so package usage is visible when editing.
Use the same package table and “Use” button behavior.
new_exam.js
Add package rendering logic.
Add a handler for package “Use” button:
when clicked, insert a service row into the existing service table
prefill quantity, price, service id/name, note, prepaid flag
Ensure the hidden form inputs include:
service_id
service_name
service_price
service_quantity
service_note
maybe service_prepaid=true or service_prepaid_status=...
Update calculateTotals() if needed to include service quantity and package pricing correctly.
If edit_exam.html uses a different JS file, mirror the changes there too; otherwise use the shared new_exam.js logic.

exam.py
Edit these functions:

new_exam()
edit_exam()
_collect_services_from_form()
Suggested changes:

Extract exam_date from the form and pass it into _collect_services_from_form() so expiry can be checked.
In _collect_services_from_form():
read service_quantity from form
if a package matches and is active/available:
use pkg['unit_price']
decrement pkg['remaining_sessions'] by the selected quantity
if quantity exceeds remaining sessions, either:
reject/save only available amount
or prevent the package use in UI
Add helper functions such as:
_package_is_active(pkg, exam_date)
_apply_package_to_service(pkg, quantity)
_package_display_status(pkg, exam_date)
Also:

when POST saves the exam, persist updated patient_packages to the patient record if sessions changed.
3. Print / PDF / JPEG support
template_renderer.py
This already has service row rendering with prepaid_status, so use that:

build_service_rows_markdown()
build_service_rows_html()
You should ensure the saved service object contains:

quantity
price
prepaid_status like "PAID PACKAGE"
maybe package_used: true if you want a dedicated marker
exam_template.json
Current default template already includes:

service_row_template: | {index} | {name} | {quantity} | {price} | {prepaid_status} |
So:

if you want to hide package rows in print-template management later, add a new field such as {package_label} or show_prepaid and conditionally render it.
keep the default service rows visible in PDF, but mark package-sourced rows clearly.
exam.py and pdf_generator.py
No structural change is needed if the exam object already stores service rows with quantity and prepaid_status. The generator will render them automatically if the template supports those fields.

4. Recommended UI flow
Doctor opens new_exam or edit_exam
They see:
current package list
status for each package:
available sessions
expiry date
expired/active
Doctor clicks Use on one package
The package is added into the normal service table
quantity editable
price automatically set to package unit price
a prepaid badge appears in the row
On save:
if package used, decrement remaining_sessions by quantity
if expired / zero left, fall back to normal price
5. Minimal function additions
Suggested helper names:

def _package_is_expired(pkg, exam_date):
def _package_can_cover(pkg, quantity, exam_date):
def _consume_package(pkg, quantity):
def _package_display_label(pkg, exam_date):
def _collect_services_from_form(form, patient_packages, exam_date):
6. What to do later
If you want a hide-in-print option:

add a show_in_print attribute on service rows
update build_service_rows_html() / markdown so package rows can be hidden if that attribute is false
update exam_template.json with a placeholder or row template that supports conditional display
Summary
Modify
new_exam.html
edit_exam.html
new_exam.js
exam.py
template_renderer.py
exam_template.json
Add
package display table
“Use” button behavior
package expiry + remaining session logic
quantity-aware package consumption
prepaid marker for print/PDF
This keeps the existing service/drug flow intact and adds a clean package-first workflow that feeds into the existing exam save/print pipeline.

# Processed

## Implementation Summary (Completed May 9, 2026)

### Files Modified:

1. **`routes/exam.py`**:
   - Added helper functions: `_package_is_active()`, `_package_display_status()`
   - Updated `_collect_services_from_form()` to handle quantity, notes, and package application
   - Modified `new_exam()` and `edit_exam()` routes to enrich package data with status
   - Added logging after each function to show processing details (print statements)

2. **`templates/new_exam.html`**:
   - Replaced simple package list with a detailed table showing service name, total sessions, remaining, unit price, expiry, status, and "Use" button

3. **`templates/edit_exam.html`**:
   - Same package table as new_exam.html
   - Added package "Use" button handler in inline JS

4. **`static/new_exam.js`**:
   - Added package "Use" button handler that prompts for quantity and adds service rows from packages
   - Includes validation for remaining sessions

5. **`routes/patients.py`**:
   - Added `manage_packages()` route for CRUD operations on patient packages
   - Added `view_package_usage()` route for package usage statistics and history
   - Imported services_table for service selection in package creation

6. **`templates/patients.html`**:
   - Added "Quản lý gói" (Manage Packages) and "Xem sử dụng gói" (View Package Usage) buttons to the "Thao tác" column

7. **`templates/manage_packages.html`** (New):
   - Package creation form with service selection dropdown
   - Current packages table with edit/delete functionality
   - Modal dialog for editing existing packages
   - JavaScript for auto-filling service details from selection

8. **`templates/package_usage.html`** (New):
   - Package purchase history table with session tracking
   - Service usage statistics (total, package vs regular visits)
   - Usage percentage calculations and status indicators

### Key Features Implemented:

- **Package Display**: Shows active packages in a table with expiry and status
- **Package Usage**: "Use" button allows selecting quantity from available sessions
- **Automatic Pricing**: Uses package unit_price when applying services
- **Session Tracking**: Decrements `remaining_sessions` when packages are used
- **Expiry Handling**: Checks `expires_at` against exam date
- **Print Support**: Services include `prepaid_status` for PDF/JPEG templates
- **Logging**: Added print statements after each function showing what was processed

### Data Model:
Packages now support:
```json
{
  "service_id": "...",
  "service_name": "...", 
  "unit_price": 150000,
  "remaining_sessions": 5,
  "expires_at": "2027-03-07"  // optional
}
```

### UI Flow:
1. Doctor sees package table in exam page
2. Clicks "Use" on active package
3. Prompts for quantity (max = remaining)
4. Adds service row with package pricing
5. On save, decrements package sessions

### Status:
✅ Package usage in exams is fully functional
✅ Package creation/edit UI implemented
✅ Package management endpoints added
✅ Package usage statistics implemented

The package management feature is now complete with full CRUD operations and usage tracking.
