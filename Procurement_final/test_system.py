"""
Simple test script to verify the CRM system is working
"""

import requests
import json
from time import sleep

BASE_URL = "http://localhost:5000"

def test_connection():
    """Test if the server is running"""
    try:
        response = requests.get(BASE_URL)
        if response.status_code == 200:
            print("✓ Server is running")
            return True
        else:
            print("✗ Server responded with status:", response.status_code)
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Is it running?")
        print("  Start the server with: python app.py")
        return False

def test_login():
    """Test login functionality"""
    print("\nTesting login...")
    
    session = requests.Session()
    
    # Try to login
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        print("✓ Login successful")
        return session
    else:
        print("✗ Login failed:", response.text)
        return None

def test_dashboard(session):
    """Test dashboard stats endpoint"""
    print("\nTesting dashboard stats...")
    
    response = session.get(f"{BASE_URL}/api/dashboard/stats")
    
    if response.status_code == 200:
        data = response.json()
        print("✓ Dashboard stats retrieved:")
        print(f"  - Active vendors: {data.get('total_vendors', 0)}")
        print(f"  - Pending requisitions: {data.get('pending_requisitions', 0)}")
        print(f"  - Active purchase orders: {data.get('active_purchase_orders', 0)}")
        print(f"  - Active sales orders: {data.get('active_sales_orders', 0)}")
        return True
    else:
        print("✗ Failed to get dashboard stats:", response.text)
        return False

def test_vendors(session):
    """Test vendor listing"""
    print("\nTesting vendor list...")
    
    response = session.get(f"{BASE_URL}/api/vendors")
    
    if response.status_code == 200:
        vendors = response.json()
        print(f"✓ Found {len(vendors)} vendors")
        if vendors:
            print(f"  First vendor: {vendors[0].get('name', 'Unknown')}")
        return True
    else:
        print("✗ Failed to get vendors:", response.text)
        return False

def test_items(session):
    """Test item listing"""
    print("\nTesting item list...")
    
    response = session.get(f"{BASE_URL}/api/items")
    
    if response.status_code == 200:
        items = response.json()
        print(f"✓ Found {len(items)} items")
        if items:
            item = items[0]
            print(f"  First item: {item.get('name', 'Unknown')} (Stock: {item.get('current_stock', 0)})")
        return True
    else:
        print("✗ Failed to get items:", response.text)
        return False

def main():
    print("="*60)
    print("Sales + Procurement CRM - System Test")
    print("="*60)
    
    # Test connection
    if not test_connection():
        return
    
    sleep(1)
    
    # Test login
    session = test_login()
    if not session:
        print("\n✗ Tests failed: Cannot login")
        print("  Make sure you ran: python init_db.py sample")
        return
    
    sleep(0.5)
    
    # Run tests
    tests = [
        test_dashboard(session),
        test_vendors(session),
        test_items(session)
    ]
    
    # Summary
    print("\n" + "="*60)
    passed = sum(tests)
    total = len(tests) + 1  # +1 for login
    
    if passed == total - 1:
        print(f"✓ All tests passed! ({passed}/{total-1})")
        print("\nYour CRM system is working correctly!")
        print("Next steps:")
        print("  - Import postman_collection.json into Postman")
        print("  - Read the README.md for full API documentation")
        print("  - Start building your custom features!")
    else:
        print(f"✗ Some tests failed ({passed}/{total-1} passed)")
        print("\nTroubleshooting:")
        print("  - Check if database is configured correctly")
        print("  - Verify you ran: python init_db.py sample")
        print("  - Look for errors in the server console")
    
    print("="*60)

if __name__ == "__main__":
    main()
