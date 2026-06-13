from flask import Flask, render_template, request, redirect, session, flash, url_for, get_flashed_messages, g


import mysql.connector
from mysql.connector import IntegrityError


app = Flask(__name__)
app.secret_key = 'your_secret_key'


@app.teardown_appcontext
def close_db_connection(exception=None):
    conn = getattr(g, '_database', None)
    if conn is not None:
        conn.close()


# ✅ Database connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",  # put your MySQL password here
        database="airline"
    )

# ---------------- HOME ----------------
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        role = request.form['role']
        return redirect(url_for('login', role=role))
    return render_template('role_selection.html')



# ---------------- REGISTER ----------------

from mysql.connector import IntegrityError

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password'].strip()
        name = request.form['name'].strip()
        age = request.form['age']
        gender = request.form['gender']

        conn = get_db_connection()
        conn.autocommit = False  # 🔥 ensure IntegrityError is raised properly
        cursor = conn.cursor()

        try:
            # Try inserting new user
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                (username, password, 'passenger')
            )

            # Get user_id
            cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
            user_id = cursor.fetchone()[0]

            # Create passenger record
            cursor.execute(
                "INSERT INTO passengers (name, age, gender, user_id) VALUES (%s, %s, %s, %s)",
                (name, age, gender, user_id)
            )

            conn.commit()
            flash("✅ Account created successfully! You can now log in.")
            return redirect(url_for('login', role='passenger'))

        except IntegrityError as e:
            conn.rollback()
            print("⚠️ Duplicate username error caught:", e)
            flash("❌ Username already exists! Please choose a different one.")
            return redirect(url_for('register'))

        except mysql.connector.Error as err:
            conn.rollback()
            print("❌ Database error:", err)
            flash(f"❌ Database error: {err}")
            return redirect(url_for('register'))

        finally:
            cursor.close()
            conn.close()

    return render_template('register.html')



# ---------------- DELETE FLIGHT ----------------
@app.route('/delete_flight/<int:flight_id>', methods=['POST'])
def delete_flight(flight_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Step 1 – Delete related bookings
    cursor.execute("DELETE FROM bookings WHERE flight_id = %s", (flight_id,))

    # Step 2 – Delete related seats
    cursor.execute("DELETE FROM seats WHERE flight_id = %s", (flight_id,))

    # Step 3 – Delete the flight itself
    cursor.execute("DELETE FROM flights WHERE id = %s", (flight_id,))
    conn.commit()

    cursor.close()
    conn.close()
    flash("✈️ Flight deleted successfully!")
    return redirect('/admin_dashboard')

# ---------------- LOGIN ----------------

@app.route('/login/<role>', methods=['GET', 'POST'])
def login(role):
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s AND role=%s", 
                       (username, password, role))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['username'] = username
            session['role'] = role
            if role == 'admin':
                return redirect('/admin_dashboard')
            else:
                return redirect('/passenger_dashboard')
        else:
            flash("❌ Invalid username or password")
            return redirect(url_for('login', role=role))

    messages = get_flashed_messages()
    return render_template('login.html', role=role, messages=messages)


# ---------------- ADMIN DASHBOARD ----------------
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' not in session or session['role'] != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # dictionary=True returns rows as dicts
    cursor.execute("SELECT * FROM flights")
    flights = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('admin_dashboard.html', flights=flights)

# ---------------- ADD FLIGHT ----------------
@app.route('/add_flight', methods=['POST'])
def add_flight():
    if 'username' not in session or session['role'] != 'admin':
        return redirect('/login')

    source = request.form['source']
    destination = request.form['destination']
    departure_time = request.form['departure_time']
    arrival_time = request.form['arrival_time']
    price = request.form['price']  # NEW

    conn = get_db_connection()
    cursor = conn.cursor()

    # Insert flight with price
    cursor.execute(
        "INSERT INTO flights (source, destination, departure_time, arrival_time, price) VALUES (%s, %s, %s, %s, %s)",
        (source, destination, departure_time, arrival_time, price)
    )
    conn.commit()

    # Get newly created flight ID
    flight_id = cursor.lastrowid

    # Create 30 seats for that flight
    seat_rows = ['A', 'B', 'C', 'D', 'E', 'F']
    for row in seat_rows:
        for num in range(1, 6):
            seat_number = f"{row}{num}"
            cursor.execute(
                "INSERT INTO seats (flight_id, seat_number, is_booked) VALUES (%s, %s, %s)",
                (flight_id, seat_number, False)
            )

    conn.commit()
    cursor.close()
    conn.close()

    flash("✈️ Flight added successfully with 30 seats!")
    return redirect('/admin_dashboard')


