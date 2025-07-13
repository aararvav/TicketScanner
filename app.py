from flask import Flask, request, jsonify, session, render_template, redirect, url_for, flash, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import sqlite3
from datetime import datetime
import qrcode
import os
import json
from werkzeug.utils import secure_filename
from config import Config
from utils import *

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Flask-Limiter for rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Create necessary directories
create_directories()

class User(UserMixin):
    def __init__(self, id, username, email, role):
        self.id = id
        self.username = username
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['email'], user_data['role'])
    return None

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check rate limiting
        if not check_rate_limit(request.remote_addr, username):
            flash('Too many login attempts. Please try again later.', 'error')
            return render_template('login.html')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password(password, user['password_hash']):
            user_obj = User(user['id'], user['username'], user['email'], user['role'])
            login_user(user_obj)
            
            # Update last login
            conn = get_db_connection()
            conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            conn.commit()
            conn.close()
            
            record_login_attempt(request.remote_addr, username, True)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            record_login_attempt(request.remote_addr, username, False)
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    conn = get_db_connection()
    
    if request.method == 'POST':
        selected_event = request.form['event']
        session['event'] = selected_event
    
    event = session.get('event')
    events = conn.execute("SELECT * FROM events ORDER BY date DESC").fetchall()
    
    # Set default event if none is selected and events exist
    if not event and events:
        event = events[0]['name']
        session['event'] = event
    
    # Get event statistics
    event_stats = None
    if event:
        event_stats = get_event_stats(event)
    
    conn.close()
    return render_template('dashboard.html', event=event, events=events, stats=event_stats)

