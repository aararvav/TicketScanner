import sqlite3
import bcrypt
import re
from datetime import datetime, timedelta
from flask import request
import csv
import json
import os
from werkzeug.utils import secure_filename

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """Check if password matches hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format"""
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    return len(digits) >= 10

def validate_ticket_data(name, num_people, amount, email=None, phone=None):
    """Validate ticket input data"""
    errors = []
    
    if not name or len(name.strip()) < 2:
        errors.append("Name must be at least 2 characters long")
    
    if not num_people or num_people < 1:
        errors.append("Number of people must be at least 1")
    
    if not amount or amount < 0:
        errors.append("Amount must be non-negative")
    
    if email and not validate_email(email):
        errors.append("Invalid email format")
    
    if phone and not validate_phone(phone):
        errors.append("Invalid phone number format")
    
    return errors

def check_rate_limit(ip_address, username):
    """Check if user has exceeded login attempts"""
    conn = get_db_connection()
    
    # Get recent failed attempts
    recent_attempts = conn.execute('''
        SELECT COUNT(*) FROM login_attempts 
        WHERE ip_address = ? AND username = ? AND success = FALSE 
        AND attempt_time > datetime('now', '-15 minutes')
    ''', (ip_address, username)).fetchone()[0]
    
    conn.close()
    return recent_attempts < 5

def record_login_attempt(ip_address, username, success):
    """Record a login attempt"""
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO login_attempts (ip_address, username, success)
        VALUES (?, ?, ?)
    ''', (ip_address, username, success))
    conn.commit()
    conn.close()

def create_backup():
    """Create a database backup"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'backup_{timestamp}.db'
    
    # Copy database
    import shutil
    shutil.copy2('database.db', f'backups/{backup_filename}')
    
    # Record backup in database
    conn = get_db_connection()
    size = os.path.getsize(f'backups/{backup_filename}')
    conn.execute('''
        INSERT INTO backups (filename, size_bytes, description)
        VALUES (?, ?, ?)
    ''', (backup_filename, size, f'Automatic backup created at {timestamp}'))
    conn.commit()
    conn.close()
    
    return backup_filename

def export_data_to_csv(event_name):
    """Export event data to CSV"""
    conn = get_db_connection()
    tickets = conn.execute('''
        SELECT * FROM tickets WHERE event = ?
    ''', (event_name,)).fetchall()
    conn.close()
    
    if not tickets:
        return None
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'export_{event_name}_{timestamp}.csv'
    
    with open(f'exports/{filename}', 'w', newline='') as csvfile:
        fieldnames = ['ticket_id', 'name', 'email', 'phone', 'num_people', 
                     'checked_in', 'seats_left', 'ticket_type', 'price', 
                     'payment_status', 'purchase_date', 'notes']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for ticket in tickets:
            writer.writerow(dict(ticket))
    
    return filename

def import_guest_list(file_path, event_name):
    """Import guest list from CSV"""
    conn = get_db_connection()
    
    with open(file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            conn.execute('''
                INSERT OR IGNORE INTO guest_lists 
                (event_name, name, email, phone, num_people, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                event_name,
                row.get('name', ''),
                row.get('email', ''),
                row.get('phone', ''),
                int(row.get('num_people', 1)),
                row.get('notes', '')
            ))
    
    conn.commit()
    conn.close()

def get_event_stats(event_name):
    """Get statistics for an event"""
    conn = get_db_connection()
    
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_tickets,
            SUM(num_people) as total_people,
            SUM(checked_in) as total_checked_in,
            SUM(seats_left) as total_seats_left,
            SUM(price) as total_revenue
        FROM tickets 
        WHERE event = ?
    ''', (event_name,)).fetchone()
    
    conn.close()
    return dict(stats)

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'csv', 'txt'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_directories():
    """Create necessary directories"""
    directories = ['backups', 'exports', 'static/uploads']
    for directory in directories:
        os.makedirs(directory, exist_ok=True) 