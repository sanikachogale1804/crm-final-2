from flask import Blueprint, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── SMTP Config ───────────────────────────────────────────────────────────────
def get_smtp_config():
    return {
        "host":     os.environ.get("MAIL_SERVER",   "smtp.mailngx.com"),
        "port":     int(os.environ.get("MAIL_PORT", 587)),
        "user":     os.environ.get("MAIL_USERNAME", "sanika@cogentsecurity.ai"),
        "password": os.environ.get("MAIL_PASSWORD", "San@180704"),
        "use_tls":  os.environ.get("MAIL_USE_TLS",  "True") == "True",
    }

# ─── Role-based Email Fetcher ─────────────────────────────────────────────────
def get_emails_by_role(*roles):
    from models import User
    emails = []
    for role in roles:
        users = User.query.filter(
            User.role.ilike(role),
            User.email != None,
            User.email != ''
        ).all()
        emails.extend([u.email for u in users if u.email])
    return list(set(emails))

# ─── Email Helper ─────────────────────────────────────────────────────────────
def send_email(subject, recipients, html_body):
    recipients = [r for r in recipients if r]
    if not recipients:
        print(f"📧 [NO RECIPIENTS] Subject: {subject}")
        return

    cfg = get_smtp_config()

    if not cfg["password"]:
        print(f"\n📧 [MAIL PASSWORD MISSING] Would send to: {recipients}")
        print(f"   Subject: {subject}\n")
        return

    try:
        for to_email in recipients:
            msg = MIMEMultipart("alternative")
            msg["From"]    = cfg["user"]
            msg["To"]      = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
                if cfg["use_tls"]:
                    server.starttls()
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)

            print(f"✅ Email sent to {to_email} | Subject: {subject}")

    except Exception as e:
        print(f"⚠️  Email failed (app still works): {e}")

# ── Safe user helpers ─────────────────────────────────────────────────────────
def current_user_id():
    return current_user.id if current_user.is_authenticated else None

def current_user_role():
    return current_user.role if current_user.is_authenticated else None

def require_role(*roles):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Login required'}), 401
    if roles and current_user_role() not in roles:
        return jsonify({'error': 'Unauthorized'}), 403
    return None

# ─── Unique Number Generators (MAX-based — never duplicates) ──────────────────
def generate_number(model, field_name, prefix):
    """
    Safely generate the next sequential number for any document type.
    Uses MAX of existing numbers instead of COUNT(*), so deletions
    or gaps never cause duplicate-key errors.

    Example: prefix='PO-2026-' → 'PO-2026-00009'
    """
    from sqlalchemy import func
    col = getattr(model, field_name)
    last = (
        model.query
        .filter(col.like(f"{prefix}%"))
        .order_by(col.desc())
        .first()
    )
    if last:
        last_val = getattr(last, field_name)
        try:
            last_num = int(last_val.replace(prefix, ""))
        except (ValueError, AttributeError):
            last_num = 0
        return f"{prefix}{last_num + 1:05d}"
    return f"{prefix}00001"


from datetime import datetime
from sqlalchemy import func

from models import (
    User,
    Vendor, VendorStatus,
    Item,
    SalesOrder, SalesOrderItem, SalesOrderStatus,
    PurchaseRequisition, PRStatus,
    PurchaseOrder, PurchaseOrderItem, POStatus,
    GoodsReceipt, GoodsReceiptItem,
    Invoice, InvoiceStatus,
    VendorApproval, PRQuote
)

from extensions import db

routes = Blueprint("routes", __name__)

@routes.route("/home")
def home():
    return "Procurement Module Running Successfully!"


@routes.route("/")
def index():
    return jsonify({
        'message': 'Sales + Procurement CRM API',
        'version': '1.0',
        'endpoints': {
            'auth': '/api/auth/*',
            'vendors': '/api/vendors/*',
            'items': '/api/items/*',
            'sales': '/api/sales/*',
            'procurement': '/api/procurement/*'
        }
    })


# ============= Auth Routes =============

@routes.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400

    user = User(
        username=data['username'],
        email=data['email'],
        role=data.get('role', 'user'),
        department=data.get('department')
    )
    user.set_password(data['password'])

    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'User created successfully', 'user_id': user.id}), 201

@routes.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()

    if user and user.check_password(data['password']):
        login_user(user)
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        }), 200

    return jsonify({'error': 'Invalid credentials'}), 401

