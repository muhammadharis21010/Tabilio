# TABLIO - Food Ordering Management System
Beyond Dining. Smarter Restaurant Management.

Stack: Python 3 + Flask, MySQL (PyMySQL), HTML5 / CSS3 / JavaScript, `qrcode` library.

## Run
1. Install MySQL and start it. Then: `pip install -r requirements.txt`
2. Set DB details if needed (defaults: localhost / root / empty password / db `tablio`):
   `export DB_USER=root DB_PASSWORD=yourpass SECRET_KEY=something-long`
   (Windows PowerShell: `$env:DB_PASSWORD="yourpass"`)
3. `python init_db.py`  (creates tables, sample menu, tables, 4 staff accounts)
4. `python app.py` and open http://localhost:5000
   For phones to scan QR codes, open the site using your PC's LAN IP (e.g. http://192.168.1.5:5000) so the QR points to it.

## Default logins (change them!)
admin/admin123, waiter/waiter123, kitchen/kitchen123, cashier/cashier123

## Implemented features
Customer: QR code per table, digital menu, deals banner, order placement, per-item customization, live order tracking, call waiter, feedback.
Staff: kitchen display (placed -> preparing -> ready), live floor map with waiter calls, waiter marks served, cashier billing (discount, tax, cash/card/online), digital receipt.
Admin: dashboard (sales, top items, ratings), CSV sales report, manage menu/deals/staff/tables.

## Not implemented (future work only)
Multiplayer games, Wi-Fi integration, loyalty program, prep scheduling, smart notifications, AI recommendations, advanced analytics.

## Known limits
No CSRF tokens, no real payment gateway (payment is recorded by the cashier), food photos via image URL only. Menu items show a letter placeholder until an image URL is added.
