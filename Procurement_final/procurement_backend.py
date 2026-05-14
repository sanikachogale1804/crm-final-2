"""
Procurement CRM Backend — FastAPI + SQLite
Run:  pip install fastapi uvicorn aiosqlite --break-system-packages
      python procurement_backend.py
Listens on: http://localhost:5001
"""

import sqlite3, json, os, base64, uuid
from datetime import datetime, date
from typing import Optional, List
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Procurement CRM API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "procurement.db"
QUOTES_DIR = Path("uploads/quotes")
QUOTES_DIR.mkdir(parents=True, exist_ok=True)

# ─── DB Helpers ───────────────────────────────────────────────────────────────
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows] if rows else []

# ─── DB Init ──────────────────────────────────────────────────────────────────
def init_db():
    with get_db() as conn:
        c = conn.cursor()

        # ── Vendors ──
        c.execute("""
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            gst_number TEXT,
            bank_name TEXT,
            bank_account TEXT,
            ifsc_code TEXT,
            items_services TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS vendor_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            stage TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            approved_by TEXT,
            comments TEXT,
            approved_at DATETIME,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        )""")

        # ── Items ──
        c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT,
            category TEXT,
            unit TEXT DEFAULT 'pcs',
            unit_price REAL DEFAULT 0,
            current_stock REAL DEFAULT 0,
            reorder_level REAL DEFAULT 0,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

        # ── Sales Orders ──
        c.execute("""
        CREATE TABLE IF NOT EXISTS sales_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT,
            customer_phone TEXT,
            expected_delivery DATE,
            notes TEXT,
            total_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'confirmed',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS sales_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sales_order_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            total REAL,
            FOREIGN KEY (sales_order_id) REFERENCES sales_orders(id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        )""")

        # ── Purchase Requisitions ──
        c.execute("""
        CREATE TABLE IF NOT EXISTS purchase_requisitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_number TEXT UNIQUE NOT NULL,
            item_id INTEGER,
            item_name TEXT,
            quantity REAL NOT NULL,
            estimated_cost REAL,
            expected_delivery DATE,
            justification TEXT,
            requested_by TEXT DEFAULT 'System',
            sales_order TEXT,
            auto_generated INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS pr_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_id INTEGER NOT NULL,
            vendor_name TEXT NOT NULL,
            quote_number TEXT,
            amount REAL,
            notes TEXT,
            pdf_filename TEXT,
            has_pdf INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pr_id) REFERENCES purchase_requisitions(id)
        )""")

        # ── Purchase Orders ──
        c.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT UNIQUE NOT NULL,
            vendor_id INTEGER NOT NULL,
            requisition_id INTEGER,
            order_date DATE DEFAULT CURRENT_DATE,
            expected_delivery DATE,
            payment_terms TEXT,
            terms_conditions TEXT,
            total_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'draft',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id),
            FOREIGN KEY (requisition_id) REFERENCES purchase_requisitions(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS po_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            total REAL,
            FOREIGN KEY (po_id) REFERENCES purchase_orders(id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        )""")

        # ── Goods Receipt ──
        c.execute("""
        CREATE TABLE IF NOT EXISTS goods_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grn_number TEXT UNIQUE NOT NULL,
            po_id INTEGER NOT NULL,
            po_number TEXT,
            receipt_date DATE DEFAULT CURRENT_DATE,
            quality_check INTEGER DEFAULT 1,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (po_id) REFERENCES purchase_orders(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS grn_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grn_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity_ordered REAL,
            quantity_received REAL,
            quantity_accepted REAL,
            quantity_rejected REAL DEFAULT 0,
            FOREIGN KEY (grn_id) REFERENCES goods_receipts(id)
        )""")

        # ── Invoices ──
        c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            vendor_id INTEGER NOT NULL,
            po_id INTEGER,
            invoice_date DATE,
            due_date DATE,
            amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            notes TEXT,
            status TEXT DEFAULT 'pending',
            payment_reference TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id),
            FOREIGN KEY (po_id) REFERENCES purchase_orders(id)
        )""")

        # ══════════════════════════════════════════════
        #   OEM TABLES
        # ══════════════════════════════════════════════
        c.execute("""
        CREATE TABLE IF NOT EXISTS oems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oem_company_name TEXT NOT NULL,
            category TEXT,
            country TEXT,
            website TEXT,
            registered_address TEXT,
            primary_contact_name TEXT,
            designation TEXT,
            mobile TEXT,
            email TEXT,
            secondary_contact TEXT,
            support_email TEXT,
            support_phone TEXT,
            status TEXT DEFAULT 'Pending',
            strategic_priority TEXT DEFAULT 'Medium',
            noc_for_marketing INTEGER DEFAULT 0,
            agreement_type TEXT,
            agreement_signed_date DATE,
            agreement_expiry_date DATE,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS oem_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oem_id INTEGER NOT NULL,
            product_category TEXT,
            brand TEXT,
            model_number TEXT,
            series_make TEXT,
            hsn_code TEXT,
            serial_number_format TEXT,
            compliance TEXT,
            warranty_period TEXT,
            warranty_type TEXT,
            amc_available INTEGER DEFAULT 0,
            datasheet_available INTEGER DEFAULT 0,
            hd_images_available INTEGER DEFAULT 0,
            product_description TEXT,
            key_features TEXT,
            technical_specifications TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (oem_id) REFERENCES oems(id) ON DELETE CASCADE
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS oem_product_pricing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            price_product TEXT,
            oem_price REAL,
            distributor_price REAL,
            reseller_price REAL,
            suggested_mrp REAL,
            standard_margin_pct REAL,
            currency TEXT DEFAULT 'INR',
            moq INTEGER DEFAULT 1,
            lead_time_days INTEGER,
            payment_terms TEXT,
            warehouse_location TEXT,
            supply_type TEXT DEFAULT 'direct',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES oem_products(id) ON DELETE CASCADE
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS oem_agreements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oem_id INTEGER NOT NULL,
            agreement_type TEXT,
            signed_date DATE,
            expiry_date DATE,
            renewal_reminder_date DATE,
            agreement_document_location TEXT,
            legal_contact TEXT,
            status TEXT DEFAULT 'Active',
            remarks TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (oem_id) REFERENCES oems(id) ON DELETE CASCADE
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS oem_product_marketing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            marketing_collateral_available INTEGER DEFAULT 0,
            website_listed INTEGER DEFAULT 0,
            brochure_included INTEGER DEFAULT 0,
            social_media_ready INTEGER DEFAULT 0,
            demo_unit_available INTEGER DEFAULT 0,
            sample_unit_cost REAL,
            product_images_link TEXT,
            datasheet_link TEXT,
            case_study_link TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES oem_products(id) ON DELETE CASCADE
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS oem_trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oem_id INTEGER NOT NULL,
            ceo_meeting_done INTEGER DEFAULT 0,
            meeting_date DATE,
            sales_training_conducted INTEGER DEFAULT 0,
            training_date DATE,
            trainer_name TEXT,
            presales_support_contact TEXT,
            demo_availability TEXT,
            next_training_due DATE,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (oem_id) REFERENCES oems(id) ON DELETE CASCADE
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS oem_product_tender (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            psu_govt_approved INTEGER DEFAULT 0,
            stqc_status TEXT,
            tender_eligible INTEGER DEFAULT 0,
            ndaa_compliance INTEGER DEFAULT 0,
            used_in_psu_projects INTEGER DEFAULT 0,
            security_certifications TEXT,
            past_project_references TEXT,
            remarks TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES oem_products(id) ON DELETE CASCADE
        )""")

        conn.commit()
        print("✅ Database initialized successfully!")