@routes.route('/api/auth/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200

@routes.route('/api/auth/me', methods=['GET'])
def me():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not logged in'}), 401
    return jsonify({'user': {
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role
    }}), 200


# ============= Vendor Management Routes =============

@routes.route('/api/vendors', methods=['GET', 'POST'])
def vendors():
    if request.method == 'GET':
        status = request.args.get('status')
        query = Vendor.query
        if status:
            query = query.filter_by(status=status)
        vendors = query.all()
        return jsonify([{
            'id': v.id,
            'name': v.name,
            'contact_person': v.contact_person,
            'email': v.email,
            'phone': v.phone,
            'address': v.address,
            'gst_number': v.gst_number,
            'status': v.status,
            'items_services': v.items_services
        } for v in vendors]), 200

    elif request.method == 'POST':
        data = request.json
        vendor = Vendor(
            name=data['name'],
            contact_person=data.get('contact_person'),
            email=data.get('email'),
            phone=data.get('phone'),
            address=data.get('address'),
            gst_number=data.get('gst_number'),
            vat_number=data.get('vat_number'),
            bank_name=data.get('bank_name'),
            bank_account=data.get('bank_account'),
            ifsc_code=data.get('ifsc_code'),
            items_services=data.get('items_services'),
            status=VendorStatus.PENDING.value
        )

        db.session.add(vendor)
        db.session.flush()

        for stage in ['accounts', 'finance', 'management']:
            approval = VendorApproval(vendor_id=vendor.id, stage=stage, status='pending')
            db.session.add(approval)

        db.session.commit()

        company = os.environ.get('COMPANY_NAME', 'Your Company')
        email_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
          <div style="background:#1e3a8a;padding:20px 24px;">
            <h2 style="color:#fff;margin:0;font-size:20px;">🏭 New Vendor Registration — Action Required</h2>
          </div>
          <div style="padding:24px;">
            <p style="color:#374151;font-size:15px;">A new vendor has been registered and requires your approval.</p>
            <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
              <tr style="background:#f8fafc;"><td style="padding:10px 14px;font-weight:600;color:#6b7280;width:140px;">Vendor Name</td><td style="padding:10px 14px;color:#1e293b;font-weight:700;">{vendor.name}</td></tr>
              <tr><td style="padding:10px 14px;font-weight:600;color:#6b7280;">Contact Person</td><td style="padding:10px 14px;color:#1e293b;">{vendor.contact_person or '—'}</td></tr>
              <tr style="background:#f8fafc;"><td style="padding:10px 14px;font-weight:600;color:#6b7280;">Email</td><td style="padding:10px 14px;color:#1e293b;">{vendor.email or '—'}</td></tr>
              <tr><td style="padding:10px 14px;font-weight:600;color:#6b7280;">Phone</td><td style="padding:10px 14px;color:#1e293b;">{vendor.phone or '—'}</td></tr>
              <tr style="background:#f8fafc;"><td style="padding:10px 14px;font-weight:600;color:#6b7280;">GST Number</td><td style="padding:10px 14px;color:#1e293b;">{vendor.gst_number or '—'}</td></tr>
              <tr><td style="padding:10px 14px;font-weight:600;color:#6b7280;">Items/Services</td><td style="padding:10px 14px;color:#1e293b;">{vendor.items_services or '—'}</td></tr>
              <tr style="background:#f8fafc;"><td style="padding:10px 14px;font-weight:600;color:#6b7280;">Address</td><td style="padding:10px 14px;color:#1e293b;">{vendor.address or '—'}</td></tr>
            </table>
            <div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;padding:12px 16px;margin:16px 0;">
              <strong style="color:#92400e;">⚠️ Approval Pipeline:</strong>
              <span style="color:#92400e;font-size:13px;"> Accounts → Finance → Management.</span>
            </div>
          </div>
          <div style="background:#f8fafc;padding:12px 24px;border-top:1px solid #e2e8f0;">
            <p style="color:#9ca3af;font-size:12px;margin:0;">Automated notification from {company} Procurement System.</p>
          </div>
        </div>
        """

        accounts_emails = get_emails_by_role('accounts')
        if accounts_emails:
            send_email(f"[Action Required] New Vendor Registration: {vendor.name}", accounts_emails, email_html)

        fin_mgmt_emails = get_emails_by_role('finance', 'management')
        if fin_mgmt_emails:
            send_email(f"[FYI] New Vendor Pending Approval: {vendor.name}", fin_mgmt_emails, email_html)

        return jsonify({'message': 'Vendor created, pending multi-level approval', 'vendor_id': vendor.id}), 201


@routes.route('/api/vendors/<int:vendor_id>', methods=['GET', 'PUT', 'DELETE'])
def vendor_detail(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)

    if request.method == 'GET':
        return jsonify({
            'id': vendor.id,
            'name': vendor.name,
            'contact_person': vendor.contact_person,
            'email': vendor.email,
            'phone': vendor.phone,
            'address': vendor.address,
            'gst_number': vendor.gst_number,
            'vat_number': vendor.vat_number,
            'bank_name': vendor.bank_name,
            'bank_account': vendor.bank_account,
            'ifsc_code': vendor.ifsc_code,
            'status': vendor.status,
            'items_services': vendor.items_services
        }), 200

    elif request.method == 'PUT':
        data = request.json
        for key, value in data.items():
            if hasattr(vendor, key):
                setattr(vendor, key, value)
        db.session.commit()
        return jsonify({'message': 'Vendor updated'}), 200

    elif request.method == 'DELETE':
        db.session.delete(vendor)
        db.session.commit()
        return jsonify({'message': 'Vendor deleted'}), 200


@routes.route('/api/vendors/<int:vendor_id>/approve', methods=['POST'])
def approve_vendor(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    vendor.status = VendorStatus.ACTIVE.value
    db.session.commit()
    return jsonify({'message': 'Vendor approved'}), 200


# ============= Item Management Routes =============

@routes.route('/api/items', methods=['GET', 'POST'])
def items():
    if request.method == 'GET':
        items = Item.query.all()
        return jsonify([{
            'id': i.id,
            'name': i.name,
            'sku': i.sku,
            'category': i.category,
            'unit': i.unit,
            'current_stock': i.current_stock,
            'reorder_level': i.reorder_level,
            'unit_price': i.unit_price
        } for i in items]), 200

    elif request.method == 'POST':
        data = request.json
        item = Item(
            name=data['name'],
            description=data.get('description'),
            sku=data.get('sku'),
            category=data.get('category'),
            unit=data.get('unit', 'pcs'),
            current_stock=data.get('current_stock', 0),
            reorder_level=data.get('reorder_level', 0),
            unit_price=data.get('unit_price')
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({'message': 'Item created', 'item_id': item.id}), 201


@routes.route('/api/items/<int:item_id>', methods=['GET', 'PUT'])
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)

    if request.method == 'GET':
        return jsonify({
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'sku': item.sku,
            'category': item.category,
            'unit': item.unit,
            'current_stock': item.current_stock,
            'reorder_level': item.reorder_level,
            'unit_price': item.unit_price
        }), 200

    elif request.method == 'PUT':
        data = request.json
        for key, value in data.items():
            if hasattr(item, key):
                setattr(item, key, value)
        db.session.commit()
        return jsonify({'message': 'Item updated'}), 200


# ============= Sales Order Routes =============

@routes.route('/api/sales/orders', methods=['GET', 'POST'])
def sales_orders():
    if request.method == 'GET':
        orders = SalesOrder.query.all()
        return jsonify([{
            'id': o.id,
            'order_number': o.order_number,
            'customer_name': o.customer_name,
            'order_date': o.order_date.isoformat(),
            'status': o.status,
            'total_amount': o.total_amount
        } for o in orders]), 200

    elif request.method == 'POST':
        data = request.json

        # Resolve user
        username = data.get("username")
        if username:
            finance_user = User.query.filter(
                func.lower(User.username) == username.lower()
            ).first()
        else:
            finance_user = User.query.filter_by(role='admin').first() or User.query.first()

        if not finance_user:
            return jsonify({"error": "No users found in DB. Run init_db.py first."}), 400

        created_by = finance_user.id

        # MAX-based SO number (no duplicates)
        year = datetime.now().year
        order_number = generate_number(SalesOrder, 'order_number', f"SO-{year}-")

        sales_order = SalesOrder(
            order_number=order_number,
            customer_name=data['customer_name'],
            customer_email=data.get('customer_email'),
            customer_phone=data.get('customer_phone'),
            expected_delivery=datetime.strptime(
                data['expected_delivery'], '%Y-%m-%d'
            ).date() if data.get('expected_delivery') else None,
            notes=data.get('notes'),
            created_by=created_by
        )

        db.session.add(sales_order)
        db.session.flush()

        total_amount = 0
        items_needing_procurement = []

        for item_data in data.get('items', []):
            item = None  # ✅ FIX: pehle None initialize karo

            # ✅ FIX: item_id se pehle dhundho
            if item_data.get('item_id'):
                item = Item.query.get(item_data['item_id'])
                # agar item_id se nahi mila toh naam se try karo
                if not item and item_data.get('item_name'):
                    item = Item.query.filter(
                        Item.name.ilike(item_data['item_name'])
                    ).first()

            # ✅ item_id nahi tha — naam se dhundho
            elif item_data.get('item_name'):
                item = Item.query.filter(
                    Item.name.ilike(item_data['item_name'])
                ).first()
                # naam se bhi nahi mila — auto-create karo
                if not item:
                    item = Item(
                        name=item_data['item_name'],
                        description=item_data.get('item_type', ''),
                        unit='pcs',
                        current_stock=0,
                        reorder_level=0,
                        unit_price=0
                    )
                    db.session.add(item)
                    db.session.flush()
                    print(f"✅ Auto-created item: {item_data['item_name']}")

            # ✅ FIX: agar item nahi mila toh error return karo
            if not item:
                db.session.rollback()
                return jsonify({'error': f"Item not found: {item_data}"}), 404

            # ✅ FIX: yeh sab ab BAHAR hai — item_id aur item_name dono ke liye chalega
            quantity   = item_data.get('quantity', 1)
            unit_price = item_data.get('unit_price') or item.unit_price or 0
            total_price = quantity * unit_price

            so_item = SalesOrderItem(
                sales_order_id=sales_order.id,
                item_id=item.id,
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price
            )
            db.session.add(so_item)
            total_amount += total_price

            # ✅ FIX: stock check — PR tabhi banega jab stock kam ho
            print(f"📦 Item: {item.name} | Stock: {item.current_stock} | Required: {quantity}")
            if item.current_stock < quantity:
                shortage = quantity - item.current_stock
                items_needing_procurement.append({
                    'item_id': item.id,
                    'item_name': item.name,
                    'shortage': shortage
                })
                print(f"⚠️ Shortage detected: {item.name} needs {shortage} more units — PR will be created")

        sales_order.total_amount = total_amount
        sales_order.status = SalesOrderStatus.CONFIRMED.value
        db.session.commit()

        # ✅ PR auto-generate karo har shortage ke liye
        prs_created = []
        if items_needing_procurement:
            print(f"📋 Creating {len(items_needing_procurement)} PR(s)...")
            for shortage_info in items_needing_procurement:
                pr = create_auto_purchase_requisition(
                    sales_order.id,
                    shortage_info['item_id'],
                    shortage_info['shortage'],
                    created_by
                )
                prs_created.append(pr.pr_number)
                print(f"✅ PR created: {pr.pr_number} for {shortage_info['item_name']} x{shortage_info['shortage']}")
        else:
            print("ℹ️ No shortages — no PRs needed")

        return jsonify({
            'message': 'Sales order created',
            'order_id': sales_order.id,
            'order_number': sales_order.order_number,
            'purchase_requisitions_created': prs_created
        }), 201


def create_auto_purchase_requisition(sales_order_id, item_id, quantity, user_id):
    """Auto-create a PR from a sales order shortage. Uses MAX-based numbering."""
    # ✅ FIX: MAX-based PR number
    year = datetime.now().year
    pr_number = generate_number(PurchaseRequisition, 'pr_number', f"PR-{year}-")

    pr = PurchaseRequisition(
        pr_number=pr_number,
        item_id=item_id,
        quantity=quantity,
        sales_order_id=sales_order_id,
        requested_by=user_id,
        auto_generated=True,
        status=PRStatus.APPROVED.value,
        approved_by=user_id,
        approval_date=datetime.utcnow()
    )

    db.session.add(pr)
    db.session.commit()
    return pr


@routes.route('/api/sales/orders/<int:order_id>', methods=['GET', 'PUT'])
def sales_order_detail(order_id):
    order = SalesOrder.query.get_or_404(order_id)

    if request.method == 'GET':
        return jsonify({
            'id': order.id,
            'order_number': order.order_number,
            'customer_name': order.customer_name,
            'customer_email': order.customer_email,
            'customer_phone': order.customer_phone,
            'order_date': order.order_date.isoformat(),
            'expected_delivery': order.expected_delivery.isoformat() if order.expected_delivery else None,
            'status': order.status,
            'total_amount': order.total_amount,
            'notes': order.notes,
            'items': [{
                'id': i.id,
                'item_name': i.item.name,
                'quantity': i.quantity,
                'unit_price': i.unit_price,
                'total_price': i.total_price
            } for i in order.items]
        }), 200

    elif request.method == 'PUT':
        data = request.json
        if 'status' in data:
            order.status = data['status']
        db.session.commit()
        return jsonify({'message': 'Sales order updated'}), 200


# ============= Purchase Requisition Routes =============

@routes.route('/api/procurement/requisitions', methods=['GET', 'POST'])
def purchase_requisitions():
    if request.method == 'GET':
        prs = PurchaseRequisition.query.all()
        return jsonify([{
            'id': pr.id,
            'pr_number': pr.pr_number,
            'item_name': pr.item.name,
            'quantity': pr.quantity,
            'status': pr.status,
            'requested_by': pr.requester.username,
            'auto_generated': pr.auto_generated,
            'sales_order': pr.sales_order.order_number if pr.sales_order else None
        } for pr in prs]), 200

    elif request.method == 'POST':
        data = request.json

        default_user = User.query.filter_by(role='admin').first() or User.query.first()
        user_id = current_user_id() or (default_user.id if default_user else 1)
        dept = data.get('department', '')
        if current_user.is_authenticated and current_user.department:
            dept = current_user.department

        # ✅ FIX: MAX-based PR number
        year = datetime.now().year
        pr_number = generate_number(PurchaseRequisition, 'pr_number', f"PR-{year}-")

        pr = PurchaseRequisition(
            pr_number=pr_number,
            item_id=data['item_id'],
            quantity=data['quantity'],
            expected_delivery=datetime.strptime(data['expected_delivery'], '%Y-%m-%d').date() if data.get('expected_delivery') else None,
            estimated_cost=data.get('estimated_cost'),
            requested_by=user_id,
            department=dept,
            justification=data.get('justification')
        )

        db.session.add(pr)
        db.session.commit()
        return jsonify({'message': 'Purchase requisition created', 'pr_id': pr.id}), 201


@routes.route('/api/procurement/requisitions/<int:pr_id>/approve', methods=['POST'])
def approve_requisition(pr_id):
    pr = PurchaseRequisition.query.get_or_404(pr_id)
    pr.status = PRStatus.APPROVED.value
    pr.approved_by = current_user_id()
    pr.approval_date = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Purchase requisition approved'}), 200


@routes.route('/api/procurement/requisitions/<int:pr_id>/reject', methods=['POST'])
def reject_requisition(pr_id):
    pr = PurchaseRequisition.query.get_or_404(pr_id)
    pr.status = PRStatus.REJECTED.value
    db.session.commit()
    return jsonify({'message': 'Purchase requisition rejected'}), 200


# ============= Purchase Order Routes =============

@routes.route('/api/procurement/purchase-orders', methods=['GET', 'POST'])
def purchase_orders():
    if request.method == 'GET':
        pos = PurchaseOrder.query.all()
        return jsonify([{
            'id': po.id,
            'po_number': po.po_number,
            'vendor_id': po.vendor_id,
            'vendor_name': po.vendor.name if po.vendor else f'Unknown Vendor (ID: {po.vendor_id})',
            'order_date': po.order_date.isoformat(),
            'status': po.status,
            'total_amount': po.total_amount
        } for po in pos]), 200

    elif request.method == 'POST':
        data = request.json

        default_user = User.query.filter_by(role='admin').first() or User.query.first()
        user_id = current_user_id() or (default_user.id if default_user else 1)

        # ✅ FIX: MAX-based PO number — no more duplicate key errors
        year = datetime.now().year
        po_number = generate_number(PurchaseOrder, 'po_number', f"PO-{year}-")

        po = PurchaseOrder(
            po_number=po_number,
            vendor_id=data['vendor_id'],
            requisition_id=data.get('requisition_id'),
            expected_delivery=datetime.strptime(data['expected_delivery'], '%Y-%m-%d').date() if data.get('expected_delivery') else None,
            terms_conditions=data.get('terms_conditions'),
            payment_terms=data.get('payment_terms'),
            notes=data.get('notes'),
            created_by=user_id
        )

        db.session.add(po)
        db.session.flush()

        total_amount = 0
        for item_data in data['items']:
            quantity   = item_data['quantity']
            unit_price = item_data['unit_price']
            total_price = quantity * unit_price

            po_item = PurchaseOrderItem(
                po_id=po.id,
                item_id=item_data['item_id'],
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price
            )
            db.session.add(po_item)
            total_amount += total_price

        po.total_amount = total_amount
        po.status = POStatus.DRAFT.value
        db.session.commit()

        return jsonify({
            'message': 'Purchase order created',
            'po_id': po.id,
            'po_number': po.po_number
        }), 201


@routes.route('/api/procurement/purchase-orders/<int:po_id>/send', methods=['POST'])
def send_purchase_order(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    po.status = POStatus.SENT.value
    db.session.commit()

    company = os.environ.get('COMPANY_NAME', 'Your Company')
    items_rows = ''.join([f"""
        <tr style="{'background:#f8fafc;' if i%2==0 else ''}">
          <td style="padding:10px 12px;">{item.item.name}</td>
          <td style="padding:10px 12px;text-align:center;">{item.quantity}</td>
          <td style="padding:10px 12px;text-align:right;">₹{item.unit_price:,.2f}</td>
          <td style="padding:10px 12px;text-align:right;font-weight:600;">₹{item.total_price:,.2f}</td>
        </tr>""" for i, item in enumerate(po.items)])

    vendor_email_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
      <div style="background:#1e3a8a;padding:24px;">
        <h1 style="color:#fff;margin:0;font-size:26px;">PURCHASE ORDER</h1>
        <p style="color:rgba(255,255,255,0.75);margin:4px 0 0;font-size:14px;">{company}</p>
      </div>
      <div style="padding:24px;">
        <table style="width:100%;margin-bottom:20px;font-size:14px;">
          <tr>
            <td style="vertical-align:top;width:50%;">
              <strong style="color:#6b7280;font-size:11px;text-transform:uppercase;">Vendor</strong><br>
              <strong style="font-size:16px;">{po.vendor.name}</strong><br>
              {po.vendor.contact_person or ''}<br>{po.vendor.email or ''}<br>{po.vendor.phone or ''}
            </td>
            <td style="vertical-align:top;text-align:right;">
              <table style="margin-left:auto;font-size:13px;border-collapse:collapse;">
                <tr><td style="padding:3px 8px;color:#6b7280;font-weight:600;">PO Number</td><td style="padding:3px 8px;font-weight:700;color:#1e3a8a;">{po.po_number}</td></tr>
                <tr><td style="padding:3px 8px;color:#6b7280;font-weight:600;">PO Date</td><td style="padding:3px 8px;">{po.order_date.strftime('%d %b %Y')}</td></tr>
                <tr><td style="padding:3px 8px;color:#6b7280;font-weight:600;">Expected Delivery</td><td style="padding:3px 8px;">{po.expected_delivery.strftime('%d %b %Y') if po.expected_delivery else '—'}</td></tr>
                <tr><td style="padding:3px 8px;color:#6b7280;font-weight:600;">Payment Terms</td><td style="padding:3px 8px;">{po.payment_terms or 'Net 30'}</td></tr>
              </table>
            </td>
          </tr>
        </table>
        <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:20px;">
          <thead>
            <tr style="background:#1e3a8a;color:#fff;">
              <th style="padding:10px 12px;text-align:left;">Item Description</th>
              <th style="padding:10px 12px;text-align:center;">Qty</th>
              <th style="padding:10px 12px;text-align:right;">Unit Price</th>
              <th style="padding:10px 12px;text-align:right;">Total</th>
            </tr>
          </thead>
          <tbody>{items_rows}</tbody>
          <tfoot>
            <tr style="background:#1e3a8a;color:#fff;">
              <td colspan="3" style="padding:12px;text-align:right;font-weight:700;font-size:15px;">TOTAL AMOUNT</td>
              <td style="padding:12px;text-align:right;font-weight:700;font-size:15px;">₹{po.total_amount:,.2f}</td>
            </tr>
          </tfoot>
        </table>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:14px;font-size:13px;color:#374151;">
          <strong>Terms & Conditions:</strong> {po.terms_conditions or 'Standard terms and conditions apply.'}
        </div>
        <div style="margin-top:20px;padding:14px 16px;background:#eff6ff;border-left:4px solid #2563eb;border-radius:4px;font-size:13px;color:#1e40af;">
          Please acknowledge this Purchase Order by contacting us at
          <strong>{os.environ.get('MAIL_USERNAME', 'procurement@company.com')}</strong>
        </div>
      </div>
      <div style="background:#f8fafc;padding:12px 24px;border-top:1px solid #e2e8f0;font-size:12px;color:#9ca3af;">
        System-generated Purchase Order from {company}.
      </div>
    </div>
    """

    if po.vendor.email:
        send_email(
            subject=f"Purchase Order {po.po_number} from {company}",
            recipients=[po.vendor.email],
            html_body=vendor_email_html
        )

    internal_emails = get_emails_by_role('accounts', 'finance')
    if internal_emails:
        send_email(
            subject=f"PO {po.po_number} sent to {po.vendor.name}",
            recipients=internal_emails,
            html_body=f"""<div style="font-family:Arial,sans-serif;padding:20px;max-width:500px;">
              <h3 style="color:#1e3a8a;">🛒 Purchase Order Sent</h3>
              <p><strong>{po.po_number}</strong> has been sent to <strong>{po.vendor.name}</strong>.</p>
              <p>Total: <strong>₹{po.total_amount:,.2f}</strong></p>
              <p>Expected Delivery: {po.expected_delivery.strftime('%d %b %Y') if po.expected_delivery else '—'}</p>
            </div>"""
        )

    return jsonify({
        'message': f'Purchase order sent to {po.vendor.name}' + (' via email' if po.vendor.email else ' (no vendor email on file)')
    }), 200


# ============= Goods Receipt Routes =============

@routes.route('/api/procurement/goods-receipt', methods=['GET', 'POST'])
def goods_receipts():
    if request.method == 'GET':
        grns = GoodsReceipt.query.all()
        return jsonify([{
            'id': grn.id,
            'grn_number': grn.grn_number,
            'po_number': grn.purchase_order.po_number if grn.purchase_order else '—',
            'receipt_date': str(grn.receipt_date) if grn.receipt_date else None,
            'quality_check': grn.quality_check,
            'notes': grn.notes
        } for grn in grns])

    elif request.method == 'POST':
        data = request.json

        # ✅ FIX: MAX-based GRN number
        year = datetime.now().year
        grn_number = generate_number(GoodsReceipt, 'grn_number', f"GRN-{year}-")

        po = PurchaseOrder.query.get_or_404(data['po_id'])

        grn = GoodsReceipt(
            grn_number=grn_number,
            po_id=po.id,
            received_by=current_user_id(),
            quality_check=data.get('quality_check', False),
            quality_notes=data.get('quality_notes'),
            notes=data.get('notes')
        )

        db.session.add(grn)
        db.session.flush()

        for item_data in data['items']:
            item = Item.query.get(item_data['item_id'])
            quantity_received = item_data['quantity_received']
            quantity_accepted = item_data.get('quantity_accepted', quantity_received)

            grn_item = GoodsReceiptItem(
                grn_id=grn.id,
                item_id=item.id,
                quantity_ordered=item_data['quantity_ordered'],
                quantity_received=quantity_received,
                quantity_accepted=quantity_accepted,
                quantity_rejected=item_data.get('quantity_rejected', 0)
            )
            db.session.add(grn_item)

            # Update inventory
            item.current_stock += quantity_accepted

        po.status = POStatus.COMPLETED.value

        if po.requisition and po.requisition.sales_order:
            check_and_update_sales_order_status(po.requisition.sales_order.id)

        db.session.commit()
        return jsonify({'message': 'Goods receipt recorded', 'grn_id': grn.id}), 201


def check_and_update_sales_order_status(sales_order_id):
    sales_order = SalesOrder.query.get(sales_order_id)
    all_items_available = all(
        so_item.item.current_stock >= so_item.quantity
        for so_item in sales_order.items
    )
    if all_items_available:
        sales_order.status = SalesOrderStatus.READY_TO_SHIP.value
        db.session.commit()


# ============= Invoice & Payment Routes =============

@routes.route('/api/procurement/invoices', methods=['GET', 'POST'])
def invoices():
    if request.method == 'GET':
        invoices = Invoice.query.all()
        return jsonify([{
            'id': inv.id,
            'invoice_number': inv.invoice_number,
            'vendor_name': inv.vendor.name,
            'invoice_date': inv.invoice_date.isoformat(),
            'total_amount': inv.total_amount,
            'status': inv.status
        } for inv in invoices]), 200

    elif request.method == 'POST':
        data = request.json
        invoice = Invoice(
            invoice_number=data['invoice_number'],
            vendor_id=data['vendor_id'],
            po_id=data.get('po_id'),
            invoice_date=datetime.strptime(data['invoice_date'], '%Y-%m-%d').date(),
            due_date=datetime.strptime(data['due_date'], '%Y-%m-%d').date() if data.get('due_date') else None,
            amount=data['amount'],
            tax_amount=data.get('tax_amount', 0),
            total_amount=data['total_amount'],
            notes=data.get('notes')
        )
        db.session.add(invoice)
        db.session.commit()
        return jsonify({'message': 'Invoice created', 'invoice_id': invoice.id}), 201


@routes.route('/api/procurement/invoices/<int:invoice_id>/verify', methods=['POST'])
def verify_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    invoice.verified_by = current_user_id()
    db.session.commit()
    return jsonify({'message': 'Invoice verified'}), 200


@routes.route('/api/procurement/invoices/<int:invoice_id>/approve', methods=['POST'])
def approve_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    invoice.status = InvoiceStatus.APPROVED.value
    invoice.approved_by = current_user_id()
    db.session.commit()
    return jsonify({'message': 'Invoice approved for payment'}), 200


@routes.route('/api/procurement/invoices/<int:invoice_id>/pay', methods=['POST'])
def pay_invoice(invoice_id):
    data = request.json
    invoice = Invoice.query.get_or_404(invoice_id)
    invoice.status = InvoiceStatus.PAID.value
    invoice.payment_date = datetime.utcnow().date()
    invoice.payment_reference = data.get('payment_reference')
    db.session.commit()
    return jsonify({'message': 'Payment recorded'}), 200


# ============= Dashboard Stats =============

@routes.route('/api/dashboard/stats', methods=['GET'])
def dashboard_stats():
    return jsonify({
        'total_vendors': Vendor.query.filter_by(status=VendorStatus.ACTIVE.value).count(),
        'pending_requisitions': PurchaseRequisition.query.filter_by(status=PRStatus.PENDING.value).count(),
        'active_purchase_orders': PurchaseOrder.query.filter(
            PurchaseOrder.status.in_([POStatus.SENT.value, POStatus.ACKNOWLEDGED.value])
        ).count(),
        'pending_invoices': Invoice.query.filter_by(status=InvoiceStatus.PENDING.value).count(),
        'active_sales_orders': SalesOrder.query.filter(
            SalesOrder.status.in_([SalesOrderStatus.CONFIRMED.value, SalesOrderStatus.IN_PROGRESS.value])
        ).count()
    }), 200


@routes.route("/api/procurement/purchase-orders/<int:po_id>", methods=["GET"])
def get_purchase_order(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    items = PurchaseOrderItem.query.filter_by(po_id=po_id).all()
    return jsonify({
        "id": po.id,
        "po_number": po.po_number,
        "vendor_name": po.vendor.name if po.vendor else "",
        "total_amount": po.total_amount,
        "status": po.status,
        "items": [{
            "item_id": i.item_id,
            "item_name": i.item.name if i.item else "",
            "quantity": i.quantity
        } for i in items]
    }), 200


# ============= OEM Master Routes =============

from models import OEM, OEMStatus, OEMPriority

# ⚠️  /stats MUST come before /<int:oem_id>
@routes.route('/api/oems/stats', methods=['GET'])
def oem_stats():
    return jsonify({
        'total': OEM.query.count(),
        'active': OEM.query.filter_by(status='Onboarded').count(),
        'pending': OEM.query.filter_by(status='Work in Progress').count(),
        'high_priority': OEM.query.filter_by(strategic_priority=OEMPriority.HIGH.value).count(),
        'expiring_soon': OEM.query.filter(
            OEM.agreement_expiry_date != None,
            OEM.agreement_expiry_date <= db.func.date_add(db.func.now(), db.text('INTERVAL 90 DAY'))
        ).count()
    }), 200


@routes.route('/api/oems', methods=['GET', 'POST'])
def oems():
    if request.method == 'GET':
        status   = request.args.get('status')
        priority = request.args.get('priority')
        query    = OEM.query
        if status:   query = query.filter_by(status=status)
        if priority: query = query.filter_by(strategic_priority=priority)
        oem_list = query.order_by(OEM.oem_company_name).all()
        return jsonify([{
            'id': o.id,
            'oem_company_name': o.oem_company_name,
            'category': o.category,
            'country': o.country,
            'website': o.website,
            'registered_address': o.registered_address,
            'primary_contact_name': o.primary_contact_name,
            'designation': o.designation,
            'mobile': o.mobile,
            'email': o.email,
            'secondary_contact': o.secondary_contact,
            'support_email': o.support_email,
            'support_phone': o.support_phone,
            'status': o.status,
            'agreement_type': o.agreement_type,
            'agreement_signed_date': o.agreement_signed_date.isoformat() if o.agreement_signed_date else None,
            'agreement_expiry_date': o.agreement_expiry_date.isoformat() if o.agreement_expiry_date else None,
            'noc_for_marketing': o.noc_for_marketing,
            'strategic_priority': o.strategic_priority,
            'notes': o.notes,
            'created_at': o.created_at.isoformat()
        } for o in oem_list]), 200

    elif request.method == 'POST':
        data = request.json
        oem = OEM(
            oem_company_name=data['oem_company_name'],
            category=data.get('category'),
            country=data.get('country'),
            website=data.get('website'),
            registered_address=data.get('registered_address'),
            primary_contact_name=data.get('primary_contact_name'),
            designation=data.get('designation'),
            mobile=data.get('mobile'),
            email=data.get('email'),
            secondary_contact=data.get('secondary_contact'),
            support_email=data.get('support_email'),
            support_phone=data.get('support_phone'),
            status=data.get('status', OEMStatus.PENDING.value),
            agreement_type=data.get('agreement_type'),
            agreement_signed_date=datetime.strptime(data['agreement_signed_date'], '%Y-%m-%d').date() if data.get('agreement_signed_date') else None,
            agreement_expiry_date=datetime.strptime(data['agreement_expiry_date'], '%Y-%m-%d').date() if data.get('agreement_expiry_date') else None,
            noc_for_marketing=data.get('noc_for_marketing', False),
            strategic_priority=data.get('strategic_priority', OEMPriority.MEDIUM.value),
            notes=data.get('notes')
        )
        db.session.add(oem)
        db.session.flush()

        from models import (OEMProduct, OEMPricing, OEMAgreement,
                            OEMMarketingAsset, OEMTrainingMeeting, OEMTenderCompliance)

        pricing_list   = data.get('pricing', [])
        marketing_data = data.get('marketing', {})
        tender_data    = data.get('tender', {})

        for prod in data.get('products', []):
            if not any([prod.get('brand'), prod.get('model_number'), prod.get('product_category')]):
                continue

            product = OEMProduct(
                oem_id=oem.id,
                product_category=prod.get('product_category'),
                brand=prod.get('brand'),
                model_number=prod.get('model_number'),
                series_make=prod.get('series_make'),
                hsn_code=prod.get('hsn_code'),
                serial_number_format=prod.get('serial_number_format'),
                compliance=prod.get('compliance'),
                warranty_period=prod.get('warranty_period'),
                warranty_type=prod.get('warranty_type'),
                amc_available=bool(prod.get('amc_available')),
                datasheet_available=bool(prod.get('datasheet_available')),
                hd_images_available=bool(prod.get('hd_images_available')),
                product_description=prod.get('product_description'),
                key_features=prod.get('key_features'),
                technical_specifications=prod.get('technical_specifications'),
            )
            db.session.add(product)
            db.session.flush()

            if pricing_list:
                pr = next(
                    (p for p in pricing_list if p.get('price_product', '').strip().lower()
                     in (prod.get('model_number', '').lower(), prod.get('brand', '').lower())),
                    pricing_list[0]
                )
                pricing = OEMPricing(
                    product_id=product.id,
                    oem_price=pr.get('oem_price'),
                    distributor_price=pr.get('distributor_price'),
                    reseller_price=pr.get('reseller_price'),
                    suggested_mrp=pr.get('suggested_mrp'),
                    standard_margin_pct=pr.get('standard_margin_pct'),
                    currency=pr.get('currency', 'INR'),
                    moq=pr.get('moq', 1),
                    lead_time_days=pr.get('lead_time_days'),
                    payment_terms=pr.get('payment_terms'),
                    warehouse_location=pr.get('warehouse_location'),
                    supply_type=pr.get('supply_type', 'direct'),
                )
                db.session.add(pricing)

            if marketing_data:
                marketing = OEMMarketingAsset(
                    product_id=product.id,
                    oem_id=oem.id,
                    marketing_collateral_available=bool(marketing_data.get('marketing_collateral_available')),
                    website_listed=bool(marketing_data.get('website_listed')),
                    brochure_included=bool(marketing_data.get('brochure_included')),
                    social_media_ready=bool(marketing_data.get('social_media_ready')),
                    demo_unit_available=bool(marketing_data.get('demo_unit_available')),
                    sample_unit_cost=marketing_data.get('sample_unit_cost'),
                    product_images_link=marketing_data.get('product_images_link'),
                    datasheet_link=marketing_data.get('datasheet_link'),
                    case_study_link=marketing_data.get('case_study_link'),
                )
                db.session.add(marketing)

            if tender_data:
                tender = OEMTenderCompliance(
                    product_id=product.id,
                    oem_id=oem.id,
                    psu_govt_approved=bool(tender_data.get('psu_govt_approved')),
                    stqc_status=tender_data.get('stqc_status'),
                    tender_eligible=bool(tender_data.get('tender_eligible')),
                    ndaa_compliance=bool(tender_data.get('ndaa_compliance')),
                    used_in_psu_projects=bool(tender_data.get('used_in_psu_projects')),
                    security_certifications=tender_data.get('security_certifications'),
                    past_project_references=tender_data.get('past_project_references'),
                    remarks=tender_data.get('remarks'),
                )
                db.session.add(tender)

        agr = data.get('agreement', {})
        if agr and any(v for v in agr.values() if v):
            agreement = OEMAgreement(
                oem_id=oem.id,
                agreement_type=agr.get('agreement_type'),
                signed_date=datetime.strptime(agr['signed_date'], '%Y-%m-%d').date() if agr.get('signed_date') else None,
                expiry_date=datetime.strptime(agr['expiry_date'], '%Y-%m-%d').date() if agr.get('expiry_date') else None,
                renewal_reminder_date=datetime.strptime(agr['renewal_reminder_date'], '%Y-%m-%d').date() if agr.get('renewal_reminder_date') else None,
                agreement_document_location=agr.get('agreement_document_location'),
                legal_contact=agr.get('legal_contact'),
                status=agr.get('status', 'Active'),
                remarks=agr.get('remarks'),
            )
            db.session.add(agreement)

        trn = data.get('training', {})
        if trn and any(v for v in trn.values() if v):
            training = OEMTrainingMeeting(
                oem_id=oem.id,
                ceo_meeting_done=bool(trn.get('ceo_meeting_done')),
                meeting_date=datetime.strptime(trn['meeting_date'], '%Y-%m-%d').date() if trn.get('meeting_date') else None,
                sales_training_conducted=bool(trn.get('sales_training_conducted')),
                training_date=datetime.strptime(trn['training_date'], '%Y-%m-%d').date() if trn.get('training_date') else None,
                trainer_name=trn.get('trainer_name'),
                presales_support_contact=trn.get('presales_support_contact'),
                demo_availability=trn.get('demo_availability'),
                next_training_due=datetime.strptime(trn['next_training_due'], '%Y-%m-%d').date() if trn.get('next_training_due') else None,
                notes=trn.get('notes'),
            )
            db.session.add(training)

        db.session.commit()
        return jsonify({'message': 'OEM created successfully with all sections', 'oem_id': oem.id}), 201


@routes.route('/api/oems/<int:oem_id>', methods=['GET', 'PUT', 'DELETE'])
def oem_detail(oem_id):
    oem = OEM.query.get_or_404(oem_id)

    if request.method == 'GET':
        return jsonify({
            'id': oem.id,
            'oem_company_name': oem.oem_company_name,
            'category': oem.category,
            'country': oem.country,
            'website': oem.website,
            'registered_address': oem.registered_address,
            'primary_contact_name': oem.primary_contact_name,
            'designation': oem.designation,
            'mobile': oem.mobile,
            'email': oem.email,
            'secondary_contact': oem.secondary_contact,
            'support_email': oem.support_email,
            'support_phone': oem.support_phone,
            'status': oem.status,
            'agreement_type': oem.agreement_type,
            'agreement_signed_date': oem.agreement_signed_date.isoformat() if oem.agreement_signed_date else None,
            'agreement_expiry_date': oem.agreement_expiry_date.isoformat() if oem.agreement_expiry_date else None,
            'noc_for_marketing': oem.noc_for_marketing,
            'strategic_priority': oem.strategic_priority,
            'notes': oem.notes
        }), 200

    elif request.method == 'PUT':
        data = request.json
        for field in ['oem_company_name','category','country','website','registered_address',
                      'primary_contact_name','designation','mobile','email','secondary_contact',
                      'support_email','support_phone','status','agreement_type',
                      'noc_for_marketing','strategic_priority','notes']:
            if field in data:
                setattr(oem, field, data[field])
        if data.get('agreement_signed_date'):
            oem.agreement_signed_date = datetime.strptime(data['agreement_signed_date'], '%Y-%m-%d').date()
        if data.get('agreement_expiry_date'):
            oem.agreement_expiry_date = datetime.strptime(data['agreement_expiry_date'], '%Y-%m-%d').date()
        oem.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'message': 'OEM updated successfully'}), 200

    elif request.method == 'DELETE':
        db.session.delete(oem)
        db.session.commit()
        return jsonify({'message': 'OEM deleted successfully'}), 200