# ---------------- VIEW PASSENGERS FOR A FLIGHT ----------------
@app.route('/view_passengers/<int:flight_id>')
def view_passengers(flight_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get flight details
    cursor.execute("SELECT * FROM flights WHERE id=%s", (flight_id,))
    flight = cursor.fetchone()

    # Get passengers + seat + passenger_id
    cursor.execute("""
        SELECT 
            p.passenger_id,
            p.name, 
            p.age, 
            p.gender, 
            s.seat_number
        FROM bookings b
        JOIN passengers p ON b.passenger_id = p.passenger_id
        JOIN seats s ON b.seat_id = s.seat_id
        WHERE b.flight_id = %s
    """, (flight_id,))
    passengers = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('view_passengers.html',
                           flight=flight,
                           passengers=passengers)



@app.route('/passenger_dashboard')
def passenger_dashboard():
    if 'username' not in session or session['role'] != 'passenger':
        return redirect('/login')

    username = session['username']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE username=%s", (username,))
    user_id = cursor.fetchone()[0]

    cursor.execute("SELECT passenger_id FROM passengers WHERE user_id=%s", (user_id,))
    passenger_id = cursor.fetchone()[0]

    # -------- SORTING LOGIC ----------
    sort = request.args.get("sort_by")

    if sort == "departure":
        cursor.execute("SELECT * FROM flights ORDER BY departure_time")
    elif sort == "arrival":
        cursor.execute("SELECT * FROM flights ORDER BY arrival_time")
    elif sort == "price":
        cursor.execute("SELECT * FROM flights ORDER BY price")
    else:
        cursor.execute("SELECT * FROM flights")

    flights = cursor.fetchall()

    # -------- BOOKED FLIGHTS ----------
    cursor.execute("""
        SELECT b.booking_id, f.id, f.source, f.destination, 
               f.departure_time, f.arrival_time, s.seat_number
        FROM bookings b
        JOIN flights f ON b.flight_id = f.id
        JOIN seats s ON b.seat_id = s.seat_id
        WHERE b.passenger_id = %s
    """, (passenger_id,))
    booked_flights = cursor.fetchall()

    # -------- FOOD ORDERS ----------
    cursor.execute("""
        SELECT fo.booking_id, fi.name, fi.price, fo.quantity
        FROM food_orders fo
        JOIN food_items fi ON fo.food_id = fi.id
        WHERE fo.booking_id IN (
            SELECT booking_id FROM bookings WHERE passenger_id = %s
        )
    """, (passenger_id,))
    food_orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("passenger_dashboard.html",
                           flights=flights,
                           booked_flights=booked_flights,
                           food_orders=food_orders)

@app.route('/admin/view_food/<int:passenger_id>')
def admin_view_food(passenger_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get passenger info
    cursor.execute("SELECT name FROM passengers WHERE passenger_id=%s", (passenger_id,))
    passenger = cursor.fetchone()

    # Fetch food orders WITH seat number
    cursor.execute("""
        SELECT 
            fo.booking_id,
            s.seat_number,
            fi.name AS food_name,
            fi.price,
            fo.quantity
        FROM food_orders fo
        JOIN bookings b ON fo.booking_id = b.booking_id
        JOIN seats s ON b.seat_id = s.seat_id
        JOIN food_items fi ON fo.food_id = fi.id
        WHERE b.passenger_id = %s
    """, (passenger_id,))
    food_orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin_food_orders.html",
                           passenger=passenger,
                           food_orders=food_orders)




# ---------------- BOOK FLIGHT (redirects to seat selection) ----------------
@app.route('/book_flight', methods=['POST'])
def book_flight():
    if 'username' not in session or session['role'] != 'passenger':
        return redirect('/login')

    flight_id = request.form['flight_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE username=%s", (session['username'],))
    user_id = cursor.fetchone()[0]

    cursor.execute("SELECT passenger_id FROM passengers WHERE user_id=%s", (user_id,))
    passenger_id = cursor.fetchone()[0]

    # Store passenger_id in session (IMPORTANT FIX)
    session['passenger_id'] = passenger_id

    cursor.close()
    conn.close()

    return redirect(url_for('select_seat', flight_id=flight_id))


@app.route('/order_food/<int:booking_id>/<seat_number>', methods=['GET', 'POST'])
def order_food(booking_id, seat_number):
    if 'username' not in session or session['role'] != 'passenger':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # fetch menu items
    cursor.execute("SELECT * FROM food_items")
    menu = cursor.fetchall()

    if request.method == 'POST':
        food_ids = request.form.getlist('food_id')
        quantities = request.form.getlist('qty')

        for fid, qty in zip(food_ids, quantities):
            if int(qty) > 0:
                cursor.execute(
                    "INSERT INTO food_orders (booking_id, food_id, quantity) VALUES (%s, %s, %s)",
                    (booking_id, fid, qty)
                )

        conn.commit()
        cursor.close()
        conn.close()

        return render_template("payment_success.html", message="Food Order Successful!")

    cursor.close()
    conn.close()

    return render_template("order_food.html",
                           menu=menu,
                           booking_id=booking_id,
                           seat_number=seat_number)



# ---------------- SEAT SELECTION----------------

@app.route('/select_seat/<int:flight_id>', methods=['GET', 'POST'])
def select_seat(flight_id):
    if 'username' not in session or session['role'] != 'passenger':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch flight details
    cursor.execute('SELECT * FROM flights WHERE id = %s', (flight_id,))
    flight = cursor.fetchone()

    # Store flight info in session (price, source, destination)
    session['flight_source'] = flight['source']
    session['flight_destination'] = flight['destination']
    session['flight_price'] = flight['price']

    # Fetch seats
    cursor.execute('SELECT * FROM seats WHERE flight_id = %s', (flight_id,))
    seats = cursor.fetchall()

    # ALWAYS fetch passenger_id and store in session
    cursor.execute("SELECT user_id FROM users WHERE username=%s", (session['username'],))
    user_id = cursor.fetchone()['user_id']

    cursor.execute("SELECT passenger_id FROM passengers WHERE user_id=%s", (user_id,))
    passenger_id = cursor.fetchone()['passenger_id']

    session['passenger_id'] = passenger_id  # IMPORTANT

    cursor.close()
    conn.close()

    # If user submits seat selection
    if request.method == 'POST':
        selected_seats = request.form.getlist('seat_id')
        if not selected_seats:
            flash("Please select at least one seat.")
            return redirect(url_for('select_seat', flight_id=flight_id))

        session['selected_seats'] = selected_seats
        session['flight_id'] = flight_id
        return redirect(url_for('transaction'))

    return render_template('select_seat.html', flight=flight, seats=seats)


# ---------------- CONFIRM SEAT ----------------
@app.route('/confirm_seat/<int:seat_id>', methods=['POST'])
def confirm_seat(seat_id):
    if 'username' not in session or session['role'] != 'passenger':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT is_booked, flight_id FROM seats WHERE seat_id = %s', (seat_id,))
    seat = cursor.fetchone()

    if not seat:
        cursor.close()
        conn.close()
        flash("❌ Invalid seat selected.")
        return redirect('/passenger_dashboard')

    if not seat[0]:  # seat available
        flight_id = seat[1]

        cursor.execute("SELECT user_id FROM users WHERE username=%s", (session['username'],))
        user_id = cursor.fetchone()[0]
        cursor.execute("SELECT passenger_id FROM passengers WHERE user_id=%s", (user_id,))
        passenger_id = cursor.fetchone()[0]

        cursor.execute('UPDATE seats SET is_booked = TRUE WHERE seat_id = %s', (seat_id,))
        cursor.execute('INSERT INTO bookings (passenger_id, flight_id, seat_id) VALUES (%s, %s, %s)',
                       (passenger_id, flight_id, seat_id))

        conn.commit()
        cursor.close()
        conn.close()
        flash("✅ Seat booked successfully!")
        return redirect('/passenger_dashboard')

    else:
        cursor.close()
        conn.close()
        flash("❌ Seat already booked. Please select another.")
        return redirect(url_for('select_seat', flight_id=seat[1]))


@app.route('/transaction', methods=['GET', 'POST'])
def transaction():

    # Prevent direct access
    if 'selected_seats' not in session or 'flight_id' not in session:
        flash("No seat selection found.")
        return redirect(url_for('passenger_dashboard'))

    flight_id = session['flight_id']
    selected_seat_ids = session['selected_seats']
    passenger_id = session['passenger_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch flight details including price
    cursor.execute("SELECT source, destination, price FROM flights WHERE id=%s", (flight_id,))
    flight = cursor.fetchone()
    price_per_seat = flight['price']

    # Fetch seat details
    format_ids = ",".join(["%s"] * len(selected_seat_ids))
    cursor.execute(f"SELECT seat_id, seat_number FROM seats WHERE seat_id IN ({format_ids})", selected_seat_ids)
    seats = cursor.fetchall()

    total_amount = price_per_seat * len(seats)

    # ---------- PAYMENT CONFIRMATION ----------
    if request.method == 'POST':

        booking_ids = []

        for seat in seats:
            cursor.execute("""
                INSERT INTO bookings(passenger_id, flight_id, seat_id)
                VALUES (%s, %s, %s)
            """, (passenger_id, flight_id, seat['seat_id']))

            booking_ids.append(cursor.lastrowid)

            # Mark seat booked
            cursor.execute("UPDATE seats SET is_booked=1 WHERE seat_id=%s", (seat['seat_id'],))

        conn.commit()
        cursor.close()
        conn.close()

        # Clear session
        session.pop('selected_seats', None)
        session.pop('flight_id', None)

        return redirect(url_for('payment_success'))

    # ---------- SHOW TRANSACTION PAGE (GET) ----------
    cursor.close()
    conn.close()

    return render_template(
        'transaction.html',
        seats=seats,
        total_amount=total_amount,
        flight={'source': flight['source'], 'destination': flight['destination']}
    )



@app.route("/payment_success")
def payment_success():
    return render_template("payment_success.html")





@app.route("/payment_failed")
def payment_failed():
    return "Payment Failed. Try again."


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('home'))



# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(debug=True, port=5001)
