from flask import Flask, request, jsonify, session
import sqlite3
import datetime


app = Flask(__name__)
app.secret_key = "supersecretkey"

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    return "Hello, Flask is running!"

# @app.route('/login', methods=['POST'])
# def login():
#     data = request.json
#     username = data.get("username")
#     password = data.get("password")
#     if username == "host" and password == "party123":
#         session['logged_in'] = True
#         return jsonify({"message": "Login successful"})
#     else:
#         return jsonify({"message": "Invalid credentials"}), 401


from flask import render_template, request, redirect, url_for, session

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'host' and password == 'party123':
            session['logged_in'] = True
            return redirect(url_for('events'))
        else:
            return "Invalid credentials", 401
    return render_template('login.html')


@app.route('/events', methods=['GET', 'POST'])
def events():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    if request.method == 'POST':
        new_event = request.form['new_event']
        if new_event:
            try:
                conn.execute("INSERT INTO events (name) VALUES (?)", (new_event,))
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # event name already exists, ignore
        session['event'] = new_event
        return redirect(url_for('dashboard'))

    # show list of events
    events = conn.execute("SELECT name FROM events").fetchall()
    conn.close()
    return render_template("events.html", events=events)






# @app.route('/dashboard')
# def dashboard():
#     if 'logged_in' not in session:
#         return redirect(url_for('login'))
#     return "<h2>Dashboard placeholder — more coming next step.</h2>"

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()  # 🔹 Add this line

    if request.method == 'POST':
        selected_event = request.form['event']
        session['event'] = selected_event

    event = session.get('event')

    events = conn.execute("SELECT name FROM events").fetchall()  # 🔹 Fetch all event names
    conn.close()  # 🔹 Close connection

    return render_template('dashboard.html', event=event, events=events)


@app.route('/add', methods=['GET', 'POST'])
def add_entry():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    qr_filename = None
    if request.method == 'POST':
        name = request.form['name']
        num_people = int(request.form['num_people'])
        amount = int(request.form['amount'])
        user_id = request.form.get('user_id', '')
        event = session.get('event', 'N/A')


        # create unique ticket_id
        ticket_id = f"TKT{int(datetime.datetime.now().timestamp())}"

        # insert to database
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute(
          "INSERT INTO tickets (ticket_id, name, num_people, checked_in, seats_left, event, user_id) VALUES (?, ?, ?, 0, ?, ?, ?)",
          (ticket_id, name, num_people, num_people, event, user_id)
        )


        conn.commit()
        conn.close()

        # generate qr
        qr = qrcode.make(ticket_id)
        qr_filename = f"{ticket_id}.png"
        qr.save(os.path.join('static', 'qrcodes', qr_filename))

    return render_template('add.html', qr_filename=qr_filename)


# @app.route('/scan', methods=['POST'])
# def scan_ticket():
#     if 'logged_in' not in session:
#         return jsonify({"error": "Unauthorized"}), 401
#     data = request.json
#     ticket_id = data.get('ticket_id')
#     conn = get_db_connection()
#     ticket = conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
#     conn.close()
#     if ticket is None:
#         return jsonify({"status": "invalid", "message": "Ticket not found"})
#     if ticket['seats_used'] >= ticket['total_seats']:
#         return jsonify({"status": "invalid", "message": "Ticket already fully used"})
#     seats_left = ticket['total_seats'] - ticket['seats_used']
#     return jsonify({
#         "status": "valid",
#         "name": ticket['name'],
#         "seats_left": seats_left
#     })

@app.route('/scan', methods=['GET', 'POST'])
def scan_ticket():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('scan.html')

    # POST logic: handling scanned QR
    data = request.json
    ticket_id = data.get('ticket_id')
    conn = get_db_connection()
    ticket = conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    conn.close()

    if ticket is None:
        return jsonify({"status": "invalid", "message": "Ticket not found"})

    # Special handling for exactly 1 seat left to prevent race conditions
    if ticket['seats_left'] == 1:
        # For exactly 1 seat left, we'll allow the scan but indicate it's the last entry
        return jsonify({
            "status": "valid",
            "name": ticket['name'],
            "seats_left": ticket['seats_left'],
            "is_last_entry": True
        })
    elif ticket['seats_left'] <= 0:
        return jsonify({"status": "invalid", "message": "Ticket already fully used"})

    return jsonify({
        "status": "valid",
        "name": ticket['name'],
        "seats_left": ticket['seats_left']
    })