# ── OEM Sub-Tab Routes ─────────────────────────────────────────────────────────

@routes.route('/api/oems/<int:oem_id>/products', methods=['GET'])
def oem_products(oem_id):
    from models import OEMProduct
    products = OEMProduct.query.filter_by(oem_id=oem_id).all()
    return jsonify([{
        'id': p.id, 'oem_id': p.oem_id,
        'product_category': p.product_category, 'brand': p.brand,
        'model_number': p.model_number, 'series_make': p.series_make,
        'hsn_code': p.hsn_code, 'serial_number_format': p.serial_number_format,
        'product_description': p.product_description, 'key_features': p.key_features,
        'technical_specifications': p.technical_specifications, 'compliance': p.compliance,
        'warranty_period': p.warranty_period, 'warranty_type': p.warranty_type,
        'amc_available': p.amc_available, 'datasheet_available': p.datasheet_available,
        'hd_images_available': p.hd_images_available,
    } for p in products]), 200


@routes.route('/api/oem-products/<int:product_id>/pricing', methods=['GET'])
def oem_product_pricing(product_id):
    from models import OEMPricing
    pr = OEMPricing.query.filter_by(product_id=product_id).first_or_404()
    return jsonify({
        'id': pr.id, 'product_id': pr.product_id,
        'oem_price': pr.oem_price, 'distributor_price': pr.distributor_price,
        'reseller_price': pr.reseller_price, 'suggested_mrp': pr.suggested_mrp,
        'standard_margin_pct': pr.standard_margin_pct, 'currency': pr.currency,
        'payment_terms': pr.payment_terms, 'moq': pr.moq,
        'lead_time_days': pr.lead_time_days, 'warehouse_location': pr.warehouse_location,
        'supply_type': pr.supply_type,
    }), 200