# ─────────────────────────────────────────────────────────────────────────────
#   UTILITY
# ─────────────────────────────────────────────────────────────────────────────
def next_number(conn, table, column, prefix):
    # COUNT ke bajaye MAX use karo — deletions se affect nahi hoga
    row = conn.execute(
        f"SELECT {column} FROM {table} WHERE {column} LIKE ? ORDER BY {column} DESC LIMIT 1",
        (f"{prefix}-%",)
    ).fetchone()
    if row and row[0]:
        try:
            last_num = int(row[0].split("-")[-1])
        except (ValueError, IndexError):
            last_num = 0
    else:
        last_num = 0
    return f"{prefix}-{str(last_num + 1).zfill(5)}"

# ─────────────────────────────────────────────────────────────────────────────
#   DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/dashboard/stats")
def dashboard_stats():
    with get_db() as conn:
        def count(q): return conn.execute(q).fetchone()[0] or 0
        return {
            "total_vendors":           count("SELECT COUNT(*) FROM vendors WHERE status='active'"),
            "active_sales_orders":     count("SELECT COUNT(*) FROM sales_orders WHERE status NOT IN ('delivered','cancelled')"),
            "pending_requisitions":    count("SELECT COUNT(*) FROM purchase_requisitions WHERE status='pending'"),
            "active_purchase_orders":  count("SELECT COUNT(*) FROM purchase_orders WHERE status NOT IN ('completed','cancelled')"),
            "pending_invoices":        count("SELECT COUNT(*) FROM invoices WHERE status='pending'"),
        }

# ─────────────────────────────────────────────────────────────────────────────
#   VENDORS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/vendors")
def list_vendors():
    with get_db() as conn:
        return rows_to_list(conn.execute("SELECT * FROM vendors ORDER BY created_at DESC").fetchall())

@app.post("/api/vendors")
def create_vendor(data: dict = Body(...)):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO vendors (name,contact_person,email,phone,address,gst_number,
                     bank_name,bank_account,ifsc_code,items_services,status)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (data.get("name"), data.get("contact_person"), data.get("email"),
                   data.get("phone"), data.get("address"), data.get("gst_number"),
                   data.get("bank_name"), data.get("bank_account"), data.get("ifsc_code"),
                   data.get("items_services"), "pending"))
        return {"id": c.lastrowid, "message": "Vendor created"}

