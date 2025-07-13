import sqlite3
import bcrypt
from datetime import datetime

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Create users table with proper authentication
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Create events table with more details
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            date DATE,
            time TIME,
            location TEXT,
            venue TEXT,
            organizer_name TEXT,
            organizer_phone TEXT,
            organizer_email TEXT,
            capacity INTEGER,
            ticket_price DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create tickets table with improved schema
    c.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            num_people INTEGER NOT NULL,
            checked_in INTEGER DEFAULT 0,
            seats_left INTEGER NOT NULL,
            event TEXT NOT NULL,
            user_id TEXT,
            ticket_type TEXT DEFAULT 'regular',
            price DECIMAL(10,2),
            payment_status TEXT DEFAULT 'paid',
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    ''')
    
    # Create guest_lists table for pre-uploaded guests
    c.execute('''
        CREATE TABLE IF NOT EXISTS guest_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            num_people INTEGER DEFAULT 1,
            rsvp_status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create login_attempts table for rate limiting
    c.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            username TEXT NOT NULL,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Create backups table
    c.execute('''
        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            size_bytes INTEGER,
            description TEXT
        )
    ''')
    
    # Insert default admin user
    default_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
    c.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, email, role)
        VALUES (?, ?, ?, ?)
    ''', ('admin', default_password.decode('utf-8'), 'admin@example.com', 'admin'))
    
    # Insert some sample events
    c.execute('''
        INSERT OR IGNORE INTO events (name, description, date, time, location, venue, organizer_name, organizer_phone, organizer_email, capacity, ticket_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('Sample Party', 'A sample event for testing', '2025-01-15', '19:00', 'My House', 'My House, 123 Main St, City', 'John Doe', '+91 98765 43210', 'john@example.com', 50, 25.00))
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")
    print("Default admin credentials: username='admin', password='admin123'")

if __name__ == '__main__':
    init_db() 