@routes.route('/api/oems/<int:oem_id>/agreements', methods=['GET'])
def oem_agreements(oem_id):
    from models import OEMAgreement
    agreements = OEMAgreement.query.filter_by(oem_id=oem_id).all()
    return jsonify([{
        'id': a.id, 'oem_id': a.oem_id,
        'agreement_type': a.agreement_type,
        'signed_date': a.signed_date.isoformat() if a.signed_date else None,
        'expiry_date': a.expiry_date.isoformat() if a.expiry_date else None,
        'renewal_reminder_date': a.renewal_reminder_date.isoformat() if a.renewal_reminder_date else None,
        'agreement_document_location': a.agreement_document_location,
        'legal_contact': a.legal_contact, 'status': a.status, 'remarks': a.remarks,
    } for a in agreements]), 200


@routes.route('/api/oem-products/<int:product_id>/marketing', methods=['GET'])
def oem_product_marketing(product_id):
    from models import OEMMarketingAsset
    m = OEMMarketingAsset.query.filter_by(product_id=product_id).first_or_404()
    return jsonify({
        'id': m.id, 'product_id': m.product_id, 'oem_id': m.oem_id,
        'product_images_link': m.product_images_link, 'datasheet_link': m.datasheet_link,
        'case_study_link': m.case_study_link,
        'marketing_collateral_available': m.marketing_collateral_available,
        'website_listed': m.website_listed, 'brochure_included': m.brochure_included,
        'social_media_ready': m.social_media_ready, 'demo_unit_available': m.demo_unit_available,
        'sample_unit_cost': m.sample_unit_cost,
    }), 200