@app.put("/api/vendors/{vendor_id}")
def update_vendor(vendor_id: int, data: dict = Body(...)):
    with get_db() as conn:
        fields = ", ".join(f"{k}=?" for k in data)
        conn.execute(f"UPDATE vendors SET {fields}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                     (*data.values(), vendor_id))
        return {"message": "Updated"}

@app.get("/api/vendors/{vendor_id}/approvals")
def get_vendor_approvals(vendor_id: int):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM vendor_approvals WHERE vendor_id=?", (vendor_id,)).fetchall()
        return {"approvals": rows_to_list(rows)}

@app.post("/api/vendors/{vendor_id}/approve-stage")
def approve_vendor_stage(vendor_id: int, data: dict = Body(...)):
    stage   = data.get("stage")
    action  = data.get("action")          # "approve" or "reject"
    comment = data.get("comments", "")
    by      = data.get("approved_by", "Admin")
    status  = "approved" if action == "approve" else "rejected"

    with get_db() as conn:
        # Upsert approval record
        existing = conn.execute("SELECT id FROM vendor_approvals WHERE vendor_id=? AND stage=?",
                                (vendor_id, stage)).fetchone()
        if existing:
            conn.execute("UPDATE vendor_approvals SET status=?,approved_by=?,comments=?,approved_at=CURRENT_TIMESTAMP WHERE id=?",
                         (status, by, comment, existing["id"]))
        else:
            conn.execute("INSERT INTO vendor_approvals (vendor_id,stage,status,approved_by,comments,approved_at) VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                         (vendor_id, stage, status, by, comment))

        if action == "reject":
            conn.execute("UPDATE vendors SET status='rejected', updated_at=CURRENT_TIMESTAMP WHERE id=?", (vendor_id,))
        else:
            # Check if all 3 stages approved
            approved = conn.execute(
                "SELECT COUNT(*) FROM vendor_approvals WHERE vendor_id=? AND status='approved'",
                (vendor_id,)).fetchone()[0]
            if approved >= 3:
                conn.execute("UPDATE vendors SET status='active', updated_at=CURRENT_TIMESTAMP WHERE id=?", (vendor_id,))
        return {"message": f"Stage {stage} {status}"}

# ─────────────────────────────────────────────────────────────────────────────
#   ITEMS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/items")
def list_items():
    with get_db() as conn:
        return rows_to_list(conn.execute("SELECT * FROM items ORDER BY name").fetchall())

@app.post("/api/items")
def create_item(data: dict = Body(...)):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO items (name,sku,category,unit,unit_price,current_stock,reorder_level,description)
                     VALUES (?,?,?,?,?,?,?,?)""",
                  (data.get("name"), data.get("sku"), data.get("category"), data.get("unit","pcs"),
                   data.get("unit_price",0), data.get("current_stock",0),
                   data.get("reorder_level",0), data.get("description")))
        return {"id": c.lastrowid, "message": "Item created"}

# ─────────────────────────────────────────────────────────────────────────────
#   SALES ORDERS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/sales/orders")
def list_sales_orders():
    with get_db() as conn:
        return rows_to_list(conn.execute("SELECT * FROM sales_orders ORDER BY created_at DESC").fetchall())

@app.get("/api/sales/orders/{order_id}")
def get_sales_order(order_id: int):
    with get_db() as conn:
        order = row_to_dict(conn.execute("SELECT * FROM sales_orders WHERE id=?", (order_id,)).fetchone())
        if not order:
            raise HTTPException(404, "Order not found")
        items = rows_to_list(conn.execute(
            "SELECT soi.*, i.name as item_name FROM sales_order_items soi JOIN items i ON soi.item_id=i.id WHERE soi.sales_order_id=?",
            (order_id,)).fetchall())
        order["items"] = items
        return order

@app.post("/api/sales/orders")
def create_sales_order(data: dict = Body(...)):
    with get_db() as conn:
        c = conn.cursor()
        order_num = next_number(conn, "sales_orders", "order_number", "SO")
        items = data.get("items", [])

        so_id_temp = None
        total = 0
        prs_created = []

        c.execute("""INSERT INTO sales_orders (order_number,customer_name,customer_email,customer_phone,
                     expected_delivery,notes,total_amount,status)
                     VALUES (?,?,?,?,?,?,?,'confirmed')""",
                  (order_num, data["customer_name"], data.get("customer_email"),
                   data.get("customer_phone"), data.get("expected_delivery"),
                   data.get("notes"), 0))
        so_id = c.lastrowid

        for item in items:
            # ── Step 1: item_id se dhundho ──
            item_id   = item.get("item_id")
            item_row  = None

            if item_id:
                item_row = conn.execute(
                    "SELECT * FROM items WHERE id=?", (item_id,)
                ).fetchone()

            # ── Step 2: item_name se dhundho (CRM se aata hai) ──
            if not item_row and item.get("item_name"):
                item_row = conn.execute(
                    "SELECT * FROM items WHERE LOWER(name)=LOWER(?)",
                    (item.get("item_name","").strip(),)
                ).fetchone()

            # ── Step 3: item nahi mila toh auto-create ──
            if not item_row:
                item_name = item.get("item_name") or f"Item-{item_id or 'Unknown'}"
                print(f"⚠️ Auto-creating item: {item_name}")
                c.execute("""INSERT INTO items (name,unit,unit_price,current_stock,reorder_level)
                             VALUES (?,?,?,?,?)""",
                          (item_name, "pcs",
                           item.get("unit_price", 0), 0, 0))
                item_id  = c.lastrowid
                # Re-fetch
                item_row = conn.execute(
                    "SELECT * FROM items WHERE id=?", (item_id,)
                ).fetchone()
            else:
                item_id = item_row["id"]

            quantity   = int(item.get("quantity") or 1)
            unit_price = float(item.get("unit_price") or item_row["unit_price"] or 0)
            item_total = quantity * unit_price
            total     += item_total

            c.execute("""INSERT INTO sales_order_items
                         (sales_order_id,item_id,quantity,unit_price,total)
                         VALUES (?,?,?,?,?)""",
                      (so_id, item_id, quantity, unit_price, item_total))

            # ── Stock check → auto PR ──
            current_stock = item_row["current_stock"] if item_row else 0
            if current_stock < quantity:
                pr_num = next_number(conn, "purchase_requisitions", "pr_number", "PR")
                shortage = quantity - current_stock
                c.execute("""INSERT INTO purchase_requisitions
                             (pr_number,item_id,item_name,quantity,requested_by,
                              sales_order,auto_generated,status)
                             VALUES (?,?,?,?,'System',?,1,'pending')""",
                          (pr_num, item_id,
                           item_row["name"] if item_row else item.get("item_name",""),
                           shortage, order_num))
                prs_created.append(pr_num)
                print(f"📋 Auto PR created: {pr_num} for shortage {shortage}")

        # Total update karo
        conn.execute(
            "UPDATE sales_orders SET total_amount=? WHERE id=?",
            (total, so_id)
        )

        return {
            "order_number": order_num,
            "id": so_id,
            "total_amount": total,
            "purchase_requisitions_created": prs_created
        }
    
@app.put("/api/sales/orders/{order_id}")
def update_sales_order(order_id: int, data: dict = Body(...)):
    with get_db() as conn:
        conn.execute("UPDATE sales_orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                     (data.get("status"), order_id))
        return {"message": "Updated"}

# ─────────────────────────────────────────────────────────────────────────────
#   PURCHASE REQUISITIONS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/procurement/requisitions")
def list_prs():
    with get_db() as conn:
        return rows_to_list(conn.execute("SELECT * FROM purchase_requisitions ORDER BY created_at DESC").fetchall())

@app.post("/api/procurement/requisitions")
def create_pr(data: dict = Body(...)):
    with get_db() as conn:
        c = conn.cursor()
        pr_num = next_number(conn, "purchase_requisitions", "pr_number", "PR")
        item_name = ""
        if data.get("item_id"):
            row = conn.execute("SELECT name FROM items WHERE id=?", (data["item_id"],)).fetchone()
            item_name = row["name"] if row else ""
        c.execute("""INSERT INTO purchase_requisitions
                     (pr_number,item_id,item_name,quantity,estimated_cost,expected_delivery,justification,requested_by,status)
                     VALUES (?,?,?,?,?,?,?,'Manual','pending')""",
                  (pr_num, data.get("item_id"), item_name, data["quantity"],
                   data.get("estimated_cost"), data.get("expected_delivery"), data.get("justification")))
        return {"id": c.lastrowid, "pr_number": pr_num}

@app.post("/api/procurement/requisitions/{pr_id}/approve-with-check")
def approve_pr(pr_id: int):
    with get_db() as conn:
        qcount = conn.execute("SELECT COUNT(*) FROM pr_quotes WHERE pr_id=?", (pr_id,)).fetchone()[0]
        if qcount < 3:
            raise HTTPException(400, f"Only {qcount}/3 quotes uploaded. Upload all 3 first.")
        conn.execute("UPDATE purchase_requisitions SET status='approved', updated_at=CURRENT_TIMESTAMP WHERE id=?", (pr_id,))
        return {"message": "Approved"}

@app.post("/api/procurement/requisitions/{pr_id}/reject")
def reject_pr(pr_id: int):
    with get_db() as conn:
        conn.execute("UPDATE purchase_requisitions SET status='rejected', updated_at=CURRENT_TIMESTAMP WHERE id=?", (pr_id,))
        return {"message": "Rejected"}

# ── PR Quotes ──────────────────────────────────────────────────────────────
@app.get("/api/procurement/requisitions/{pr_id}/quotes")
def list_quotes(pr_id: int):
    with get_db() as conn:
        return rows_to_list(conn.execute("SELECT * FROM pr_quotes WHERE pr_id=? ORDER BY created_at", (pr_id,)).fetchall())

@app.post("/api/procurement/requisitions/{pr_id}/quotes")
def upload_quote(pr_id: int, data: dict = Body(...)):
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM pr_quotes WHERE pr_id=?", (pr_id,)).fetchone()[0]
        if count >= 3:
            raise HTTPException(400, "Maximum 3 quotes allowed")
        pdf_filename = None
        has_pdf = 0
        if data.get("pdf_data"):
            pdf_filename = f"{uuid.uuid4().hex}.pdf"
            pdf_path = QUOTES_DIR / pdf_filename
            with open(pdf_path, "wb") as f:
                f.write(base64.b64decode(data["pdf_data"]))
            has_pdf = 1
        c = conn.cursor()
        c.execute("""INSERT INTO pr_quotes (pr_id,vendor_name,quote_number,amount,notes,pdf_filename,has_pdf)
                     VALUES (?,?,?,?,?,?,?)""",
                  (pr_id, data["vendor_name"], data.get("quote_number"), data.get("amount"),
                   data.get("notes"), pdf_filename, has_pdf))
        return {"id": c.lastrowid, "message": "Quote uploaded"}

@app.get("/api/procurement/requisitions/{pr_id}/quotes/{quote_id}/pdf")
def download_quote_pdf(pr_id: int, quote_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM pr_quotes WHERE id=? AND pr_id=?", (quote_id, pr_id)).fetchone()
        if not row or not row["pdf_filename"]:
            raise HTTPException(404, "PDF not found")
        path = QUOTES_DIR / row["pdf_filename"]
        if not path.exists():
            raise HTTPException(404, "File not found on disk")
        return FileResponse(str(path), media_type="application/pdf", filename=row["pdf_filename"])

@app.delete("/api/procurement/requisitions/{pr_id}/quotes/{quote_id}")
def delete_quote(pr_id: int, quote_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT pdf_filename FROM pr_quotes WHERE id=? AND pr_id=?", (quote_id, pr_id)).fetchone()
        if row and row["pdf_filename"]:
            p = QUOTES_DIR / row["pdf_filename"]
            if p.exists(): p.unlink()
        conn.execute("DELETE FROM pr_quotes WHERE id=? AND pr_id=?", (quote_id, pr_id))
        return {"message": "Deleted"}

# ─────────────────────────────────────────────────────────────────────────────
#   PURCHASE ORDERS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/procurement/purchase-orders")
def list_pos():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT po.*, v.name as vendor_name
            FROM purchase_orders po
            LEFT JOIN vendors v ON po.vendor_id = v.id
            ORDER BY po.created_at DESC""").fetchall()
        return rows_to_list(rows)

@app.get("/api/procurement/purchase-orders/{po_id}")
def get_po(po_id: int):
    with get_db() as conn:
        po = row_to_dict(conn.execute(
            "SELECT po.*, v.name as vendor_name FROM purchase_orders po LEFT JOIN vendors v ON po.vendor_id=v.id WHERE po.id=?",
            (po_id,)).fetchone())
        if not po:
            raise HTTPException(404, "PO not found")
        items = rows_to_list(conn.execute(
            "SELECT poi.*, i.name as item_name FROM po_items poi JOIN items i ON poi.item_id=i.id WHERE poi.po_id=?",
            (po_id,)).fetchall())
        po["items"] = items
        return po

@app.post("/api/procurement/purchase-orders")
def create_po(data: dict = Body(...)):
    with get_db() as conn:
        c = conn.cursor()
        po_num = next_number(conn, "purchase_orders", "po_number", "PO")
        items = data.get("items", [])
        total = sum(i.get("quantity",1) * i.get("unit_price",0) for i in items)

        c.execute("""INSERT INTO purchase_orders
                     (po_number,vendor_id,requisition_id,expected_delivery,payment_terms,terms_conditions,total_amount,status)
                     VALUES (?,?,?,?,?,?,?,'draft')""",
                  (po_num, data["vendor_id"], data.get("requisition_id"),
                   data.get("expected_delivery"), data.get("payment_terms","Net 30"),
                   data.get("terms_conditions","Standard terms apply"), total))
        po_id = c.lastrowid

        for item in items:
            c.execute("INSERT INTO po_items (po_id,item_id,quantity,unit_price,total) VALUES (?,?,?,?,?)",
                      (po_id, item["item_id"], item["quantity"], item["unit_price"],
                       item["quantity"]*item["unit_price"]))
        return {"po_number": po_num, "id": po_id}

@app.post("/api/procurement/purchase-orders/{po_id}/send")
def send_po(po_id: int):
    with get_db() as conn:
        conn.execute("UPDATE purchase_orders SET status='sent', updated_at=CURRENT_TIMESTAMP WHERE id=?", (po_id,))
        return {"message": "PO sent"}

@app.get("/api/procurement/purchase-orders/{po_id}/print-data")
def po_print_data(po_id: int):
    with get_db() as conn:
        po = row_to_dict(conn.execute(
            "SELECT po.*, v.name as vendor_name, v.address as vendor_address, v.phone as vendor_phone, v.email as vendor_email, v.gst_number as vendor_gst FROM purchase_orders po LEFT JOIN vendors v ON po.vendor_id=v.id WHERE po.id=?",
            (po_id,)).fetchone())
        if not po:
            raise HTTPException(404, "PO not found")
        items = rows_to_list(conn.execute(
            "SELECT poi.*, i.name as item_name FROM po_items poi JOIN items i ON poi.item_id=i.id WHERE poi.po_id=?",
            (po_id,)).fetchall())
        subtotal = sum(i["total"] or 0 for i in items)
        tax_pct  = 18
        tax_amt  = round(subtotal * tax_pct / 100, 2)

        formatted_items = [{"name": i["item_name"], "qty": i["quantity"],
                             "unit_price": i["unit_price"], "total": i["total"]} for i in items]
        return {
            "po_number": po["po_number"],
            "po_date": po["order_date"] or str(date.today()),
            "expected_delivery": po["expected_delivery"] or "—",
            "payment_terms": po["payment_terms"] or "Net 30",
            "terms_conditions": po["terms_conditions"] or "Standard terms apply.",
            "company": {
                "name": "Cogent Safety & Security Pvt Ltd",
                "address": "Mumbai, Maharashtra, India",
                "phone": "+91-22-0000-0000",
                "email": "info@cogentsecurity.ai",
                "website": "www.cogentsecurity.ai",
            },
            "vendor": {
                "name": po.get("vendor_name","—"),
                "address": po.get("vendor_address","—"),
                "phone": po.get("vendor_phone","—"),
                "email": po.get("vendor_email","—"),
                "gst": po.get("vendor_gst","—"),
            },
            "items": formatted_items,
            "subtotal": subtotal,
            "tax_pct": tax_pct,
            "tax_amount": tax_amt,
            "grand_total": round(subtotal + tax_amt, 2),
        }

# ─────────────────────────────────────────────────────────────────────────────
#   GOODS RECEIPT
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/procurement/goods-receipt")
def list_grns():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT gr.*, po.po_number FROM goods_receipts gr
            LEFT JOIN purchase_orders po ON gr.po_id=po.id
            ORDER BY gr.created_at DESC""").fetchall()
        return rows_to_list(rows)

@app.post("/api/procurement/goods-receipt")
def create_grn(data: dict = Body(...)):
    with get_db() as conn:
        c = conn.cursor()
        po = conn.execute("SELECT po_number FROM purchase_orders WHERE id=?", (data["po_id"],)).fetchone()
        grn_num = next_number(conn, "goods_receipts", "grn_number", "GRN")
        c.execute("""INSERT INTO goods_receipts (grn_number,po_id,po_number,quality_check,notes)
                     VALUES (?,?,?,?,?)""",
                  (grn_num, data["po_id"], po["po_number"] if po else None,
                   1 if data.get("quality_check") else 0, data.get("notes")))
        grn_id = c.lastrowid

        for item in data.get("items", []):
            c.execute("""INSERT INTO grn_items (grn_id,item_id,quantity_ordered,quantity_received,quantity_accepted,quantity_rejected)
                         VALUES (?,?,?,?,?,?)""",
                      (grn_id, item["item_id"], item.get("quantity_ordered",0),
                       item.get("quantity_received",0), item.get("quantity_accepted",0),
                       item.get("quantity_rejected",0)))
            # Update stock
            conn.execute("UPDATE items SET current_stock = current_stock + ? WHERE id=?",
                         (item.get("quantity_accepted",0), item["item_id"]))

        conn.execute("UPDATE purchase_orders SET status='completed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (data["po_id"],))
        return {"grn_number": grn_num, "id": grn_id}

# ─────────────────────────────────────────────────────────────────────────────
#   INVOICES
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/procurement/invoices")
def list_invoices():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT inv.*, v.name as vendor_name FROM invoices inv
            LEFT JOIN vendors v ON inv.vendor_id=v.id
            ORDER BY inv.created_at DESC""").fetchall()
        return rows_to_list(rows)

