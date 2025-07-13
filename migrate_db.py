import sqlite3

def migrate_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Add new columns to events table
    try:
        c.execute('ALTER TABLE events ADD COLUMN venue TEXT')
        print("Added venue column")
    except sqlite3.OperationalError:
        print("venue column already exists")
    
    try:
        c.execute('ALTER TABLE events ADD COLUMN organizer_name TEXT')
        print("Added organizer_name column")
    except sqlite3.OperationalError:
        print("organizer_name column already exists")
    
    try:
        c.execute('ALTER TABLE events ADD COLUMN organizer_phone TEXT')
        print("Added organizer_phone column")
    except sqlite3.OperationalError:
        print("organizer_phone column already exists")
    
    try:
        c.execute('ALTER TABLE events ADD COLUMN organizer_email TEXT')
        print("Added organizer_email column")
    except sqlite3.OperationalError:
        print("organizer_email column already exists")
    
    # Update existing sample event with contact information
    c.execute('''
        UPDATE events 
        SET venue = 'My House, 123 Main St, City',
            organizer_name = 'John Doe',
            organizer_phone = '+91 98765 43210',
            organizer_email = 'john@example.com'
        WHERE name = 'Sample Party'
    ''')
    
    conn.commit()
    conn.close()
    print("Database migration completed successfully!")

if __name__ == '__main__':
    migrate_db() 