@routes.route('/api/oems/<int:oem_id>/trainings', methods=['GET'])
def oem_trainings(oem_id):
    from models import OEMTrainingMeeting
    trainings = OEMTrainingMeeting.query.filter_by(oem_id=oem_id).all()
    return jsonify([{
        'id': t.id, 'oem_id': t.oem_id,
        'ceo_meeting_done': t.ceo_meeting_done,
        'meeting_date': t.meeting_date.isoformat() if t.meeting_date else None,
        'sales_training_conducted': t.sales_training_conducted,
        'training_date': t.training_date.isoformat() if t.training_date else None,
        'trainer_name': t.trainer_name, 'presales_support_contact': t.presales_support_contact,
        'demo_availability': t.demo_availability,
        'next_training_due': t.next_training_due.isoformat() if t.next_training_due else None,
        'notes': t.notes,
    } for t in trainings]), 200


@routes.route('/api/oem-products/<int:product_id>/tender', methods=['GET'])
def oem_product_tender(product_id):
    from models import OEMTenderCompliance
    t = OEMTenderCompliance.query.filter_by(product_id=product_id).first_or_404()
    return jsonify({
        'id': t.id, 'product_id': t.product_id, 'oem_id': t.oem_id,
        'psu_govt_approved': t.psu_govt_approved, 'stqc_status': t.stqc_status,
        'tender_eligible': t.tender_eligible, 'ndaa_compliance': t.ndaa_compliance,
        'security_certifications': t.security_certifications,
        'past_project_references': t.past_project_references,
        'used_in_psu_projects': t.used_in_psu_projects, 'remarks': t.remarks,
    }), 200