@app.route('/events', methods=['GET', 'POST'])
@login_required
def events():
    conn = get_db_connection()
    
    if request.method == 'POST':
        print("POST request received for events")
        print("Form data received:", dict(request.form))
        event_name = request.form.get('event_name')
        description = request.form.get('description')
        event_date = request.form.get('event_date')
        event_time = request.form.get('event_time')
        venue = request.form.get('venue')
        max_capacity = request.form.get('max_capacity')
        ticket_price = request.form.get('ticket_price')
        organizer_name = request.form.get('organizer_name')
        organizer_phone = request.form.get('organizer_phone')
        organizer_email = request.form.get('organizer_email')
        
        print(f"Form data: event_name={event_name}, venue={venue}, organizer_name={organizer_name}")
        
        if event_name:
            try:
                conn.execute('''
                    INSERT INTO events (name, description, date, time, venue, organizer_name, organizer_phone, organizer_email, capacity, ticket_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (event_name, description, event_date, event_time, venue, organizer_name, organizer_phone, organizer_email, max_capacity, ticket_price))
                conn.commit()
                flash('Event created successfully!', 'success')
            except sqlite3.IntegrityError as e:
                print('DB IntegrityError:', e)
                flash('Event name already exists.', 'error')
            except Exception as e:
                print('DB Exception:', e)
                flash('Error creating event: ' + str(e), 'error')
        
        session['event'] = event_name
        return redirect(url_for('events'))
    
    events = conn.execute("SELECT * FROM events ORDER BY date DESC").fetchall()
    conn.close()
    return render_template("events.html", events=events)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_entry():
    qr_filename = None
    errors = []
    
    # Get current event from session
    event = session.get('event')
    if not event:
        # Get the first available event if none is selected
        conn_temp = get_db_connection()
        first_event = conn_temp.execute("SELECT name FROM events ORDER BY date DESC LIMIT 1").fetchone()
        conn_temp.close()
        event = first_event['name'] if first_event else 'N/A'
        session['event'] = event
    
    if request.method == 'POST':
        name = request.form['name']
        num_people = int(request.form.get('num_people', 1))
        amount = float(request.form.get('amount', 0))
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')
        ticket_type = request.form.get('ticket_type', 'regular')
        notes = request.form.get('notes', '')
        
        # Validate input
        errors = validate_ticket_data(name, num_people, amount, email, phone)
        
        if not errors:
            # Create unique ticket_id
            ticket_id = f"TKT{int(datetime.now().timestamp())}"
            
            # Insert to database
            conn = get_db_connection()
            try:
                conn.execute('''
                    INSERT INTO tickets (ticket_id, name, email, phone, num_people, checked_in, 
                                       seats_left, event, user_id, ticket_type, price, notes)
                    VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
                ''', (ticket_id, name, email, phone, num_people, num_people, event, '', ticket_type, amount, notes))
                conn.commit()
                
                # Generate QR code
                qr = qrcode.make(ticket_id)
                qr_filename = f"{ticket_id}.png"
                qr.save(os.path.join('static', 'qrcodes', qr_filename))
                
                flash('Ticket created successfully!', 'success')
                
            except Exception as e:
                flash(f'Error creating ticket: {str(e)}', 'error')
            finally:
                conn.close()
        else:
            for error in errors:
                flash(error, 'error')
    
    # Get event information for the ticket card
    event_info = None
    if event and event != 'N/A':
        conn = get_db_connection()
        event_data = conn.execute("SELECT * FROM events WHERE name = ?", (event,)).fetchone()
        conn.close()
        if event_data:
            # Convert sqlite3.Row to dict for safer access
            event_dict = dict(event_data)
            # Convert date from YYYY-MM-DD to DDMMYYYY format
            date_str = event_dict.get('date', '')
            if date_str:
                try:
                    # Parse the date and reformat it
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%d%m%Y')
                except:
                    formatted_date = date_str
            else:
                formatted_date = ''
            
            event_info = {
                'name': event_dict.get('name'),
                'date': formatted_date,
                'time': event_dict.get('time'),
                'location': event_dict.get('location'),
                'venue': event_dict.get('venue'),
                'organizer_name': event_dict.get('organizer_name'),
                'organizer_phone': event_dict.get('organizer_phone'),
                'organizer_email': event_dict.get('organizer_email')
            }
    
    return render_template('add.html', qr_filename=qr_filename, event_info=event_info)

@app.route('/scan', methods=['GET', 'POST'])
@login_required
def scan_ticket():
    if request.method == 'GET':
        return render_template('scan.html')
    
    # Handle manual entry (form submission)
    if request.form:
        ticket_id = request.form.get('ticket_id')
        if not ticket_id:
            flash('No ticket ID provided', 'error')
            return redirect(url_for('scan_ticket'))
        
        conn = get_db_connection()
        ticket = conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
        conn.close()
        
        if ticket is None:
            flash('Ticket not found', 'error')
            return redirect(url_for('scan_ticket'))
        
        if ticket['seats_left'] <= 0:
            flash('Ticket already fully used', 'error')
            return redirect(url_for('scan_ticket'))
        
        # Show ticket info for manual check-in
        return render_template('scan.html', ticket=ticket)
    
    # Handle JSON requests (QR scanning)
    data = request.json
    ticket_id = data.get('ticket_id')
    
    if not ticket_id:
        return jsonify({"success": False, "message": "No ticket ID provided"})
    
    conn = get_db_connection()
    ticket = conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    conn.close()
    
    if ticket is None:
        return jsonify({"success": False, "message": "Ticket not found"})
    
    if ticket['seats_left'] <= 0:
        return jsonify({"success": False, "message": "Ticket already fully used"})
    
    return jsonify({
        "success": True,
        "guest_name": ticket['name'],
        "seats_left": f"{ticket['seats_left']} seats left"
    })

@app.route('/checkin', methods=['POST'])
@login_required
def checkin():
    data = request.json
    ticket_id = data.get('ticket_id')
    num_people = int(data.get('num_people', 1))
    
    if not ticket_id:
        return jsonify({"success": False, "message": "No ticket ID provided"})
    
    conn = get_db_connection()
    ticket = conn.execute("SELECT seats_left, checked_in FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    
    if ticket is None:
        conn.close()
        return jsonify({"success": False, "message": "Ticket not found"})
    
    if num_people > ticket['seats_left']:
        conn.close()
        return jsonify({"success": False, "message": "Not enough seats left"})
    
    new_checked_in = ticket['checked_in'] + num_people
    new_seats_left = ticket['seats_left'] - num_people
    
    conn.execute("UPDATE tickets SET checked_in = ?, seats_left = ? WHERE ticket_id = ?",
                 (new_checked_in, new_seats_left, ticket_id))
    conn.commit()
    conn.close()
    
    if new_seats_left == 0:
        return jsonify({"success": True, "message": "All guests checked in. Ticket fully used."})
    else:
        return jsonify({"success": True, "message": f"{new_seats_left} seats left."})

@app.route('/list')
@login_required
def list_entries():
    event = session.get('event')
    if not event:
        # Get the first available event if none is selected
        conn_temp = get_db_connection()
        first_event = conn_temp.execute("SELECT name FROM events ORDER BY date DESC LIMIT 1").fetchone()
        conn_temp.close()
        event = first_event['name'] if first_event else 'N/A'
        session['event'] = event
    
    conn = get_db_connection()
    tickets = conn.execute("SELECT * FROM tickets WHERE event = ? ORDER BY purchase_date DESC", (event,)).fetchall()
    conn.close()
    
    return render_template('list.html', tickets=tickets, event=event)

@app.route('/guest_list', methods=['GET', 'POST'])
@login_required
def guest_list():
    event = session.get('event', 'N/A')
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join('static/uploads', filename)
            file.save(filepath)
            
            try:
                import_guest_list(filepath, event)
                flash('Guest list imported successfully!', 'success')
            except Exception as e:
                flash(f'Error importing guest list: {str(e)}', 'error')
            finally:
                os.remove(filepath)  # Clean up uploaded file
    
    conn = get_db_connection()
    guests = conn.execute("SELECT * FROM guest_lists WHERE event_name = ? ORDER BY name", (event,)).fetchall()
    conn.close()
    
    return render_template('guest_list.html', guests=guests, event=event)

@app.route('/export/<event_name>')
@login_required
def export_event(event_name):
    filename = export_data_to_csv(event_name)
    if filename:
        return send_file(f'exports/{filename}', as_attachment=True)
    else:
        flash('No data to export for this event', 'error')
        return redirect(url_for('dashboard'))

@app.route('/backup')
@login_required
def create_backup_route():
    try:
        filename = create_backup()
        flash(f'Backup created: {filename}', 'success')
    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/stats')
@login_required
def stats():
    event = session.get('event', 'N/A')
    stats = get_event_stats(event) if event else None
    return render_template('stats.html', stats=stats, event=event)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/edit_ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def edit_ticket(ticket_id):
    if request.method == 'GET':
        conn = get_db_connection()
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        conn.close()
        
        if not ticket:
            flash('Ticket not found', 'error')
            return redirect(url_for('list_entries'))
        
        return render_template('edit_ticket.html', ticket=ticket)
    
    elif request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form.get('email', '')
            phone = request.form.get('phone', '')
            num_people = int(request.form.get('num_people', 1))
            price = float(request.form.get('price', 0))
            ticket_type = request.form.get('ticket_type', 'regular')
            notes = request.form.get('notes', '')
            
            conn = get_db_connection()
            conn.execute('''
                UPDATE tickets 
                SET name = ?, email = ?, phone = ?, num_people = ?, 
                    price = ?, ticket_type = ?, notes = ?
                WHERE id = ?
            ''', (name, email, phone, num_people, price, ticket_type, notes, ticket_id))
            conn.commit()
            conn.close()
            
            flash('Ticket updated successfully!', 'success')
            return redirect(url_for('list_entries'))
            
        except Exception as e:
            flash(f'Error updating ticket: {str(e)}', 'error')
            return redirect(url_for('edit_ticket', ticket_id=ticket_id))

@app.route('/delete_ticket/<int:ticket_id>', methods=['DELETE'])
@login_required
def delete_ticket(ticket_id):
    try:
        conn = get_db_connection()
        
        # Get ticket info for QR code cleanup
        ticket = conn.execute("SELECT ticket_id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        
        if not ticket:
            conn.close()
            return jsonify({"success": False, "message": "Ticket not found"})
        
        # Delete the ticket from database
        conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        conn.commit()
        conn.close()
        
        # Delete the QR code file if it exists
        qr_filename = f"{ticket['ticket_id']}.png"
        qr_path = os.path.join('static', 'qrcodes', qr_filename)
        if os.path.exists(qr_path):
            os.remove(qr_path)
        
        return jsonify({"success": True, "message": "Ticket deleted successfully"})
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Error deleting ticket: {str(e)}"})

@app.route('/get_event/<int:event_id>')
@login_required
def get_event(event_id):
    try:
        conn = get_db_connection()
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        conn.close()
        
        if not event:
            return jsonify({"success": False, "message": "Event not found"})
        
        # Convert sqlite3.Row to dict
        event_dict = dict(event)
        return jsonify({"success": True, "event": event_dict})
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Error fetching event: {str(e)}"})

@app.route('/update_event/<int:event_id>', methods=['POST'])
@login_required
def update_event(event_id):
    try:
        event_name = request.form.get('event_name')
        description = request.form.get('description')
        event_date = request.form.get('event_date')
        event_time = request.form.get('event_time')
        venue = request.form.get('venue')
        max_capacity = request.form.get('max_capacity')
        ticket_price = request.form.get('ticket_price')
        organizer_name = request.form.get('organizer_name')
        organizer_phone = request.form.get('organizer_phone')
        organizer_email = request.form.get('organizer_email')
        
        if not event_name:
            return jsonify({"success": False, "message": "Event name is required"})
        
        conn = get_db_connection()
        
        # Check if event name already exists (excluding current event)
        existing = conn.execute("SELECT id FROM events WHERE name = ? AND id != ?", (event_name, event_id)).fetchone()
        if existing:
            conn.close()
            return jsonify({"success": False, "message": "Event name already exists"})
        
        # Update the event
        conn.execute('''
            UPDATE events 
            SET name = ?, description = ?, date = ?, time = ?, venue = ?, 
                organizer_name = ?, organizer_phone = ?, organizer_email = ?, 
                capacity = ?, ticket_price = ?
            WHERE id = ?
        ''', (event_name, description, event_date, event_time, venue, 
              organizer_name, organizer_phone, organizer_email, 
              max_capacity, ticket_price, event_id))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Event updated successfully"})
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Error updating event: {str(e)}"})

@app.route('/delete_event/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    try:
        conn = get_db_connection()
        
        # Get event info
        event = conn.execute("SELECT name FROM events WHERE id = ?", (event_id,)).fetchone()
        
        if not event:
            conn.close()
            return jsonify({"success": False, "message": "Event not found"})
        
        # Delete associated tickets
        conn.execute("DELETE FROM tickets WHERE event = ?", (event['name'],))
        
        # Delete the event
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Event deleted successfully"})
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Error deleting event: {str(e)}"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)

