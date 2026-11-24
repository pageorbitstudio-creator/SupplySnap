# SupplySnap

A mobile-friendly inventory replenishment MVP built with Flask, SQLite, Flask-Login and QR codes. It adds a lightweight replenishment workflow without replacing existing suppliers or procurement systems.

## Features
- Role-based accounts: admin, purchasing manager, employee
- Product and supplier directory
- Unique QR code per product; downloadable as PNG
- QR-linked prefilled reorder form
- Duplicate pending-request detection and flagging
- Manager approval/rejection workflow
- Supplier email after approval (SMTP, or console logging in development)
- Dashboard, low-stock indicators and basic reorder reports
- Responsive modern UI

## Requirements
- Python 3.10+
- pip
- Optional SMTP account for sending real supplier emails

## Windows setup (PowerShell)
```powershell
cd SupplySnap
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```
Open http://127.0.0.1:5000

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## macOS / Linux
```bash
cd SupplySnap
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

## Demo login
- Email: `admin@supplysnap.local`
- Password: `Admin123!`

When using the default local SQLite database, the first run creates sample suppliers and products. The demo account and credentials are for local SQLite evaluation only; a Neon/PostgreSQL database never receives the demo account or sample products. In Vercel, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` to create the first administrator.

## First-use walkthrough
1. Sign in as the demo admin.
2. Open **Suppliers** and add the business's existing supplier email contacts.
3. Open **Products** and add products, SKU, stock, reorder quantity, unit price and supplier.
4. Use the QR icon in the product row to download its QR PNG. Print and attach it to the relevant shelf or bin.
5. An employee signs in, scans the QR with a phone camera (or opens the QR URL), and submits a quantity.
6. A manager/admin opens **Reorder requests**, reviews possible duplicate flags, then approves or rejects.
7. On approval, SupplySnap sends an email to the product's assigned supplier. Without SMTP settings, the email content is logged to the Flask console and the request is marked as notified in this demo mode.

## Configure real email (optional)
Edit `.env`:
```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-sender@gmail.com
MAIL_PASSWORD=your-16-character-app-password
DEFAULT_SENDER=your-sender@gmail.com
```
For Gmail, use a Google App Password (requires 2-Step Verification), not your normal account password. Never commit `.env`. If mail credentials are absent, email is logged locally rather than transmitted.

## Deploy to Vercel

See [DEPLOY_TO_VERCEL.md](DEPLOY_TO_VERCEL.md) for a step-by-step guide. Vercel's local function filesystem is temporary, so use a hosted PostgreSQL database instead of the local SQLite database. The guide sets up the first administrator using environment variables; the demo login is only created for local SQLite development. The app creates its database tables at startup, but this project does not include database migration or backup automation.

## Database
SQLite is created automatically in `instance/supplysnap.db`. Tables:
- `user`
- `supplier`
- `product`
- `reorder_request`

To reset demo data, stop the server and delete `instance/supplysnap.db`, then restart. This permanently deletes local application data.

## Testing checklist
Manual end-to-end test:
1. Log in with demo admin credentials.
2. Add a supplier with an email address you control.
3. Add a test product with stock `2`, reorder level `5`, reorder quantity `8`, and assign the supplier.
4. Download its QR code and open/scan it. Confirm product information and suggested quantity are prefilled.
5. Submit quantity `8`. Confirm the request appears as Pending.
6. Submit another request for the same product before reviewing the first. Confirm the new request is flagged as a possible duplicate.
7. Approve the first request as admin. Confirm supplier notification status and check console logs (or inbox with SMTP configured).
8. Reject the second request. Confirm statuses.
9. Create an employee from **Team** and verify the employee sees their own requests but cannot access management pages.
10. Check responsive layout using a mobile browser viewport.

## Important MVP notes / production hardening
- This is a runnable MVP, not a security-audited production procurement system.
- Before deployment: use a strong random `SECRET_KEY`, HTTPS, PostgreSQL, database backups, CSRF protection (e.g. Flask-WTF), login rate limiting, password reset, audit logging, email retry/outbox, and secure secrets management.
- Configure a production WSGI server (Gunicorn/waitress); do not run Flask debug mode in production.
- The approval workflow does not decrement stock automatically because actual stock changes should be confirmed on receipt.
- Duplicate detection flags another pending request for the same product; it does not silently discard requests.
- Supplier email is an email-based purchase request, not a purchase order integration or confirmation from the supplier.