# ── Onboarding Status ──────────────────────────────────────────────────────────

@routes.route('/api/oems/<int:oem_id>/onboarding', methods=['GET'])
def oem_onboarding_status(oem_id):
    from models import (OEM, OEMProduct, OEMPricing, OEMAgreement,
                        OEMMarketingAsset, OEMTrainingMeeting, OEMTenderCompliance)

    def yes(val):
        if val is None:
            return False
        return bool(int(val)) if isinstance(val, (int, float)) else bool(val)

    oem = OEM.query.get_or_404(oem_id)
    products    = OEMProduct.query.filter_by(oem_id=oem_id).all()
    product_ids = [p.id for p in products]

    checks = []

    checks.append({'section': 'OEM Master', 'label': 'Company name filled',        'done': bool(oem.oem_company_name)})
    checks.append({'section': 'OEM Master', 'label': 'Primary contact added',      'done': bool(oem.primary_contact_name)})
    checks.append({'section': 'OEM Master', 'label': 'Email added',                'done': bool(oem.email)})
    checks.append({'section': 'OEM Master', 'label': 'Country filled',             'done': bool(oem.country)})
    checks.append({'section': 'OEM Master', 'label': 'NOC for Marketing obtained', 'done': yes(oem.noc_for_marketing)})

    agreement = OEMAgreement.query.filter_by(oem_id=oem_id, status='Active').first()
    checks.append({'section': 'Agreements', 'label': 'Active agreement exists',    'done': bool(agreement)})
    checks.append({'section': 'Agreements', 'label': 'Agreement signed date set',  'done': bool(agreement and agreement.signed_date)})
    checks.append({'section': 'Agreements', 'label': 'Agreement expiry date set',  'done': bool(agreement and agreement.expiry_date)})

    checks.append({'section': 'Product Master', 'label': 'At least 1 product added', 'done': len(products) > 0})

    if product_ids:
        priced      = OEMPricing.query.filter(OEMPricing.product_id.in_(product_ids)).count()
        valid_price = OEMPricing.query.filter(OEMPricing.product_id.in_(product_ids), OEMPricing.oem_price > 0).count()
        checks.append({'section': 'Pricing', 'label': f'Pricing filled for all products ({priced}/{len(product_ids)})', 'done': priced == len(product_ids)})
        checks.append({'section': 'Pricing', 'label': 'OEM base price entered', 'done': valid_price > 0})
    else:
        checks.append({'section': 'Pricing', 'label': 'Pricing filled for all products (0/0)', 'done': False})
        checks.append({'section': 'Pricing', 'label': 'OEM base price entered', 'done': False})

    if product_ids:
        mkt = OEMMarketingAsset.query.filter(OEMMarketingAsset.product_id.in_(product_ids)).first()
        checks.append({'section': 'Marketing Assets', 'label': 'Marketing collateral available', 'done': bool(mkt) and yes(mkt.marketing_collateral_available)})
        checks.append({'section': 'Marketing Assets', 'label': 'Datasheet link added',           'done': bool(mkt) and bool(mkt.datasheet_link)})
        checks.append({'section': 'Marketing Assets', 'label': 'Product images (HD) available',  'done': bool(mkt) and bool(mkt.product_images_link)})
    else:
        checks.append({'section': 'Marketing Assets', 'label': 'Marketing collateral available', 'done': False})
        checks.append({'section': 'Marketing Assets', 'label': 'Datasheet available',            'done': False})
        checks.append({'section': 'Marketing Assets', 'label': 'Product images (HD) available',  'done': False})

    training = OEMTrainingMeeting.query.filter_by(oem_id=oem_id).first()
    checks.append({'section': 'Training & Meetings', 'label': 'CEO / Leadership meeting done',  'done': bool(training) and yes(training.ceo_meeting_done)})
    checks.append({'section': 'Training & Meetings', 'label': 'Sales training conducted',       'done': bool(training) and yes(training.sales_training_conducted)})
    checks.append({'section': 'Training & Meetings', 'label': 'Presales support contact added', 'done': bool(training) and bool(training.presales_support_contact)})

    if product_ids:
        tender = OEMTenderCompliance.query.filter(OEMTenderCompliance.product_id.in_(product_ids)).first()
        checks.append({'section': 'Tender Compliance', 'label': 'Tender compliance record added', 'done': bool(tender)})
        checks.append({'section': 'Tender Compliance', 'label': 'PSU / Govt approval status set', 'done': bool(tender) and bool(tender.stqc_status)})
    else:
        checks.append({'section': 'Tender Compliance', 'label': 'Tender compliance record added', 'done': False})
        checks.append({'section': 'Tender Compliance', 'label': 'PSU / Govt approval status set', 'done': False})

    total        = len(checks)
    completed    = sum(1 for c in checks if c['done'])
    percent      = round((completed / total) * 100) if total else 0
    is_onboarded = (completed == total)

    new_status = 'Onboarded' if is_onboarded else 'Work in Progress'
    if oem.status != new_status:
        oem.status = new_status
        db.session.commit()

    return jsonify({
        'oem_id':       oem_id,
        'total':        total,
        'completed':    completed,
        'percent':      percent,
        'is_onboarded': is_onboarded,
        'status':       new_status,
        'checks':       checks
    }), 200


