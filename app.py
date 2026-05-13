# ============================================================
# MOVIE TICKET BOOKING SYSTEM — Complete Flask Backend
# ============================================================

import os
import sqlite3
import qrcode
import io
import base64
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_file, g, jsonify
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# ============================================================
# APP CONFIGURATION
# ============================================================
app = Flask(__name__)
app.secret_key = 'movie_booking_secret_key_2024'
app.config['DATABASE'] = 'database.db'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'images')

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ============================================================
# DATABASE HELPERS
# ============================================================
def get_db():
    """Get database connection for current request."""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Close database connection when request ends."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize all database tables and insert sample data."""
    db = sqlite3.connect(app.config['DATABASE'])
    db.execute("PRAGMA foreign_keys = ON")
    cursor = db.cursor()

    # Create Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    ''')

    # Create Locations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            location_id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_name TEXT NOT NULL,
            state TEXT NOT NULL
        )
    ''')

    # Create Theatres table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS theatres (
            theatre_id INTEGER PRIMARY KEY AUTOINCREMENT,
            theatre_name TEXT NOT NULL,
            location_id INTEGER NOT NULL,
            address TEXT,
            total_screens INTEGER DEFAULT 3,
            rating REAL DEFAULT 4.0,
            FOREIGN KEY(location_id) REFERENCES locations(location_id)
        )
    ''')

    # Create Movies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            movie_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            genre TEXT NOT NULL,
            language TEXT NOT NULL,
            duration TEXT NOT NULL,
            description TEXT,
            poster TEXT,
            rating REAL DEFAULT 0,
            status TEXT DEFAULT 'Now Showing',
            release_date TEXT
        )
    ''')

    # Create Shows table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shows (
            show_id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            theatre_id INTEGER NOT NULL,
            show_time TEXT NOT NULL,
            show_date TEXT NOT NULL,
            screen TEXT NOT NULL,
            price INTEGER NOT NULL,
            FOREIGN KEY(movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
            FOREIGN KEY(theatre_id) REFERENCES theatres(theatre_id) ON DELETE CASCADE
        )
    ''')

    # Create Seats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seats (
            seat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            show_id INTEGER NOT NULL,
            seat_number TEXT NOT NULL,
            status TEXT DEFAULT 'available',
            FOREIGN KEY(show_id) REFERENCES shows(show_id) ON DELETE CASCADE
        )
    ''')

    # Create Bookings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            show_id INTEGER NOT NULL,
            seat_number TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            total_amount INTEGER NOT NULL,
            status TEXT DEFAULT 'confirmed',
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(show_id) REFERENCES shows(show_id)
        )
    ''')

    # Create Ratings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings (
            rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            movie_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            review TEXT,
            rating_date TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
        )
    ''')

    # Insert admin user if not exists
    cursor.execute("SELECT * FROM users WHERE email = 'admin@movie.com'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (name, email, password, is_admin) VALUES (?, ?, ?, ?)",
            ('Admin', 'admin@movie.com', 'admin123', 1)
        )

    # Insert sample movies if table is empty
    cursor.execute("SELECT COUNT(*) FROM movies")
    if cursor.fetchone()[0] == 0:
        sample_movies = [
            ('KGF Chapter 2', 'Action', 'Kannada', '2h 48m',
             'Rocky, now the king of Kolar Gold Fields, must face the wrath of Adheera and the government.',
             'kgf.jpg', 4.5, 'Now Showing', '2024-01-15'),
            ('Jawan', 'Action', 'Hindi', '2h 49m',
             'A high-octane action thriller that outlines the emotional journey of a man.',
             'jawan.jpg', 4.3, 'Now Showing', '2024-01-20'),
            ('RRR', 'Action', 'Telugu', '3h 7m',
             'A fictitious story about two Indian revolutionaries, Alluri Sitarama Raju and Komaram Bheem.',
             'rrr.jpg', 4.6, 'Now Showing', '2024-01-10'),
            ('Ponniyin Selvan', 'Historical', 'Tamil', '2h 47m',
             'An epic historical drama based on the Chola dynasty.',
             'ps.jpg', 4.2, 'Now Showing', '2024-02-01'),
            ('Inception', 'Sci-Fi', 'English', '2h 28m',
             'A thief who steals corporate secrets through dream-sharing technology.',
             'inception.jpg', 4.8, 'Now Showing', '2024-01-05'),
            ('Parasite', 'Thriller', 'Korean', '2h 12m',
             'Greed and class discrimination threaten the symbiotic relationship between two families.',
             'parasite.jpg', 4.7, 'Now Showing', '2024-02-10'),
            ('Spirited Away', 'Animation', 'Japanese', '2h 5m',
             'A young girl enters a world ruled by gods, witches, and spirits.',
             'spirited.jpg', 4.9, 'Now Showing', '2024-01-25'),
            ('Dangal', 'Drama', 'Hindi', '2h 41m',
             'Former wrestler Mahavir Singh Phogat trains his daughters to become wrestlers.',
             'dangal.jpg', 4.5, 'Now Showing', '2024-02-05'),
            ('Premam', 'Romance', 'Malayalam', '2h 32m',
             'The life journey of a boy from his school to college days and love stories.',
             'premam.jpg', 4.1, 'Now Showing', '2024-02-15'),
            ('Money Heist: The Movie', 'Thriller', 'Spanish', '2h 15m',
             'The Professor and his gang plan their most ambitious heist yet.',
             'moneyheist.jpg', 4.4, 'Coming Soon', '2024-06-01'),
            ('Kantara', 'Action', 'Kannada', '2h 28m',
             'A Kambala champion locks horns with a forest officer.',
             'kantara.jpg', 4.7, 'Now Showing', '2024-01-12'),
            ('The Intouchables', 'Drama', 'French', '1h 52m',
             'An unlikely friendship develops between a wealthy quadriplegic and his caretaker.',
             'intouchables.jpg', 4.6, 'Now Showing', '2024-02-20'),
            ('Pathaan', 'Action', 'Hindi', '2h 26m',
             'An Indian spy takes on the leader of a group of mercenaries.',
             'pathaan.jpg', 4.0, 'Now Showing', '2024-01-28'),
            ('Vikram', 'Action', 'Tamil', '2h 54m',
             'A special agent investigates a case connected to a series of murders.',
             'vikram.jpg', 4.4, 'Now Showing', '2024-02-08'),
            ('Salaar', 'Action', 'Telugu', '2h 55m',
             'The fate of a small peaceful village rests on the shoulders of a loyal friend.',
             'salaar.jpg', 4.1, 'Coming Soon', '2024-07-15'),
            ('Oppenheimer', 'Drama', 'English', '3h 0m',
             'The story of J. Robert Oppenheimer and the creation of the atomic bomb.',
             'oppenheimer.jpg', 4.8, 'Now Showing', '2024-01-18'),
        ]
        cursor.executemany(
            '''INSERT INTO movies
               (title, genre, language, duration, description, poster, rating, status, release_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            sample_movies
        )

        # Insert sample locations
        sample_locations = [
            ('Bangalore', 'Karnataka'),
            ('Mumbai', 'Maharashtra'),
            ('Delhi', 'Delhi'),
            ('Chennai', 'Tamil Nadu'),
            ('Hyderabad', 'Telangana'),
            ('Kolkata', 'West Bengal'),
        ]
        cursor.executemany(
            'INSERT INTO locations (city_name, state) VALUES (?, ?)',
            sample_locations
        )

        # Insert sample theatres
        sample_theatres = [
            ('PVR Orion Mall', 1, 'Dr. Rajkumar Road, Rajajinagar', 4, 4.5),
            ('INOX Garuda Mall', 1, 'Magrath Road, Ashok Nagar', 3, 4.3),
            ('Cinepolis Royal Meenakshi', 1, 'Bannerghatta Road', 5, 4.6),
            ('PVR Phoenix', 2, 'Senapati Bapat Marg, Lower Parel', 6, 4.4),
            ('INOX R-City', 2, 'LBS Marg, Ghatkopar', 4, 4.2),
            ('PVR Select Citywalk', 3, 'Saket District Centre', 5, 4.7),
            ('INOX Nehru Place', 3, 'Nehru Place', 3, 4.1),
            ('SPI Palazzo', 4, 'Montieth Road, Egmore', 4, 4.5),
            ('AGS Cinemas', 4, 'T. Nagar', 3, 4.0),
            ('PVR Next Galleria', 5, 'Panjagutta', 5, 4.3),
            ('INOX GVK One', 5, 'Banjara Hills', 4, 4.4),
            ('INOX Quest Mall', 6, 'Park Circus', 3, 4.2),
        ]
        cursor.executemany(
            '''INSERT INTO theatres (theatre_name, location_id, address, total_screens, rating)
               VALUES (?, ?, ?, ?, ?)''',
            sample_theatres
        )

        # Insert sample shows for each movie (distributed across theatres)
        show_times = ['10:00 AM', '1:30 PM', '4:00 PM', '7:30 PM', '10:00 PM']
        screens = ['Screen 1', 'Screen 2', 'Screen 3']
        prices = [150, 200, 250, 300, 350]
        today = date.today().strftime('%Y-%m-%d')

        movie_count = len(sample_movies)
        theatre_count = len(sample_theatres)
        for mid in range(1, movie_count + 1):
            for i, st in enumerate(show_times):
                tid = ((mid + i) % theatre_count) + 1
                cursor.execute(
                    '''INSERT INTO shows (movie_id, theatre_id, show_time, show_date, screen, price)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (mid, tid, st, today, screens[i % len(screens)], prices[i])
                )

        # Insert seats for each show
        cursor.execute("SELECT show_id FROM shows")
        all_shows = cursor.fetchall()
        rows_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        seats_per_row = 10
        for show in all_shows:
            for row_letter in rows_letters:
                for seat_num in range(1, seats_per_row + 1):
                    seat_label = f"{row_letter}{seat_num}"
                    cursor.execute(
                        '''INSERT INTO seats (show_id, seat_number, status)
                           VALUES (?, ?, 'available')''',
                        (show[0], seat_label)
                    )

    db.commit()
    db.close()


# ============================================================
# LOGIN REQUIRED DECORATOR
# ============================================================
def login_required(f):
    """Decorator: redirect to login if user is not logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator: redirect if user is not admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================
# ROUTES — HOME
# ============================================================
@app.route('/')
def index():
    db = get_db()
    selected_city = request.args.get('city', '')

    # Get all locations for city selector
    locations = db.execute(
        "SELECT * FROM locations ORDER BY city_name"
    ).fetchall()

    # Featured / Now Showing movies
    now_showing = db.execute(
        "SELECT * FROM movies WHERE status = 'Now Showing' ORDER BY rating DESC"
    ).fetchall()

    # Coming Soon
    coming_soon = db.execute(
        "SELECT * FROM movies WHERE status = 'Coming Soon' ORDER BY release_date"
    ).fetchall()

    # Trending (top rated)
    trending = db.execute(
        "SELECT * FROM movies ORDER BY rating DESC LIMIT 6"
    ).fetchall()

    # Get unique languages and genres for filters
    languages = db.execute(
        "SELECT DISTINCT language FROM movies ORDER BY language"
    ).fetchall()
    genres = db.execute(
        "SELECT DISTINCT genre FROM movies ORDER BY genre"
    ).fetchall()

    return render_template(
        'index.html',
        now_showing=now_showing,
        coming_soon=coming_soon,
        trending=trending,
        languages=languages,
        genres=genres,
        locations=locations,
        selected_city=selected_city
    )


# ============================================================
# ROUTES — AUTHENTICATION
# ============================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, password)
            )
            db.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()

        if user:
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['is_admin'] = user['is_admin']
            flash(f'Welcome back, {user["name"]}!', 'success')
            if user['is_admin']:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password!', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))


# ============================================================
# ROUTES — MOVIES
# ============================================================
@app.route('/movies')
def movies():
    db = get_db()
    query = "SELECT * FROM movies WHERE 1=1"
    params = []

    # Search
    search = request.args.get('search', '')
    if search:
        query += " AND (title LIKE ? OR genre LIKE ? OR language LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    # Language filter
    language = request.args.get('language', '')
    if language:
        query += " AND language = ?"
        params.append(language)

    # Genre filter
    genre = request.args.get('genre', '')
    if genre:
        query += " AND genre = ?"
        params.append(genre)

    # Status filter
    status = request.args.get('status', '')
    if status:
        query += " AND status = ?"
        params.append(status)

    # City filter — only show movies that have shows in selected city
    city = request.args.get('city', '')
    if city:
        query += """ AND movie_id IN (
            SELECT DISTINCT s.movie_id FROM shows s
            JOIN theatres t ON s.theatre_id = t.theatre_id
            JOIN locations l ON t.location_id = l.location_id
            WHERE l.city_name = ?
        )"""
        params.append(city)

    query += " ORDER BY rating DESC"
    movies_list = db.execute(query, params).fetchall()

    # For filter dropdowns
    languages = db.execute(
        "SELECT DISTINCT language FROM movies ORDER BY language"
    ).fetchall()
    genres = db.execute(
        "SELECT DISTINCT genre FROM movies ORDER BY genre"
    ).fetchall()
    locations = db.execute(
        "SELECT * FROM locations ORDER BY city_name"
    ).fetchall()

    return render_template(
        'movies.html',
        movies=movies_list,
        languages=languages,
        genres=genres,
        locations=locations,
        search=search,
        selected_language=language,
        selected_genre=genre,
        selected_status=status,
        selected_city=city
    )


@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    db = get_db()
    movie = db.execute(
        "SELECT * FROM movies WHERE movie_id = ?", (movie_id,)
    ).fetchone()

    if not movie:
        flash('Movie not found!', 'danger')
        return redirect(url_for('movies'))

    # Get shows for this movie with theatre and location info
    shows = db.execute(
        '''SELECT s.*, t.theatre_name, t.rating as theatre_rating, t.address,
                  l.city_name, l.state
           FROM shows s
           JOIN theatres t ON s.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           WHERE s.movie_id = ?
           ORDER BY l.city_name, t.theatre_name, s.show_time''',
        (movie_id,)
    ).fetchall()

    # Get ratings
    ratings_list = db.execute(
        '''SELECT r.*, u.name FROM ratings r
           JOIN users u ON r.user_id = u.user_id
           WHERE r.movie_id = ?
           ORDER BY r.rating_date DESC''',
        (movie_id,)
    ).fetchall()

    # Average rating
    avg_rating = db.execute(
        "SELECT AVG(rating) as avg_r, COUNT(*) as count FROM ratings WHERE movie_id = ?",
        (movie_id,)
    ).fetchone()

    return render_template(
        'movie_details.html',
        movie=movie,
        shows=shows,
        ratings=ratings_list,
        avg_rating=avg_rating
    )


# ============================================================
# ROUTES — SEATS
# ============================================================
@app.route('/seats/<int:show_id>')
@login_required
def seats(show_id):
    db = get_db()

    show = db.execute(
        '''SELECT s.*, m.title, m.poster, t.theatre_name, t.address, l.city_name, l.state
           FROM shows s
           JOIN movies m ON s.movie_id = m.movie_id
           JOIN theatres t ON s.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           WHERE s.show_id = ?''',
        (show_id,)
    ).fetchone()

    if not show:
        flash('Show not found!', 'danger')
        return redirect(url_for('movies'))

    seats_list = db.execute(
        "SELECT * FROM seats WHERE show_id = ? ORDER BY seat_number",
        (show_id,)
    ).fetchall()

    return render_template('seats.html', show=show, seats=seats_list)


# ============================================================
# ROUTES — PAYMENT
# ============================================================
@app.route('/payment', methods=['POST'])
@login_required
def payment():
    show_id = request.form.get('show_id')
    selected_seats = request.form.getlist('seats')

    if not selected_seats:
        flash('Please select at least one seat!', 'warning')
        return redirect(url_for('seats', show_id=show_id))

    db = get_db()
    show = db.execute(
        '''SELECT s.*, m.title, m.poster, t.theatre_name, l.city_name
           FROM shows s
           JOIN movies m ON s.movie_id = m.movie_id
           JOIN theatres t ON s.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           WHERE s.show_id = ?''',
        (show_id,)
    ).fetchone()

    total = show['price'] * len(selected_seats)

    # Store in session for booking
    session['booking_show_id'] = int(show_id)
    session['booking_seats'] = selected_seats
    session['booking_total'] = total

    return render_template(
        'payment.html',
        show=show,
        selected_seats=selected_seats,
        total=total
    )


@app.route('/payment/debit_card')
@login_required
def debit_card():
    if 'booking_show_id' not in session:
        return redirect(url_for('movies'))
    db = get_db()
    show = db.execute(
        '''SELECT s.*, m.title, t.theatre_name, l.city_name FROM shows s
           JOIN movies m ON s.movie_id = m.movie_id
           JOIN theatres t ON s.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           WHERE s.show_id = ?''',
        (session['booking_show_id'],)
    ).fetchone()
    return render_template(
        'debit_card.html',
        total=session['booking_total'],
        show=show,
        seats=session['booking_seats']
    )


@app.route('/payment/credit_card')
@login_required
def credit_card():
    if 'booking_show_id' not in session:
        return redirect(url_for('movies'))
    db = get_db()
    show = db.execute(
        '''SELECT s.*, m.title, t.theatre_name, l.city_name FROM shows s
           JOIN movies m ON s.movie_id = m.movie_id
           JOIN theatres t ON s.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           WHERE s.show_id = ?''',
        (session['booking_show_id'],)
    ).fetchone()
    return render_template(
        'credit_card.html',
        total=session['booking_total'],
        show=show,
        seats=session['booking_seats']
    )


@app.route('/payment/upi')
@login_required
def upi_payment():
    if 'booking_show_id' not in session:
        return redirect(url_for('movies'))

    total = session['booking_total']
    upi_id = "moviebooking@upi"

    # Generate QR code
    qr_data = f"upi://pay?pa={upi_id}&pn=MovieBooking&am={total}&cu=INR"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    db = get_db()
    show = db.execute(
        '''SELECT s.*, m.title, t.theatre_name, l.city_name FROM shows s
           JOIN movies m ON s.movie_id = m.movie_id
           JOIN theatres t ON s.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           WHERE s.show_id = ?''',
        (session['booking_show_id'],)
    ).fetchone()

    return render_template(
        'upi_payment.html',
        total=total,
        upi_id=upi_id,
        qr_code=qr_base64,
        show=show,
        seats=session['booking_seats']
    )


@app.route('/payment/netbanking')
@login_required
def netbanking():
    if 'booking_show_id' not in session:
        return redirect(url_for('movies'))
    db = get_db()
    show = db.execute(
        '''SELECT s.*, m.title, t.theatre_name, l.city_name FROM shows s
           JOIN movies m ON s.movie_id = m.movie_id
           JOIN theatres t ON s.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           WHERE s.show_id = ?''',
        (session['booking_show_id'],)
    ).fetchone()
    return render_template(
        'netbanking.html',
        total=session['booking_total'],
        show=show,
        seats=session['booking_seats']
    )


# ============================================================
# ROUTES — CONFIRM BOOKING
# ============================================================
@app.route('/confirm_booking', methods=['POST'])
@login_required
def confirm_booking():
    payment_method = request.form.get('payment_method', 'Unknown')

    if 'booking_show_id' not in session:
        flash('Session expired. Please try again.', 'danger')
        return redirect(url_for('movies'))

    show_id = session['booking_show_id']
    selected_seats = session['booking_seats']
    total = session['booking_total']
    user_id = session['user_id']

    db = get_db()

    # Check if seats are still available (prevent double booking)
    for seat in selected_seats:
        seat_row = db.execute(
            "SELECT * FROM seats WHERE show_id = ? AND seat_number = ? AND status = 'available'",
            (show_id, seat)
        ).fetchone()
        if not seat_row:
            flash(f'Seat {seat} is no longer available. Please select different seats.', 'danger')
            # Clear session booking data
            session.pop('booking_show_id', None)
            session.pop('booking_seats', None)
            session.pop('booking_total', None)
            return redirect(url_for('seats', show_id=show_id))

    # Book seats
    booking_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    seats_str = ', '.join(selected_seats)

    # Insert booking
    cursor = db.execute(
        '''INSERT INTO bookings (user_id, show_id, seat_number, booking_date, payment_method, total_amount, status)
           VALUES (?, ?, ?, ?, ?, ?, 'confirmed')''',
        (user_id, show_id, seats_str, booking_date, payment_method, total)
    )
    booking_id = cursor.lastrowid

    # Update seat status
    for seat in selected_seats:
        db.execute(
            "UPDATE seats SET status = 'booked' WHERE show_id = ? AND seat_number = ?",
            (show_id, seat)
        )

    db.commit()

    # Clear session booking data
    session.pop('booking_show_id', None)
    session.pop('booking_seats', None)
    session.pop('booking_total', None)

    # Get booking details for confirmation page
    booking = db.execute(
        '''SELECT b.*, s.show_time, s.show_date, s.screen, s.price, m.title, m.poster,
                  t.theatre_name, l.city_name
           FROM bookings b
           JOIN shows s ON b.show_id = s.show_id
           JOIN movies m ON s.movie_id = m.movie_id
           JOIN theatres t ON s.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           WHERE b.booking_id = ?''',
        (booking_id,)
    ).fetchone()

    return render_template('booking_confirmation.html', booking=booking)


# ============================================================
# ROUTES — BOOKING HISTORY
# ============================================================
@app.route('/booking_history')
@login_required
def booking_history():
    db = get_db()
    bookings = db.execute(
        '''SELECT b.*, s.show_time, s.show_date, s.screen, s.price, m.title, m.poster,
                  t.theatre_name, l.city_name
           FROM bookings b
           JOIN shows s ON b.show_id = s.show_id
           JOIN movies m ON s.movie_id = m.movie_id
           JOIN theatres t ON s.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           WHERE b.user_id = ?
           ORDER BY b.booking_date DESC''',
        (session['user_id'],)
    ).fetchall()

    return render_template('booking_history.html', bookings=bookings)


# ============================================================
# ROUTES — CANCEL BOOKING
# ============================================================
@app.route('/cancel_booking/<int:booking_id>')
@login_required
def cancel_booking(booking_id):
    db = get_db()
    booking = db.execute(
        "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
        (booking_id, session['user_id'])
    ).fetchone()

    if not booking:
        flash('Booking not found!', 'danger')
        return redirect(url_for('booking_history'))

    if booking['status'] == 'cancelled':
        flash('Booking already cancelled!', 'warning')
        return redirect(url_for('booking_history'))

    # Free up the seats
    seats = booking['seat_number'].split(', ')
    for seat in seats:
        db.execute(
            "UPDATE seats SET status = 'available' WHERE show_id = ? AND seat_number = ?",
            (booking['show_id'], seat.strip())
        )

    # Update booking status
    db.execute(
        "UPDATE bookings SET status = 'cancelled' WHERE booking_id = ?",
        (booking_id,)
    )
    db.commit()

    flash('Booking cancelled successfully! Refund will be processed.', 'success')
    return redirect(url_for('booking_history'))


# ============================================================
# ROUTES — DOWNLOAD TICKET (PDF)
# ============================================================
@app.route('/download_ticket/<int:booking_id>')
@login_required
def download_ticket(booking_id):
    db = get_db()
    booking = db.execute(
        '''SELECT b.*, s.show_time, s.show_date, s.screen, s.price,
                  m.title, m.language, m.duration,
                  t.theatre_name, t.address as theatre_address,
                  l.city_name, l.state
           FROM bookings b
           JOIN shows s ON b.show_id = s.show_id
           JOIN movies m ON s.movie_id = m.movie_id
           JOIN theatres t ON s.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           WHERE b.booking_id = ? AND b.user_id = ?''',
        (booking_id, session['user_id'])
    ).fetchone()

    if not booking:
        flash('Booking not found!', 'danger')
        return redirect(url_for('booking_history'))

    # Generate PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Background
    p.setFillColor(HexColor('#1a1a2e'))
    p.rect(0, 0, width, height, fill=True)

    # Header bar
    p.setFillColor(HexColor('#e94560'))
    p.rect(0, height - 100, width, 100, fill=True)

    # Title
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 28)
    p.drawCentredString(width / 2, height - 55, "MOVIE TICKET")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, height - 80, "MovieBook - Your Cinema Experience")

    # Ticket body
    p.setFillColor(HexColor('#16213e'))
    p.roundRect(40, height - 560, width - 80, 440, 15, fill=True)

    # Movie info
    y = height - 150
    p.setFillColor(HexColor('#e94560'))
    p.setFont("Helvetica-Bold", 20)
    p.drawString(70, y, booking['title'])

    y -= 40
    p.setFillColor(colors.white)
    p.setFont("Helvetica", 14)
    info_items = [
        f"Booking ID: #{booking['booking_id']}",
        f"Date: {booking['show_date']}",
        f"Show Time: {booking['show_time']}",
        f"Theatre: {booking['theatre_name']}",
        f"Location: {booking['city_name']}, {booking['state']}",
        f"Screen: {booking['screen']}",
        f"Seats: {booking['seat_number']}",
        f"Language: {booking['language']}",
        f"Duration: {booking['duration']}",
        f"Payment: {booking['payment_method']}",
        f"Total Amount: Rs.{booking['total_amount']}",
        f"Booked On: {booking['booking_date']}",
    ]

    for item in info_items:
        y -= 32
        p.drawString(70, y, item)

    # Divider line
    y -= 20
    p.setStrokeColor(HexColor('#e94560'))
    p.setLineWidth(2)
    p.line(60, y, width - 60, y)

    # Footer
    y -= 30
    p.setFont("Helvetica-Bold", 12)
    p.setFillColor(HexColor('#e94560'))
    p.drawCentredString(width / 2, y, "* Enjoy Your Movie! *")

    y -= 25
    p.setFont("Helvetica", 10)
    p.setFillColor(HexColor('#aaaaaa'))
    p.drawCentredString(width / 2, y, "Terms: Non-transferable. Carry a valid ID.")
    p.drawCentredString(width / 2, y - 15, "Please arrive 15 minutes before showtime.")

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'ticket_{booking_id}.pdf',
        mimetype='application/pdf'
    )


# ============================================================
# ROUTES — MOVIE RATING
# ============================================================
@app.route('/rate_movie/<int:movie_id>', methods=['POST'])
@login_required
def rate_movie(movie_id):
    rating = int(request.form['rating'])
    review = request.form.get('review', '')

    db = get_db()

    # Check if already rated
    existing = db.execute(
        "SELECT * FROM ratings WHERE user_id = ? AND movie_id = ?",
        (session['user_id'], movie_id)
    ).fetchone()

    if existing:
        db.execute(
            "UPDATE ratings SET rating = ?, review = ?, rating_date = ? WHERE rating_id = ?",
            (rating, review, datetime.now().strftime('%Y-%m-%d'), existing['rating_id'])
        )
    else:
        db.execute(
            "INSERT INTO ratings (user_id, movie_id, rating, review, rating_date) VALUES (?, ?, ?, ?, ?)",
            (session['user_id'], movie_id, rating, review, datetime.now().strftime('%Y-%m-%d'))
        )

    # Update movie's average rating
    avg = db.execute(
        "SELECT AVG(rating) FROM ratings WHERE movie_id = ?",
        (movie_id,)
    ).fetchone()[0]

    if avg:
        db.execute(
            "UPDATE movies SET rating = ? WHERE movie_id = ?",
            (round(avg, 1), movie_id)
        )

    db.commit()
    flash('Rating submitted successfully!', 'success')
    return redirect(url_for('movie_details', movie_id=movie_id))


# ============================================================
# ROUTES — ADMIN DASHBOARD
# ============================================================
@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()

    total_movies = db.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    total_users = db.execute("SELECT COUNT(*) FROM users WHERE is_admin = 0").fetchone()[0]
    total_bookings = db.execute(
        "SELECT COUNT(*) FROM bookings WHERE status = 'confirmed'"
    ).fetchone()[0]
    total_revenue = db.execute(
        "SELECT COALESCE(SUM(total_amount), 0) FROM bookings WHERE status = 'confirmed'"
    ).fetchone()[0]

    # Most popular movie
    popular = db.execute(
        '''SELECT m.title, COUNT(b.booking_id) as count
           FROM bookings b
           JOIN shows s ON b.show_id = s.show_id
           JOIN movies m ON s.movie_id = m.movie_id
           WHERE b.status = 'confirmed'
           GROUP BY m.movie_id
           ORDER BY count DESC LIMIT 1'''
    ).fetchone()

    movies_list = db.execute("SELECT * FROM movies ORDER BY movie_id DESC").fetchall()
    bookings_list = db.execute(
        '''SELECT b.*, u.name as user_name, s.show_time, s.show_date, m.title
           FROM bookings b
           JOIN users u ON b.user_id = u.user_id
           JOIN shows s ON b.show_id = s.show_id
           JOIN movies m ON s.movie_id = m.movie_id
           ORDER BY b.booking_date DESC LIMIT 20'''
    ).fetchall()

    shows_list = db.execute(
        '''SELECT sh.*, m.title, t.theatre_name, l.city_name FROM shows sh
           JOIN movies m ON sh.movie_id = m.movie_id
           JOIN theatres t ON sh.theatre_id = t.theatre_id
           JOIN locations l ON t.location_id = l.location_id
           ORDER BY sh.show_date, sh.show_time'''
    ).fetchall()

    theatres_list = db.execute(
        '''SELECT t.*, l.city_name, l.state FROM theatres t
           JOIN locations l ON t.location_id = l.location_id
           ORDER BY l.city_name, t.theatre_name'''
    ).fetchall()

    locations_list = db.execute(
        "SELECT * FROM locations ORDER BY city_name"
    ).fetchall()

    return render_template(
        'admin_dashboard.html',
        total_movies=total_movies,
        total_users=total_users,
        total_bookings=total_bookings,
        total_revenue=total_revenue,
        popular_movie=popular,
        movies=movies_list,
        bookings=bookings_list,
        shows=shows_list,
        theatres=theatres_list,
        locations=locations_list
    )


# ============================================================
# ROUTES — ADMIN: ADD MOVIE
# ============================================================
@app.route('/admin/add_movie', methods=['POST'])
@admin_required
def add_movie():
    title = request.form['title']
    genre = request.form['genre']
    language = request.form['language']
    duration = request.form['duration']
    description = request.form.get('description', '')
    status = request.form.get('status', 'Now Showing')
    release_date = request.form.get('release_date', date.today().strftime('%Y-%m-%d'))

    # Handle poster upload
    poster_filename = 'default.jpg'
    if 'poster' in request.files:
        poster_file = request.files['poster']
        if poster_file.filename:
            poster_filename = poster_file.filename
            poster_file.save(
                os.path.join(app.config['UPLOAD_FOLDER'], poster_filename)
            )

    db = get_db()
    db.execute(
        '''INSERT INTO movies (title, genre, language, duration, description, poster, status, release_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (title, genre, language, duration, description, poster_filename, status, release_date)
    )
    db.commit()

    flash('Movie added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


# ============================================================
# ROUTES — ADMIN: EDIT MOVIE
# ============================================================
@app.route('/admin/edit_movie/<int:movie_id>', methods=['POST'])
@admin_required
def edit_movie(movie_id):
    title = request.form['title']
    genre = request.form['genre']
    language = request.form['language']
    duration = request.form['duration']
    description = request.form.get('description', '')
    status = request.form.get('status', 'Now Showing')

    db = get_db()

    # Handle poster upload
    if 'poster' in request.files:
        poster_file = request.files['poster']
        if poster_file.filename:
            poster_filename = poster_file.filename
            poster_file.save(
                os.path.join(app.config['UPLOAD_FOLDER'], poster_filename)
            )
            db.execute(
                "UPDATE movies SET poster = ? WHERE movie_id = ?",
                (poster_filename, movie_id)
            )

    db.execute(
        '''UPDATE movies SET title=?, genre=?, language=?, duration=?, description=?, status=?
           WHERE movie_id=?''',
        (title, genre, language, duration, description, status, movie_id)
    )
    db.commit()

    flash('Movie updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


# ============================================================
# ROUTES — ADMIN: DELETE MOVIE
# ============================================================
@app.route('/admin/delete_movie/<int:movie_id>')
@admin_required
def delete_movie(movie_id):
    db = get_db()
    db.execute("DELETE FROM movies WHERE movie_id = ?", (movie_id,))
    db.commit()
    flash('Movie deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


# ============================================================
# ROUTES — ADMIN: ADD SHOW
# ============================================================
@app.route('/admin/add_show', methods=['POST'])
@admin_required
def add_show():
    movie_id = request.form['movie_id']
    theatre_id = request.form['theatre_id']
    show_time = request.form['show_time']
    show_date = request.form['show_date']
    screen = request.form['screen']
    price = request.form['price']

    db = get_db()
    cursor = db.execute(
        '''INSERT INTO shows (movie_id, theatre_id, show_time, show_date, screen, price)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (movie_id, theatre_id, show_time, show_date, screen, price)
    )
    show_id = cursor.lastrowid

    # Create seats for this show
    rows_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    seats_per_row = 10
    for row_letter in rows_letters:
        for seat_num in range(1, seats_per_row + 1):
            seat_label = f"{row_letter}{seat_num}"
            db.execute(
                "INSERT INTO seats (show_id, seat_number, status) VALUES (?, ?, 'available')",
                (show_id, seat_label)
            )

    db.commit()
    flash('Show added successfully with 80 seats!', 'success')
    return redirect(url_for('admin_dashboard'))


# ============================================================
# ROUTES — ADMIN: DELETE SHOW
# ============================================================
@app.route('/admin/delete_show/<int:show_id>')
@admin_required
def delete_show(show_id):
    db = get_db()
    db.execute("DELETE FROM shows WHERE show_id = ?", (show_id,))
    db.commit()
    flash('Show deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


# ============================================================
# ROUTES — ADMIN: ADD THEATRE
# ============================================================
@app.route('/admin/add_theatre', methods=['POST'])
@admin_required
def add_theatre():
    theatre_name = request.form['theatre_name']
    location_id = request.form['location_id']
    address = request.form.get('address', '')
    total_screens = request.form.get('total_screens', 3)

    db = get_db()
    db.execute(
        '''INSERT INTO theatres (theatre_name, location_id, address, total_screens)
           VALUES (?, ?, ?, ?)''',
        (theatre_name, location_id, address, total_screens)
    )
    db.commit()
    flash('Theatre added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


# ============================================================
# ROUTES — ADMIN: ADD LOCATION
# ============================================================
@app.route('/admin/add_location', methods=['POST'])
@admin_required
def add_location():
    city_name = request.form['city_name']
    state = request.form['state']

    db = get_db()
    db.execute(
        'INSERT INTO locations (city_name, state) VALUES (?, ?)',
        (city_name, state)
    )
    db.commit()
    flash('Location added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


# ============================================================
# API — AVAILABLE SEATS COUNT
# ============================================================
@app.route('/api/seats_count/<int:show_id>')
def seats_count(show_id):
    db = get_db()
    count = db.execute(
        "SELECT COUNT(*) FROM seats WHERE show_id = ? AND status = 'available'",
        (show_id,)
    ).fetchone()[0]
    return jsonify({'available': count})


# ============================================================
# RUN THE APPLICATION
# ============================================================
if __name__ == '__main__':
    init_db()
    print("\n" + "=" * 50)
    print("Movie Ticket Booking System is running!")
    print("Open: http://127.0.0.1:5000")
    print("Admin: admin@movie.com / admin123")
    print("-" * 50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)