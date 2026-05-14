# Sales + Procurement CRM System

A comprehensive Flask-based CRM system integrating Sales and Procurement workflows with automated inventory management.

## Features

### Core Modules

1. **Vendor Management**
   - Vendor enrollment and approval workflow
   - Tag vendors with items/services they supply
   - Active/Inactive/Pending status management

2. **Purchase Requisition (PR)**
   - Manual PR creation by departments
   - Auto-generation from sales orders when inventory is insufficient
   - Manager approval workflow

3. **Purchase Order (PO)**
   - Create POs from approved requisitions
   - Link to sales orders for tracking
   - Send POs to vendors (email integration ready)

4. **Goods Receipt Note (GRN)**
   - Record received goods with quality checks
   - Automatic inventory updates
   - Trigger sales order fulfillment when items arrive

5. **Invoice & Payment**
   - Vendor invoice management
   - Verification and approval workflow
   - Payment tracking with reference numbers

6. **Sales Orders**
   - Create customer orders
   - Automatic inventory check
   - Auto-generate PRs for insufficient stock

### Integrated Workflow

```
Sales Order → Inventory Check → Auto PR (if needed) → PO → GRN → 
Inventory Update → Sales Order Ready to Ship → Invoice → Payment
```

## Installation

### Prerequisites

- Python 3.8+
- PostgreSQL or MySQL database
- pip package manager

### Setup Steps

1. **Clone/Download the project**

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure Database**

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and update your database credentials:

For PostgreSQL:
```
DATABASE_URL=postgresql://username:password@localhost:5432/crm_db
```

For MySQL:
```
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/crm_db
```

4. **Create Database**

PostgreSQL:
```bash
createdb crm_db
```

MySQL:
```sql
CREATE DATABASE crm_db;
```

5. **Run the Application**
```bash
python app.py
```

The application will:
- Automatically create all database tables
- Start on http://localhost:5000

## API Documentation

### Authentication

#### Register User
```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password",
  "role": "user",  // user, manager, admin, finance
  "department": "Sales"
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "john_doe",
  "password": "secure_password"
}
```

#### Logout
```http
POST /api/auth/logout
```

### Vendor Management

#### List/Create Vendors
```http
GET /api/vendors
GET /api/vendors?status=active

POST /api/vendors
Content-Type: application/json

{
  "name": "ABC Supplies Ltd",
  "contact_person": "Jane Smith",
  "email": "jane@abcsupplies.com",
  "phone": "+1234567890",
  "address": "123 Business St, City",
  "gst_number": "GST123456",
  "bank_name": "Bank Name",
  "bank_account": "1234567890",
  "ifsc_code": "BANK0001234",
  "items_services": "electronics, office supplies"
}
```

#### Get/Update/Delete Vendor
```http
GET /api/vendors/{vendor_id}
PUT /api/vendors/{vendor_id}
DELETE /api/vendors/{vendor_id}
```

#### Approve Vendor
```http
POST /api/vendors/{vendor_id}/approve
```

### Item Management

#### List/Create Items
```http
GET /api/items

POST /api/items
Content-Type: application/json

{
  "name": "Laptop - Dell XPS 15",
  "description": "15-inch laptop with i7 processor",
  "sku": "LAP-XPS15-001",
  "category": "Electronics",
  "unit": "pcs",
  "current_stock": 10,
  "reorder_level": 5,
  "unit_price": 1200.00
}
```

#### Get/Update Item
```http
GET /api/items/{item_id}
PUT /api/items/{item_id}
```

### Sales Orders

#### Create Sales Order
```http
POST /api/sales/orders
Content-Type: application/json

{
  "customer_name": "Acme Corporation",
  "customer_email": "orders@acme.com",
  "customer_phone": "+1987654321",
  "expected_delivery": "2024-03-15",
  "notes": "Urgent order",
  "items": [
    {
      "item_id": 1,
      "quantity": 5,
      "unit_price": 1200.00
    },
    {
      "item_id": 2,
      "quantity": 10,
      "unit_price": 50.00
    }
  ]
}
```

Response includes auto-generated PRs if inventory is insufficient:
```json
{
  "message": "Sales order created",
  "order_id": 1,
  "order_number": "SO-2024-00001",
  "purchase_requisitions_created": ["PR-2024-00001", "PR-2024-00002"]
}
```

#### List Sales Orders
```http
GET /api/sales/orders
```

#### Get/Update Sales Order
```http
GET /api/sales/orders/{order_id}
PUT /api/sales/orders/{order_id}

{
  "status": "delivered"
}
```

### Purchase Requisitions

#### List/Create PRs
```http
GET /api/procurement/requisitions

POST /api/procurement/requisitions
Content-Type: application/json

{
  "item_id": 1,
  "quantity": 20,
  "expected_delivery": "2024-03-10",
  "estimated_cost": 24000.00,
  "department": "IT",
  "justification": "Stock replenishment for upcoming projects"
}
```

#### Approve/Reject PR
```http
POST /api/procurement/requisitions/{pr_id}/approve
POST /api/procurement/requisitions/{pr_id}/reject
```

### Purchase Orders

