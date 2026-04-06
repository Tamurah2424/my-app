# Companion Booking MVP

A small Flask starter app for a lawful companion booking / reservation service MVP.

## Included
- Cast listing page
- Cast detail page
- Booking request form
- Basic overlap prevention for time slots
- Simple admin booking management page
- SQLite database with seed data

## Notes
This starter is intentionally framed for legal, non-adult companion reservations. Before any real launch, add legal review, identity verification, moderation, terms, and local compliance checks.

## Run locally
```bash
cd companion_booking_mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Then open `http://127.0.0.1:5000`.

## Main files
- `app.py` - Flask routes, schema, booking logic
- `templates/` - HTML views
- `static/styles.css` - styling
- `booking.db` - created automatically on first run

## Suggested next features
- User authentication
- Cast-side dashboard
- Stripe payments
- Chat / messaging
- Review system
- Availability calendar
- Admin authentication and audit logs
- Automated tests