@app.post("/api/procurement/invoices")
def create_invoice(data: dict = Body(...)):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO invoices
                     (invoice_number,vendor_id,po_id,invoice_date,due_date,amount,tax_amount,total_amount,notes,status)
                     VALUES (?,?,?,?,?,?,?,?,?,'pending')""",
                  (data["invoice_number"], data["vendor_id"], data.get("po_id"),
                   data["invoice_date"], data.get("due_date"),
                   data.get("amount",0), data.get("tax_amount",0), data.get("total_amount",0),
                   data.get("notes")))
        return {"id": c.lastrowid, "message": "Invoice created"}

@app.post("/api/procurement/invoices/{inv_id}/verify")
def verify_invoice(inv_id: int):
    with get_db() as conn:
        conn.execute("UPDATE invoices SET status='verified', updated_at=CURRENT_TIMESTAMP WHERE id=?", (inv_id,))
        return {"message": "Verified"}

@app.post("/api/procurement/invoices/{inv_id}/approve")
def approve_invoice(inv_id: int):
    with get_db() as conn:
        conn.execute("UPDATE invoices SET status='approved', updated_at=CURRENT_TIMESTAMP WHERE id=?", (inv_id,))
        return {"message": "Approved"}

@app.post("/api/procurement/invoices/{inv_id}/pay")
def pay_invoice(inv_id: int, data: dict = Body(...)):
    with get_db() as conn:
        conn.execute("UPDATE invoices SET status='paid', payment_reference=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                     (data.get("payment_reference"), inv_id))
        return {"message": "Payment recorded"}

# ─────────────────────────────────────────────────────────────────────────────
#   OEM MASTER  ✅ Full CRUD with all sub-sections
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/oems")
def list_oems():
    with get_db() as conn:
        return rows_to_list(conn.execute("SELECT * FROM oems ORDER BY created_at DESC").fetchall())

@app.get("/api/oems/stats")
def oem_stats():
    with get_db() as conn:
        def count(q, *a): return conn.execute(q, a).fetchone()[0] or 0
        today = str(date.today())
        ninety = str(date.fromordinal(date.today().toordinal() + 90))
        return {
            "total":        count("SELECT COUNT(*) FROM oems"),
            "active":       count("SELECT COUNT(*) FROM oems WHERE status='Active'"),
            "pending":      count("SELECT COUNT(*) FROM oems WHERE status='Pending'"),
            "high_priority":count("SELECT COUNT(*) FROM oems WHERE strategic_priority='High'"),
            "expiring_soon":count("SELECT COUNT(*) FROM oems WHERE agreement_expiry_date IS NOT NULL AND agreement_expiry_date <= ? AND agreement_expiry_date >= ?", ninety, today),
        }

@app.post("/api/oems")
def create_oem(data: dict = Body(...)):
    with get_db() as conn:
        c = conn.cursor()

        # ── 1. Insert OEM master ──────────────────────────────────
        c.execute("""
            INSERT INTO oems (oem_company_name,category,country,website,registered_address,
                primary_contact_name,designation,mobile,email,secondary_contact,
                support_email,support_phone,status,strategic_priority,noc_for_marketing,
                agreement_type,agreement_signed_date,agreement_expiry_date,notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["oem_company_name"], data.get("category"), data.get("country"),
             data.get("website"), data.get("registered_address"),
             data.get("primary_contact_name"), data.get("designation"), data.get("mobile"),
             data.get("email"), data.get("secondary_contact"),
             data.get("support_email"), data.get("support_phone"),
             data.get("status","Pending"), data.get("strategic_priority","Medium"),
             1 if data.get("noc_for_marketing") else 0,
             data.get("agreement_type"),
             data.get("agreement_signed_date") or None,
             data.get("agreement_expiry_date") or None,
             data.get("notes")))
        oem_id = c.lastrowid

        # ── 2. Products + their pricing / marketing / tender ──────
        for prod in data.get("products", []):
            if not any([prod.get("brand"), prod.get("model_number"), prod.get("product_category")]):
                continue
            c.execute("""
                INSERT INTO oem_products
                    (oem_id,product_category,brand,model_number,series_make,hsn_code,
                     serial_number_format,compliance,warranty_period,warranty_type,
                     amc_available,datasheet_available,hd_images_available,
                     product_description,key_features,technical_specifications)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (oem_id, prod.get("product_category"), prod.get("brand"),
                 prod.get("model_number"), prod.get("series_make"), prod.get("hsn_code"),
                 prod.get("serial_number_format"), prod.get("compliance"),
                 prod.get("warranty_period"), prod.get("warranty_type"),
                 1 if prod.get("amc_available") else 0,
                 1 if prod.get("datasheet_available") else 0,
                 1 if prod.get("hd_images_available") else 0,
                 prod.get("product_description"), prod.get("key_features"),
                 prod.get("technical_specifications")))
            prod_id = c.lastrowid

            # Pricing row (one per product from pricing tab, matched by index or first entry)
            pricing_list = data.get("pricing", [])
            if pricing_list:
                # Try to match by product name, else use first entry
                pr = next((p for p in pricing_list if p.get("price_product","").strip().lower()
                           in (prod.get("model_number","").lower(), prod.get("brand","").lower())), pricing_list[0])
                c.execute("""
                    INSERT INTO oem_product_pricing
                        (product_id,price_product,oem_price,distributor_price,reseller_price,
                         suggested_mrp,standard_margin_pct,currency,moq,lead_time_days,
                         payment_terms,warehouse_location,supply_type)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (prod_id, pr.get("price_product"), pr.get("oem_price"),
                     pr.get("distributor_price"), pr.get("reseller_price"),
                     pr.get("suggested_mrp"), pr.get("standard_margin_pct"),
                     pr.get("currency","INR"), pr.get("moq",1),
                     pr.get("lead_time_days"), pr.get("payment_terms"),
                     pr.get("warehouse_location"), pr.get("supply_type","direct")))

            # Marketing row (one per product)
            mkt = data.get("marketing", {})
            if mkt:
                c.execute("""
                    INSERT INTO oem_product_marketing
                        (product_id,marketing_collateral_available,website_listed,brochure_included,
                         social_media_ready,demo_unit_available,sample_unit_cost,
                         product_images_link,datasheet_link,case_study_link)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (prod_id,
                     1 if mkt.get("marketing_collateral_available") else 0,
                     1 if mkt.get("website_listed") else 0,
                     1 if mkt.get("brochure_included") else 0,
                     1 if mkt.get("social_media_ready") else 0,
                     1 if mkt.get("demo_unit_available") else 0,
                     mkt.get("sample_unit_cost"),
                     mkt.get("product_images_link"), mkt.get("datasheet_link"),
                     mkt.get("case_study_link")))

            # Tender row (one per product)
            tender = data.get("tender", {})
            if tender:
                c.execute("""
                    INSERT INTO oem_product_tender
                        (product_id,psu_govt_approved,stqc_status,tender_eligible,
                         ndaa_compliance,used_in_psu_projects,security_certifications,
                         past_project_references,remarks)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (prod_id,
                     1 if tender.get("psu_govt_approved") else 0,
                     tender.get("stqc_status"),
                     1 if tender.get("tender_eligible") else 0,
                     1 if tender.get("ndaa_compliance") else 0,
                     1 if tender.get("used_in_psu_projects") else 0,
                     tender.get("security_certifications"),
                     tender.get("past_project_references"),
                     tender.get("remarks")))

        # ── 3. Agreement ──────────────────────────────────────────
        agr = data.get("agreement", {})
        if agr and any(agr.values()):
            c.execute("""
                INSERT INTO oem_agreements
                    (oem_id,agreement_type,signed_date,expiry_date,renewal_reminder_date,
                     agreement_document_location,legal_contact,status,remarks)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (oem_id, agr.get("agreement_type"),
                 agr.get("signed_date") or None,
                 agr.get("expiry_date") or None,
                 agr.get("renewal_reminder_date") or None,
                 agr.get("agreement_document_location"),
                 agr.get("legal_contact"),
                 agr.get("status","Active"),
                 agr.get("remarks")))

        # ── 4. Training ───────────────────────────────────────────
        trn = data.get("training", {})
        if trn and any(trn.values()):
            c.execute("""
                INSERT INTO oem_trainings
                    (oem_id,ceo_meeting_done,meeting_date,sales_training_conducted,
                     training_date,trainer_name,presales_support_contact,
                     demo_availability,next_training_due,notes)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (oem_id,
                 1 if trn.get("ceo_meeting_done") else 0,
                 trn.get("meeting_date") or None,
                 1 if trn.get("sales_training_conducted") else 0,
                 trn.get("training_date") or None,
                 trn.get("trainer_name"),
                 trn.get("presales_support_contact"),
                 trn.get("demo_availability"),
                 trn.get("next_training_due") or None,
                 trn.get("notes")))

        return {"id": oem_id, "message": "OEM created successfully with all sub-sections"}

