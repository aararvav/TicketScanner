#!/usr/bin/env python3
"""
Test script to verify the bug fix for the 1-seat-left issue
"""

import requests
import json
import time

# Test configuration
BASE_URL = "http://localhost:5000"

def test_bug_fix():
    """Test the bug fix for the 1-seat-left scenario"""
    
    print("Testing bug fix for 1-seat-left scenario...")
    
    # First, we need to login
    session = requests.Session()
    
    # Login
    login_data = {
        'username': 'host',
        'password': 'party123'
    }
    
    response = session.post(f"{BASE_URL}/login", data=login_data)
    if response.status_code != 200:
        print("❌ Failed to login")
        return False
    
    print("✅ Login successful")
    
    # Create a test ticket with 2 people (we'll test the last person scenario)
    # We'll simulate the add_entry process by directly inserting into database
    import sqlite3
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Create a test ticket
    test_ticket_id = f"TEST{int(time.time())}"
    c.execute("""
        INSERT INTO tickets (ticket_id, name, num_people, checked_in, seats_left, event, user_id) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (test_ticket_id, "Test Guest", 2, 1, 1, "Test Event", "test_user"))
    conn.commit()
    conn.close()
    
    print(f"✅ Created test ticket: {test_ticket_id} with 1 seat left")
    
    # Test the scan endpoint - should return valid with is_last_entry flag
    scan_data = {"ticket_id": test_ticket_id}
    response = session.post(f"{BASE_URL}/scan", json=scan_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Scan response: {result}")
        
        if result.get('status') == 'valid' and result.get('is_last_entry'):
            print("✅ Bug fix working: scan correctly identifies last entry")
        else:
            print("❌ Bug fix not working: scan doesn't identify last entry correctly")
            return False
    else:
        print(f"❌ Scan failed: {response.status_code}")
        return False
    
    # Test the checkin endpoint
    checkin_data = {"ticket_id": test_ticket_id, "num_people": 1}
    response = session.post(f"{BASE_URL}/checkin", json=checkin_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Checkin response: {result}")
        
        if result.get('status') == 'success':
            print("✅ Checkin successful")
        else:
            print("❌ Checkin failed")
            return False
    else:
        print(f"❌ Checkin failed: {response.status_code}")
        return False
    
    # Verify the ticket is now fully used
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT seats_left, checked_in FROM tickets WHERE ticket_id = ?", (test_ticket_id,))
    result = c.fetchone()
    conn.close()
    
    if result and result[0] == 0 and result[1] == 2:
        print("✅ Ticket correctly updated: seats_left=0, checked_in=2")
    else:
        print(f"❌ Ticket not updated correctly: {result}")
        return False
    
    # Clean up test data
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM tickets WHERE ticket_id = ?", (test_ticket_id,))
    conn.commit()
    conn.close()
    
    print("✅ Test completed successfully!")
    return True

if __name__ == "__main__":
    try:
        success = test_bug_fix()
        if success:
            print("\n🎉 Bug fix verification completed successfully!")
        else:
            print("\n❌ Bug fix verification failed!")
    except Exception as e:
        print(f"❌ Test failed with error: {e}") 