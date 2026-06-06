# check cost and sell price after creating drugs purchase order

1. drugs purchase link: http://127.0.0.1:5000/mua_thuoc
2. after completed / save that order, run a check for each drug in the saved purchase
   - if new cost > (0.8 * current sell price) => send a note to notification area (icon at bottom right)
   - note content: "check sell price", plus a direct link to edit drug page `/edit_drug/<drug_id>`
   - else: nothing happens

## Implementation details for changelog

- Added shared helper `utils/drug_notifications.py`.
  - normalizes purchase drug names and matches them against `shared_db.drugs_table`.
  - uses exact normalized matching first, then fuzzy name matching with a threshold of 80.
  - ignores drugs with invalid or missing decimal prices.
  - generates warning objects only when `buy_price > 0.8 * sell_price`.
  - returns `edit_path` for `/edit_drug/<drug_id>` without touching `db_mua_thuoc.json` directly.

- Updated `routes/mua_thuoc.py`.
  - imported `build_price_notifications`.
  - after new purchase save (`POST /mua_thuoc`) and after purchase update (`PUT /mua_thuoc/edit/<uuid>`), it now attaches `notifications` to the JSON response.
  - preserved the existing purchase create/edit flow and response format for normal success behavior.

- Refactored notification UI into `static/notifications.js`.
  - moved `showNotification()` and global fetch interception out of `templates/base.html`.
  - warning entries now render in the existing bottom-right notification panel.
  - kept existing error logging behavior intact.

- Encrypted storage compatibility.
  - the new helper only reads from `shared_db.drugs_table`.
  - it does not open an additional `db_mua_thuoc.json` encrypted connection, so encrypted JSON storage remains unchanged.