#### Create Purchase Order
```http
POST /api/procurement/purchase-orders
Content-Type: application/json

{
  "vendor_id": 1,
  "requisition_id": 1,
  "expected_delivery": "2024-03-10",
  "payment_terms": "Net 30",
  "terms_conditions": "Standard terms apply",
  "items": [
    {
      "item_id": 1,
      "quantity": 20,
      "unit_price": 1200.00
    }
  ]
}
```

#### Send PO to Vendor
```http
POST /api/procurement/purchase-orders/{po_id}/send
```

### Goods Receipt (GRN)

#### Record Goods Receipt
```http
POST /api/procurement/goods-receipt
Content-Type: application/json

{
  "po_id": 1,
  "quality_check": true,
  "quality_notes": "All items in good condition",
  "items": [
    {
      "item_id": 1,
      "quantity_ordered": 20,
      "quantity_received": 20,
      "quantity_accepted": 20,
      "quantity_rejected": 0
    }
  ]
}
```

This will:
- Update inventory with accepted quantities
- Mark PO as completed
- Update linked sales orders to "ready_to_ship" if all items are now available

### Invoices & Payment

#### Create Invoice
```http
POST /api/procurement/invoices
Content-Type: application/json

{
  "invoice_number": "INV-2024-001",
  "vendor_id": 1,
  "po_id": 1,
  "invoice_date": "2024-03-01",
  "due_date": "2024-03-31",
  "amount": 24000.00,
  "tax_amount": 4320.00,
  "total_amount": 28320.00
}
```

#### Invoice Workflow
```http
POST /api/procurement/invoices/{invoice_id}/verify
POST /api/procurement/invoices/{invoice_id}/approve
POST /api/procurement/invoices/{invoice_id}/pay

{
  "payment_reference": "TXN-123456789"
}
```

### Dashboard

#### Get Statistics
```http
GET /api/dashboard/stats
```

Returns:
```json
{
  "total_vendors": 15,
  "pending_requisitions": 3,
  "active_purchase_orders": 5,
  "pending_invoices": 2,
  "active_sales_orders": 8
}
```

## Workflow Examples

### Example 1: Complete Sales-to-Procurement Flow

1. **Create Sales Order** (stock insufficient)
   - System auto-creates PR for shortage
   - Auto-approves PR since it's sales-linked

2. **Create PO from PR**
   ```http
   POST /api/procurement/purchase-orders
   {
     "vendor_id": 1,
     "requisition_id": 1,
     ...
   }
   ```

3. **Send PO**
   ```http
   POST /api/procurement/purchase-orders/1/send
   ```

4. **Record Goods Receipt**
   ```http
   POST /api/procurement/goods-receipt
   {
     "po_id": 1,
     "items": [...]
   }
   ```
   - Inventory updated automatically
   - Sales order status → "ready_to_ship"

5. **Process Invoice**
   ```http
   POST /api/procurement/invoices
   POST /api/procurement/invoices/1/verify
   POST /api/procurement/invoices/1/approve
   POST /api/procurement/invoices/1/pay
   ```

6. **Update Sales Order**
   ```http
   PUT /api/sales/orders/1
   {
     "status": "delivered"
   }
   ```

## User Roles

- **admin**: Full access to all modules
- **manager**: Approve PRs, invoices, vendors
- **user**: Create PRs, view data
- **finance**: Invoice verification and payment approval

## Database Schema

### Key Relationships

- Sales Order → Sales Order Items → Items
- Sales Order → Purchase Requisitions (auto-generated)
- Purchase Requisition → Purchase Order
- Purchase Order → Purchase Order Items → Items
- Purchase Order → Goods Receipt → Inventory Update
- Purchase Order → Invoice → Payment

## Security

- Password hashing using Werkzeug
- Role-based access control
- Login required for all API endpoints
- Session management with Flask-Login

## Customization

### Adding Custom Fields

Edit `models.py` to add new fields to any model:

```python
class Vendor(db.Model):
    # ... existing fields ...
    custom_field = db.Column(db.String(100))
```

Then migrate:
```bash
# Drop and recreate (development only)
# Or use Flask-Migrate for production
```

### Email Integration

Add email configuration in `routes.py`:

```python
from flask_mail import Mail, Message

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
# ... configure mail

@app.route('/api/procurement/purchase-orders/<int:po_id>/send', methods=['POST'])
def send_purchase_order(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    # Send email to vendor
    msg = Message('Purchase Order', recipients=[po.vendor.email])
    # ... attach PO PDF
    mail.send(msg)
```

## Troubleshooting

### Database Connection Issues

- Verify database credentials in `.env`
- Ensure database server is running
- Check firewall settings

### Import Errors

- Circular imports: Ensure `models.py` and `routes.py` import from `app.py`
- Missing dependencies: Run `pip install -r requirements.txt`

## Production Deployment

### Security Checklist

1. Change `SECRET_KEY` to a random string
2. Set `FLASK_ENV=production`
3. Use a production-grade WSGI server (gunicorn, uWSGI)
4. Enable HTTPS
5. Set up proper database backups
6. Configure environment-specific database URLs

### Example with Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Future Enhancements

- [ ] PDF generation for POs and invoices
- [ ] Email notifications
- [ ] Advanced reporting and analytics
- [ ] Document attachments
- [ ] Multi-currency support
- [ ] Approval workflow customization
- [ ] REST API rate limiting
- [ ] GraphQL API option

## License

MIT License

## Support

For issues or questions, please create an issue in the repository.
