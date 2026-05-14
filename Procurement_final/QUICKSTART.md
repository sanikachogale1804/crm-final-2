# Quick Start Guide

Get your Sales + Procurement CRM running in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- PostgreSQL or MySQL database server

## Step-by-Step Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Database

**Option A: PostgreSQL (Recommended)**

Create database:
```bash
createdb crm_db
```

Copy environment file:
```bash
cp .env.example .env
```

Edit `.env` and set:
```
DATABASE_URL=postgresql://your_username:your_password@localhost:5432/crm_db
SECRET_KEY=your-random-secret-key-here
```

**Option B: MySQL**

Create database:
```sql
CREATE DATABASE crm_db;
```

Edit `.env` and set:
```
DATABASE_URL=mysql+pymysql://your_username:your_password@localhost:3306/crm_db
SECRET_KEY=your-random-secret-key-here
```

### 3. Initialize Database with Sample Data

```bash
python init_db.py sample
```

This creates:
- Database tables
- 4 test users (admin, manager, user, finance)
- 3 vendors
- 5 items
- 1 sales order with auto-generated purchase requisition

### 4. Start the Application

```bash
python app.py
```

The API will be available at: `http://localhost:5000`

## Test the API

### Using curl

**Login:**
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

**Get Dashboard Stats:**
```bash
curl http://localhost:5000/api/dashboard/stats \
  --cookie-jar cookies.txt \
  --cookie cookies.txt
```

### Using Postman

1. Import `postman_collection.json` into Postman
2. Set `base_url` variable to `http://localhost:5000`
3. Login using the "Authentication → Login" request
4. Test other endpoints!

## Test Credentials

```
Admin:    username: admin    password: admin123
Manager:  username: manager  password: manager123
User:     username: user     password: user123
Finance:  username: finance  password: finance123
```

## Common Workflows

### Create a Sales Order

```bash
curl -X POST http://localhost:5000/api/sales/orders \
  -H "Content-Type: application/json" \
  --cookie cookies.txt \
  -d '{
    "customer_name": "Test Customer",
    "customer_email": "test@customer.com",
    "expected_delivery": "2024-04-15",
    "items": [
      {
        "item_id": 1,
        "quantity": 10,
        "unit_price": 1299.99
      }
    ]
  }'
```

If stock is insufficient, Purchase Requisitions are auto-created!

### Approve a Purchase Requisition

```bash
curl -X POST http://localhost:5000/api/procurement/requisitions/1/approve \
  --cookie cookies.txt
```

### Create Purchase Order

```bash
curl -X POST http://localhost:5000/api/procurement/purchase-orders \
  -H "Content-Type: application/json" \
  --cookie cookies.txt \
  -d '{
    "vendor_id": 1,
    "requisition_id": 1,
    "expected_delivery": "2024-04-01",
    "payment_terms": "Net 30",
    "items": [
      {
        "item_id": 1,
        "quantity": 15,
        "unit_price": 1299.99
      }
    ]
  }'
```

## Troubleshooting

### "Connection refused" errors
- Make sure PostgreSQL/MySQL is running
- Check database credentials in `.env`

### "Module not found" errors
- Run `pip install -r requirements.txt` again
- Ensure you're using Python 3.8+

### "Table doesn't exist" errors
- Run `python init_db.py sample` to create tables

### Need to reset everything?
```bash
python init_db.py reset
python init_db.py sample
```

## Next Steps

- Read the [full README](README.md) for complete API documentation
- Check the [models.py](models.py) file to understand the data structure
- Explore [routes.py](routes.py) to see the business logic
- Customize the system for your needs!

## Support

If you encounter issues:
1. Check the terminal output for error messages
2. Verify database connection
3. Ensure all dependencies are installed
4. Review the README for detailed documentation

Happy coding! 🚀
