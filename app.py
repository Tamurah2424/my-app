from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'booking.db'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-change-me'


CAST_SEED = [
    {
        'name': 'Airi',
        'age': 24,
        'area': 'Tokyo / Shibuya',
        'hourly_price': 12000,
        'bio': 'Friendly companion for cafe dates, shopping, and events. Calm conversation style.',
        'tags': 'Cafe, Shopping, Weekend',
        'image_url': 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=800&q=80',
    },
    {
        'name': 'Mio',
        'age': 27,
        'area': 'Tokyo / Ginza',
        'hourly_price': 15000,
        'bio': 'Elegant companion for dining, business social events, and city walks.',
        'tags': 'Dining, Events, Elegant',
        'image_url': 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?auto=format&fit=crop&w=800&q=80',
    },
    {
        'name': 'Rina',
        'age': 23,
        'area': 'Yokohama',
        'hourly_price': 10000,
        'bio': 'Bright and active companion for amusement spots and casual meetups.',
        'tags': 'Casual, Outdoors, Active',
        'image_url': 'https://images.unsplash.com/photo-1488426862026-3ee34a7d66df?auto=format&fit=crop&w=800&q=80',
    },
]


def get_db() -> sqlite3.Connection:
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc: Exception | None) -> None:
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db() -> None:
    schema = '''
    CREATE TABLE IF NOT EXISTS casts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        area TEXT NOT NULL,
        hourly_price INTEGER NOT NULL,
        bio TEXT NOT NULL,
        tags TEXT NOT NULL,
        image_url TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cast_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        booking_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        duration_hours INTEGER NOT NULL,
        location TEXT NOT NULL,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cast_id) REFERENCES casts(id)
    );
    '''
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(schema)
        count = conn.execute('SELECT COUNT(*) FROM casts').fetchone()[0]
        if count == 0:
            conn.executemany(
                '''
                INSERT INTO casts (name, age, area, hourly_price, bio, tags, image_url)
                VALUES (:name, :age, :area, :hourly_price, :bio, :tags, :image_url)
                ''',
                CAST_SEED,
            )
        conn.commit()


def validate_booking(form: dict[str, str]) -> tuple[bool, str | None]:
    required = ['customer_name', 'customer_email', 'booking_date', 'start_time', 'duration_hours', 'location']
    for key in required:
        if not form.get(key, '').strip():
            return False, f'{key} is required.'

    try:
        booking_date = datetime.strptime(form['booking_date'], '%Y-%m-%d').date()
        if booking_date < datetime.now().date():
            return False, 'Booking date must be today or later.'
    except ValueError:
        return False, 'Invalid booking date.'

    try:
        datetime.strptime(form['start_time'], '%H:%M')
    except ValueError:
        return False, 'Invalid start time.'

    try:
        hours = int(form['duration_hours'])
        if hours < 1 or hours > 12:
            return False, 'Duration must be between 1 and 12 hours.'
    except ValueError:
        return False, 'Duration must be a number.'

    return True, None


def has_schedule_conflict(cast_id: int, booking_date: str, start_time: str, duration_hours: int) -> bool:
    db = get_db()
    new_start = datetime.strptime(f'{booking_date} {start_time}', '%Y-%m-%d %H:%M')
    new_end = new_start + timedelta(hours=duration_hours)

    rows = db.execute(
        '''
        SELECT booking_date, start_time, duration_hours
        FROM bookings
        WHERE cast_id = ? AND booking_date = ? AND status IN ('pending', 'confirmed')
        ''',
        (cast_id, booking_date),
    ).fetchall()

    for row in rows:
        existing_start = datetime.strptime(f"{row['booking_date']} {row['start_time']}", '%Y-%m-%d %H:%M')
        existing_end = existing_start + timedelta(hours=row['duration_hours'])
        if new_start < existing_end and existing_start < new_end:
            return True
    return False


@app.route('/')
def home():
    db = get_db()
    casts = db.execute('SELECT * FROM casts ORDER BY id ASC').fetchall()
    return render_template('home.html', casts=casts)


@app.route('/cast/<int:cast_id>')
def cast_detail(cast_id: int):
    db = get_db()
    cast = db.execute('SELECT * FROM casts WHERE id = ?', (cast_id,)).fetchone()
    if not cast:
        return 'Cast not found', 404

    upcoming = db.execute(
        '''
        SELECT booking_date, start_time, duration_hours, status
        FROM bookings
        WHERE cast_id = ? AND booking_date >= date('now')
        ORDER BY booking_date, start_time
        LIMIT 5
        ''',
        (cast_id,),
    ).fetchall()
    return render_template('cast_detail.html', cast=cast, upcoming=upcoming)


@app.route('/book/<int:cast_id>', methods=['GET', 'POST'])
def book_cast(cast_id: int):
    db = get_db()
    cast = db.execute('SELECT * FROM casts WHERE id = ?', (cast_id,)).fetchone()
    if not cast:
        return 'Cast not found', 404

    if request.method == 'POST':
        form = {k: request.form.get(k, '').strip() for k in request.form}
        valid, message = validate_booking(form)
        if not valid:
            flash(message, 'error')
            return render_template('booking_form.html', cast=cast, form=form)

        duration_hours = int(form['duration_hours'])
        if has_schedule_conflict(cast_id, form['booking_date'], form['start_time'], duration_hours):
            flash('That time slot overlaps an existing booking.', 'error')
            return render_template('booking_form.html', cast=cast, form=form)

        db.execute(
            '''
            INSERT INTO bookings
            (cast_id, customer_name, customer_email, booking_date, start_time, duration_hours, location, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            ''',
            (
                cast_id,
                form['customer_name'],
                form['customer_email'],
                form['booking_date'],
                form['start_time'],
                duration_hours,
                form['location'],
                form.get('notes', ''),
            ),
        )
        db.commit()
        flash('Booking request submitted successfully.', 'success')
        return redirect(url_for('booking_complete', cast_id=cast_id))

    return render_template('booking_form.html', cast=cast, form={})


@app.route('/book/<int:cast_id>/complete')
def booking_complete(cast_id: int):
    db = get_db()
    cast = db.execute('SELECT * FROM casts WHERE id = ?', (cast_id,)).fetchone()
    return render_template('booking_complete.html', cast=cast)


@app.route('/admin/bookings', methods=['GET', 'POST'])
def admin_bookings():
    db = get_db()
    if request.method == 'POST':
        booking_id = request.form.get('booking_id', type=int)
        status = request.form.get('status', '').strip()
        if booking_id and status in {'pending', 'confirmed', 'cancelled'}:
            db.execute('UPDATE bookings SET status = ? WHERE id = ?', (status, booking_id))
            db.commit()
            flash('Booking status updated.', 'success')
        return redirect(url_for('admin_bookings'))

    bookings = db.execute(
        '''
        SELECT b.*, c.name AS cast_name
        FROM bookings b
        JOIN casts c ON c.id = b.cast_id
        ORDER BY b.booking_date DESC, b.start_time DESC
        '''
    ).fetchall()
    return render_template('admin_bookings.html', bookings=bookings)


@app.route('/about')
def about():
    return render_template('about.html')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