@app.delete("/api/oems/{oem_id}")
def delete_oem(oem_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM oems WHERE id=?", (oem_id,))
        return {"message": "Deleted"}

# ── OEM Sub-resources ──────────────────────────────────────────────────────
@app.get("/api/oems/{oem_id}/products")
def oem_products(oem_id: int):
    with get_db() as conn:
        return rows_to_list(conn.execute(
            "SELECT * FROM oem_products WHERE oem_id=? ORDER BY created_at", (oem_id,)).fetchall())

@app.get("/api/oems/{oem_id}/agreements")
def oem_agreements(oem_id: int):
    with get_db() as conn:
        return rows_to_list(conn.execute(
            "SELECT * FROM oem_agreements WHERE oem_id=? ORDER BY created_at DESC", (oem_id,)).fetchall())

@app.get("/api/oems/{oem_id}/trainings")
def oem_trainings(oem_id: int):
    with get_db() as conn:
        return rows_to_list(conn.execute(
            "SELECT * FROM oem_trainings WHERE oem_id=? ORDER BY created_at DESC", (oem_id,)).fetchall())

@app.get("/api/oem-products/{product_id}/pricing")
def product_pricing(product_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM oem_product_pricing WHERE product_id=?", (product_id,)).fetchone()
        if not row:
            raise HTTPException(404, "No pricing found")
        return row_to_dict(row)

@app.get("/api/oem-products/{product_id}/marketing")
def product_marketing(product_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM oem_product_marketing WHERE product_id=?", (product_id,)).fetchone()
        if not row:
            raise HTTPException(404, "No marketing data found")
        return row_to_dict(row)

@app.get("/api/oem-products/{product_id}/tender")
def product_tender(product_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM oem_product_tender WHERE product_id=?", (product_id,)).fetchone()
        if not row:
            raise HTTPException(404, "No tender data found")
        return row_to_dict(row)

# ── OEM Onboarding Checklist ───────────────────────────────────────────────
@app.get("/api/oems/{oem_id}/onboarding")
def oem_onboarding(oem_id: int):
    with get_db() as conn:
        oem = row_to_dict(conn.execute("SELECT * FROM oems WHERE id=?", (oem_id,)).fetchone())
        if not oem:
            raise HTTPException(404, "OEM not found")

        products  = conn.execute("SELECT COUNT(*) FROM oem_products WHERE oem_id=?", (oem_id,)).fetchone()[0]
        pricing   = conn.execute("SELECT COUNT(*) FROM oem_product_pricing pp JOIN oem_products op ON pp.product_id=op.id WHERE op.oem_id=?", (oem_id,)).fetchone()[0]
        agreements= conn.execute("SELECT COUNT(*) FROM oem_agreements WHERE oem_id=?", (oem_id,)).fetchone()[0]
        marketing = conn.execute("SELECT COUNT(*) FROM oem_product_marketing pm JOIN oem_products op ON pm.product_id=op.id WHERE op.oem_id=?", (oem_id,)).fetchone()[0]
        training  = conn.execute("SELECT COUNT(*) FROM oem_trainings WHERE oem_id=?", (oem_id,)).fetchone()[0]
        tender    = conn.execute("SELECT COUNT(*) FROM oem_product_tender pt JOIN oem_products op ON pt.product_id=op.id WHERE op.oem_id=?", (oem_id,)).fetchone()[0]

        checks = [
            {"section": "Basic Info",    "label": "OEM Company Name set",       "done": bool(oem.get("oem_company_name"))},
            {"section": "Basic Info",    "label": "Contact person added",        "done": bool(oem.get("primary_contact_name"))},
            {"section": "Basic Info",    "label": "Email provided",              "done": bool(oem.get("email"))},
            {"section": "Basic Info",    "label": "Website provided",            "done": bool(oem.get("website"))},
            {"section": "Agreement",     "label": "Agreement type set",          "done": bool(oem.get("agreement_type"))},
            {"section": "Agreement",     "label": "Agreement signed date set",   "done": bool(oem.get("agreement_signed_date"))},
            {"section": "Agreement",     "label": "Agreement expiry date set",   "done": bool(oem.get("agreement_expiry_date"))},
            {"section": "Agreement",     "label": "Agreement record saved",      "done": agreements > 0},
            {"section": "Products",      "label": "At least 1 product added",    "done": products > 0},
            {"section": "Pricing",       "label": "Pricing entry added",         "done": pricing > 0},
            {"section": "Marketing",     "label": "Marketing data filled",       "done": marketing > 0},
            {"section": "Training",      "label": "Training record added",       "done": training > 0},
            {"section": "Compliance",    "label": "Tender/compliance data set",  "done": tender > 0},
            {"section": "Status",        "label": "NOC for marketing obtained",  "done": bool(oem.get("noc_for_marketing"))},
        ]

        completed = sum(1 for c in checks if c["done"])
        total     = len(checks)
        percent   = round(completed / total * 100) if total else 0
        is_onboarded = percent == 100

        if is_onboarded and oem.get("status") != "Onboarded":
            conn.execute("UPDATE oems SET status='Onboarded', updated_at=CURRENT_TIMESTAMP WHERE id=?", (oem_id,))

        return {"checks": checks, "completed": completed, "total": total,
                "percent": percent, "is_onboarded": is_onboarded}

# ─────────────────────────────────────────────────────────────────────────────
#   STARTUP
# ─────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    print("🚀 Procurement API running on http://localhost:5001")

@app.get("/")
def root():
    return {"status": "Procurement CRM API is running", "port": 5001}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001, reload=True)