@app.route('/checkin', methods=['POST'])
def checkin():
    if 'logged_in' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    ticket_id = data.get('ticket_id')
    num_people = int(data.get('num_people', 1))

    conn = get_db_connection()
    ticket = conn.execute("SELECT seats_left, checked_in FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()

    if ticket is None:
        conn.close()
        return jsonify({"status": "invalid", "message": "Ticket not found"})

    if num_people > ticket['seats_left']:
        conn.close()
        return jsonify({"status": "invalid", "message": "Not enough seats left"})

    new_checked_in = ticket['checked_in'] + num_people
    new_seats_left = ticket['seats_left'] - num_people

    conn.execute("UPDATE tickets SET checked_in = ?, seats_left = ? WHERE ticket_id = ?",
                 (new_checked_in, new_seats_left, ticket_id))
    conn.commit()
    conn.close()

    # Special message for the last entry
    if new_seats_left == 0:
        return jsonify({"status": "success", "message": "All guests checked in. Ticket fully used."})
    else:
        return jsonify({"status": "success", "message": f"{new_seats_left} left."})


import qrcode
import os

@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    if 'logged_in' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    name = data.get("name")
    total_seats = data.get("total_seats")

    if not name or not total_seats:
        return jsonify({"error": "Missing name or total_seats"}), 400

    # Generate a ticket ID like TKT001, TKT002, etc
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    ticket_id = f"TKT{count+1:03d}"

    # Insert into the database
    conn.execute(
        "INSERT INTO tickets (ticket_id, name, total_seats, seats_used, status) VALUES (?, ?, ?, ?, ?)",
        (ticket_id, name, total_seats, 0, "active")
    )
    conn.commit()
    conn.close()

    # Generate the QR code
    qr = qrcode.make(ticket_id)
    qr_path = os.path.join("qrcodes", f"{ticket_id}.png")
    qr.save(qr_path)

    return jsonify({
        "message": "Ticket created",
        "ticket_id": ticket_id,
        "qr_image": qr_path
    })


from flask import send_from_directory

# Removed duplicate scan route to prevent conflicts




@app.route('/list')
def list_entries():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    event = session.get('event', 'N/A')

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM tickets WHERE event = ?", (event,))
    entries = c.fetchall()
    conn.close()

    return render_template('list.html', entries=entries, event=event)






@app.route('/manual_checkin', methods=['POST'])
def manual_checkin():
    if 'logged_in' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.get_json()
    ticket_id = data.get('ticket_id')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT seats_left FROM tickets WHERE ticket_id = ?", (ticket_id,))
    row = c.fetchone()

    if row and row[0] > 0:
        new_seats_left = row[0] - 1
        c.execute("UPDATE tickets SET seats_left = ?, checked_in = checked_in + 1 WHERE ticket_id = ?",
                  (new_seats_left, ticket_id))
        conn.commit()
        conn.close()
        return jsonify({"message": "Manual check-in recorded."})
    else:
        conn.close()
        return jsonify({"message": "No seats left to check in."})
    

@app.route('/delete', methods=['POST'])
def delete_guest():
    if 'logged_in' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.get_json()
    ticket_id = data.get('ticket_id')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM tickets WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Guest deleted."})


@app.route('/delete_event', methods=['POST'])
def delete_event():
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"})

    data = request.get_json()
    event_name = data.get('name')

    conn = get_db_connection()
    conn.execute("DELETE FROM events WHERE name = ?", (event_name,))
    conn.commit()
    conn.close()

    return jsonify({"success": True})





if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)

