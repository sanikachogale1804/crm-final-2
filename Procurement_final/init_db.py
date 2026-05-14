"""
Database initialization script
Creates tables and optionally adds sample data
"""

from app import app, db
from models import *
from datetime import datetime, timedelta

def init_db():
    """Initialize database tables"""
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Database tables created successfully!")

def create_sample_data():
    """Create sample data for testing"""
    with app.app_context():
        print("\nCreating sample data...")
        
        # Create users
        admin = User(username='admin', email='admin@crm.com', role='admin', department='Management')
        admin.set_password('admin123')
        
        manager = User(username='manager', email='manager@crm.com', role='manager', department='Procurement')
        manager.set_password('manager123')
        
        user = User(username='user', email='user@crm.com', role='user', department='Sales')
        user.set_password('user123')
        
        finance = User(username='finance', email='finance@crm.com', role='finance', department='Finance')
        finance.set_password('finance123')
        
        db.session.add_all([admin, manager, user, finance])
        db.session.commit()
        print("✓ Created 4 users (admin, manager, user, finance)")
        
        # Create vendors
        vendors_data = [
            {
                'name': 'Tech Solutions Inc',
                'contact_person': 'John Smith',
                'email': 'john@techsolutions.com',
                'phone': '+1-555-0101',
                'address': '123 Tech Street, Silicon Valley, CA 94025',
                'gst_number': 'GST-TECH-001',
                'items_services': 'laptops, computers, electronics',
                'status': VendorStatus.ACTIVE.value
            },
            {
                'name': 'Office Supplies Co',
                'contact_person': 'Mary Johnson',
                'email': 'mary@officesupplies.com',
                'phone': '+1-555-0102',
                'address': '456 Business Ave, New York, NY 10001',
                'gst_number': 'GST-OFF-002',
                'items_services': 'office supplies, furniture, stationery',
                'status': VendorStatus.ACTIVE.value
            },
            {
                'name': 'Industrial Equipment Ltd',
                'contact_person': 'Robert Brown',
                'email': 'robert@industrial.com',
                'phone': '+1-555-0103',
                'address': '789 Industry Rd, Detroit, MI 48201',
                'gst_number': 'GST-IND-003',
                'items_services': 'machinery, tools, equipment',
                'status': VendorStatus.PENDING.value
            }
        ]
        
        for vd in vendors_data:
            vendor = Vendor(**vd)
            db.session.add(vendor)
        
        db.session.commit()
        print("✓ Created 3 vendors")
        
        # Create items
        items_data = [
            {
                'name': 'Dell XPS 15 Laptop',
                'description': '15.6" FHD, Intel i7, 16GB RAM, 512GB SSD',
                'sku': 'LAP-DELL-XPS15',
                'category': 'Electronics',
                'unit': 'pcs',
                'current_stock': 15,
                'reorder_level': 5,
                'unit_price': 1299.99
            },
            {
                'name': 'HP LaserJet Printer',
                'description': 'Monochrome laser printer, network-ready',
                'sku': 'PRT-HP-LJ200',
                'category': 'Electronics',
                'unit': 'pcs',
                'current_stock': 8,
                'reorder_level': 3,
                'unit_price': 399.99
            },
            {
                'name': 'Office Chair - Ergonomic',
                'description': 'Adjustable height, lumbar support',
                'sku': 'FUR-CHR-ERG01',
                'category': 'Furniture',
                'unit': 'pcs',
                'current_stock': 25,
                'reorder_level': 10,
                'unit_price': 249.99
            },
            {
                'name': 'A4 Paper - Box of 5 Reams',
                'description': '80 GSM white paper, 500 sheets per ream',
                'sku': 'STA-PPR-A4-5R',
                'category': 'Stationery',
                'unit': 'box',
                'current_stock': 50,
                'reorder_level': 20,
                'unit_price': 24.99
            },
            {
                'name': 'USB-C Docking Station',
                'description': 'Multi-port hub with HDMI, USB 3.0, Ethernet',
                'sku': 'ELC-DOCK-USBC',
                'category': 'Electronics',
                'unit': 'pcs',
                'current_stock': 3,  # Low stock
                'reorder_level': 5,
                'unit_price': 89.99
            }
        ]
        
        for id in items_data:
            item = Item(**id)
            db.session.add(item)
        
        db.session.commit()
        print("✓ Created 5 items")
        
        # Create a sample sales order
        sales_order = SalesOrder(
            order_number='SO-2024-00001',
            customer_name='Acme Corporation',
            customer_email='orders@acme.com',
            customer_phone='+1-555-1234',
            expected_delivery=datetime.now().date() + timedelta(days=7),
            notes='Urgent order for new office setup',
            created_by=user.id,
            status=SalesOrderStatus.CONFIRMED.value
        )
        db.session.add(sales_order)
        db.session.flush()
        
        # Add items to sales order (some with insufficient stock)
        so_items_data = [
            {'item_id': 1, 'quantity': 10, 'unit_price': 1299.99},  # Dell laptops
            {'item_id': 5, 'quantity': 10, 'unit_price': 89.99},    # USB-C docks - insufficient stock!
        ]
        
        total_amount = 0
        for sid in so_items_data:
            so_item = SalesOrderItem(
                sales_order_id=sales_order.id,
                item_id=sid['item_id'],
                quantity=sid['quantity'],
                unit_price=sid['unit_price'],
                total_price=sid['quantity'] * sid['unit_price']
            )
            db.session.add(so_item)
            total_amount += so_item.total_price
        
        sales_order.total_amount = total_amount
        db.session.commit()
        print("✓ Created 1 sales order with 2 items")
        
        # Create auto-generated PR for insufficient stock (USB-C docks)
        pr = PurchaseRequisition(
            pr_number='PR-2024-00001',
            item_id=5,  # USB-C docks
            quantity=7,  # Need 7 more (10 ordered - 3 in stock)
            expected_delivery=datetime.now().date() + timedelta(days=5),
            estimated_cost=7 * 89.99,
            status=PRStatus.APPROVED.value,
            requested_by=user.id,
            department='Sales',
            justification='Auto-generated from sales order SO-2024-00001',
            sales_order_id=sales_order.id,
            auto_generated=True,
            approved_by=manager.id,
            approval_date=datetime.utcnow()
        )
        db.session.add(pr)
        db.session.commit()
        print("✓ Created 1 auto-generated purchase requisition")
        
        print("\n" + "="*60)
        print("Sample data created successfully!")
        print("="*60)
        print("\nTest Credentials:")
        print("-" * 60)
        print("Admin:    username: admin    password: admin123")
        print("Manager:  username: manager  password: manager123")
        print("User:     username: user     password: user123")
        print("Finance:  username: finance  password: finance123")
        print("-" * 60)
        print("\nNext Steps:")
        print("1. Start the application: python app.py")
        print("2. Test the API endpoints using the credentials above")
        print("3. Check the README.md for API documentation")
        print("="*60)

def reset_db():
    """Drop all tables and recreate"""
    with app.app_context():
        print("WARNING: This will delete all data!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            print("Dropping all tables...")
            db.drop_all()
            print("✓ Tables dropped")
            init_db()
        else:
            print("Operation cancelled")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'reset':
            reset_db()
        elif sys.argv[1] == 'sample':
            init_db()
            create_sample_data()
    else:
        print("Database Initialization Script")
        print("-" * 60)
        print("Usage:")
        print("  python init_db.py          - Show this help")
        print("  python init_db.py reset    - Drop and recreate tables")
        print("  python init_db.py sample   - Create tables + sample data")
        print("-" * 60)