# ============= Vendor Multi-Level Approval Routes =============

from models import VendorApproval, PRQuote
import base64

APPROVAL_STAGES = ['accounts', 'finance', 'management']

@routes.route('/api/vendors/<int:vendor_id>/approvals', methods=['GET'])
def get_vendor_approvals(vendor_id):
    vendor    = Vendor.query.get_or_404(vendor_id)
    approvals = VendorApproval.query.filter_by(vendor_id=vendor_id).all()
    return jsonify({
        'vendor_id':     vendor_id,
        'vendor_name':   vendor.name,
        'vendor_status': vendor.status,
        'approvals': [{
            'id':               a.id,
            'stage':            a.stage,
            'status':           a.status,
            'approved_by_name': a.approved_by_name,
            'approved_at':      a.approved_at.isoformat() if a.approved_at else None,
            'comments':         a.comments
        } for a in approvals]
    }), 200


@routes.route('/api/vendors/<int:vendor_id>/approve-stage', methods=['POST'])
def approve_vendor_stage(vendor_id):
    data             = request.json
    stage            = data.get('stage')
    action           = data.get('action', 'approve')
    comments         = data.get('comments', '')
    approved_by_name = data.get('approved_by', 'Admin')

    if stage not in APPROVAL_STAGES:
        return jsonify({'error': 'Invalid stage. Use: accounts, finance, management'}), 400

    stage_idx = APPROVAL_STAGES.index(stage)
    for prev_stage in APPROVAL_STAGES[:stage_idx]:
        prev = VendorApproval.query.filter_by(vendor_id=vendor_id, stage=prev_stage).first()
        if not prev or prev.status != 'approved':
            return jsonify({'error': f'Please complete {prev_stage} approval first'}), 400

    approval = VendorApproval.query.filter_by(vendor_id=vendor_id, stage=stage).first()
    if not approval:
        return jsonify({'error': 'Approval record not found'}), 404

    if action == 'approve':
        approval.status = 'approved'
    elif action == 'reject':
        approval.status = 'rejected'
    else:
        return jsonify({'error': 'Invalid action'}), 400

    approval.approved_by_name = approved_by_name
    approval.approved_at      = datetime.utcnow()
    approval.comments         = comments

    vendor_activated = False
    if action == 'approve' and stage == 'management':
        all_approved = all(
            VendorApproval.query.filter_by(vendor_id=vendor_id, stage=s).first() and
            VendorApproval.query.filter_by(vendor_id=vendor_id, stage=s).first().status == 'approved'
            for s in APPROVAL_STAGES
        )
        if all_approved:
            vendor = Vendor.query.get(vendor_id)
            vendor.status    = VendorStatus.ACTIVE.value
            vendor_activated = True

    if action == 'reject':
        vendor = Vendor.query.get(vendor_id)
        vendor.status = VendorStatus.INACTIVE.value

    db.session.commit()

    company  = os.environ.get('COMPANY_NAME', 'Your Company')
    vend_obj = Vendor.query.get(vendor_id)
    next_stage_role = {'accounts': 'finance', 'finance': 'management', 'management': None}

    if action == 'approve':
        if vendor_activated:
            all_team_emails = get_emails_by_role('accounts', 'finance', 'management', 'admin')
            if vend_obj.email:
                all_team_emails.append(vend_obj.email)
            all_team_emails = list(set(all_team_emails))
            activation_html = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
              <div style="background:#16a34a;padding:20px 24px;">
                <h2 style="color:#fff;margin:0;">✅ Vendor Approved & Activated</h2>
              </div>
              <div style="padding:24px;">
                <p style="font-size:15px;color:#374151;">Vendor <strong>{vend_obj.name}</strong> is now <strong style="color:#16a34a;">ACTIVE</strong>.</p>
                <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
                  <tr style="background:#f0fdf4;"><td style="padding:10px;font-weight:600;color:#6b7280;width:140px;">Vendor</td><td style="padding:10px;">{vend_obj.name}</td></tr>
                  <tr><td style="padding:10px;font-weight:600;color:#6b7280;">Status</td><td style="padding:10px;color:#16a34a;font-weight:700;">✅ Active</td></tr>
                  <tr style="background:#f0fdf4;"><td style="padding:10px;font-weight:600;color:#6b7280;">Approved by</td><td style="padding:10px;">{approved_by_name}</td></tr>
                </table>
              </div>
            </div>"""
            for email in all_team_emails:
                send_email(f"✅ Vendor Activated: {vend_obj.name}", [email], activation_html)

        elif next_stage_role.get(stage):
            next_emails      = get_emails_by_role(next_stage_role[stage])
            next_stage_name  = next_stage_role[stage].title()
            next_html = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
              <div style="background:#2563eb;padding:20px 24px;">
                <h2 style="color:#fff;margin:0;">🔔 Vendor Approval — Your Turn ({next_stage_name})</h2>
              </div>
              <div style="padding:24px;">
                <p style="font-size:15px;color:#374151;">Vendor <strong>{vend_obj.name}</strong> now requires <strong>{next_stage_name}</strong> approval.</p>
                <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
                  <tr style="background:#f8fafc;"><td style="padding:10px;font-weight:600;color:#6b7280;width:140px;">Vendor</td><td style="padding:10px;">{vend_obj.name}</td></tr>
                  <tr><td style="padding:10px;font-weight:600;color:#6b7280;">Previous Stage</td><td style="padding:10px;color:#16a34a;">✅ {stage.title()} — Approved by {approved_by_name}</td></tr>
                  <tr style="background:#f8fafc;"><td style="padding:10px;font-weight:600;color:#6b7280;">Comments</td><td style="padding:10px;">{comments or '—'}</td></tr>
                </table>
                <div style="background:#eff6ff;border:1px solid #3b82f6;border-radius:6px;padding:12px 16px;">
                  Please login to Procurement System → Vendor Management and click the <strong>{next_stage_name}</strong> approve button.
                </div>
              </div>
            </div>"""
            if next_emails:
                send_email(f"[Action Required] Vendor Approval ({next_stage_name}): {vend_obj.name}",
                           next_emails, next_html)

    elif action == 'reject':
        rejected_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
          <div style="background:#dc2626;padding:20px 24px;">
            <h2 style="color:#fff;margin:0;">❌ Vendor Registration Rejected</h2>
          </div>
          <div style="padding:24px;">
            <p style="font-size:15px;color:#374151;">Vendor <strong>{vend_obj.name}</strong> has been <strong style="color:#dc2626;">REJECTED</strong> at the <strong>{stage.title()}</strong> stage.</p>
            <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
              <tr style="background:#fef2f2;"><td style="padding:10px;font-weight:600;color:#6b7280;width:140px;">Rejected by</td><td style="padding:10px;">{approved_by_name}</td></tr>
              <tr><td style="padding:10px;font-weight:600;color:#6b7280;">Stage</td><td style="padding:10px;">{stage.title()}</td></tr>
              <tr style="background:#fef2f2;"><td style="padding:10px;font-weight:600;color:#6b7280;">Reason</td><td style="padding:10px;">{comments or 'No reason provided'}</td></tr>
            </table>
          </div>
        </div>"""
        all_team_emails = get_emails_by_role('accounts', 'finance', 'management', 'admin')
        if all_team_emails:
            send_email(f"❌ Vendor Rejected: {vend_obj.name}", all_team_emails, rejected_html)

    return jsonify({'message': f'Stage {stage} {action}d successfully'}), 200


# ============= PR Quotes Routes =============

@routes.route('/api/procurement/requisitions/<int:pr_id>/quotes', methods=['GET'])
def get_pr_quotes(pr_id):
    PurchaseRequisition.query.get_or_404(pr_id)
    quotes = PRQuote.query.filter_by(pr_id=pr_id).all()
    return jsonify([{
        'id':           q.id,
        'quote_number': q.quote_number,
        'vendor_name':  q.vendor_name,
        'amount':       q.amount,
        'pdf_filename': q.pdf_filename,
        'has_pdf':      bool(q.pdf_data),
        'notes':        q.notes,
        'uploaded_at':  q.uploaded_at.isoformat()
    } for q in quotes]), 200


@routes.route('/api/procurement/requisitions/<int:pr_id>/quotes', methods=['POST'])
def upload_pr_quote(pr_id):
    pr = PurchaseRequisition.query.get_or_404(pr_id)

    existing_count = PRQuote.query.filter_by(pr_id=pr_id).count()
    if existing_count >= 3:
        return jsonify({'error': 'Maximum 3 quotes allowed per requisition'}), 400

    data  = request.json
    quote = PRQuote(
        pr_id=pr_id,
        quote_number=data.get('quote_number', f'Q-{pr_id}-{existing_count+1}'),
        vendor_name=data.get('vendor_name', ''),
        amount=data.get('amount'),
        pdf_data=data.get('pdf_data'),
        pdf_filename=data.get('pdf_filename'),
        notes=data.get('notes')
    )
    db.session.add(quote)
    db.session.commit()
    return jsonify({
        'message':      'Quote uploaded',
        'quote_id':     quote.id,
        'total_quotes': existing_count + 1
    }), 201


@routes.route('/api/procurement/requisitions/<int:pr_id>/quotes/<int:quote_id>', methods=['DELETE'])
def delete_pr_quote(pr_id, quote_id):
    quote = PRQuote.query.filter_by(id=quote_id, pr_id=pr_id).first_or_404()
    db.session.delete(quote)
    db.session.commit()
    return jsonify({'message': 'Quote deleted'}), 200


@routes.route('/api/procurement/requisitions/<int:pr_id>/quotes/<int:quote_id>/pdf', methods=['GET'])
def get_quote_pdf(pr_id, quote_id):
    from flask import Response
    quote = PRQuote.query.filter_by(id=quote_id, pr_id=pr_id).first_or_404()
    if not quote.pdf_data:
        return jsonify({'error': 'No PDF uploaded'}), 404
    pdf_bytes = base64.b64decode(quote.pdf_data)
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'inline; filename="{quote.pdf_filename or "quote.pdf"}"'}
    )


@routes.route('/api/procurement/requisitions/<int:pr_id>/approve-with-check', methods=['POST'])
def approve_requisition_with_check(pr_id):
    pr          = PurchaseRequisition.query.get_or_404(pr_id)
    quote_count = PRQuote.query.filter_by(pr_id=pr_id).count()
    if quote_count < 3:
        return jsonify({'error': f'3 vendor quotes are mandatory. Currently {quote_count} uploaded.'}), 400
    pr.status        = PRStatus.APPROVED.value
    pr.approved_by   = current_user_id()
    pr.approval_date = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Purchase requisition approved with all 3 quotes verified'}), 200


# ============= PO Print Data =============

@routes.route('/api/procurement/purchase-orders/<int:po_id>/print-data', methods=['GET'])
def get_po_print_data(po_id):
    po    = PurchaseOrder.query.get_or_404(po_id)
    items = PurchaseOrderItem.query.filter_by(po_id=po_id).all()

    subtotal    = sum(i.total_price for i in items)
    tax_pct     = 18
    tax_amount  = round(subtotal * tax_pct / 100, 2)
    shipping    = 0
    grand_total = subtotal + tax_amount + shipping

    return jsonify({
        'po_number':         po.po_number,
        'po_date':           po.order_date.strftime('%d %b %Y') if po.order_date else '',
        'expected_delivery': po.expected_delivery.strftime('%d %b %Y') if po.expected_delivery else '',
        'payment_terms':     po.payment_terms or 'Net 30',
        'terms_conditions':  po.terms_conditions or 'Standard terms and conditions apply.',
        'company': {
            'name':    'Your Company Name',
            'address': '89 Your Company Street, City, State, Country',
            'phone':   '123-456-7890',
            'email':   'your@companyemail.com',
            'website': 'yourwebsite.com'
        },
        'vendor': {
            'name':    po.vendor.name,
            'address': po.vendor.address or '—',
            'phone':   po.vendor.phone or '—',
            'email':   po.vendor.email or '—',
            'gst':     po.vendor.gst_number or '—'
        },
        'items': [{
            'name':        i.item.name,
            'description': i.item.description or '',
            'qty':         i.quantity,
            'unit_price':  i.unit_price,
            'total':       i.total_price
        } for i in items],
        'subtotal':    subtotal,
        'tax_pct':     tax_pct,
        'tax_amount':  tax_amount,
        'shipping_fee': shipping,
        'grand_total': grand_total
    }), 200
