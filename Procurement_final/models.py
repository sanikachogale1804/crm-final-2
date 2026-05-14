from extensions import db
from flask_login import UserMixin
from datetime import datetime
from enum import Enum
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.mysql import LONGTEXT

pdf_data = db.Column(LONGTEXT)

# ===========================================================================
# ENUMS
# ===========================================================================

class VendorStatus(str, Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    PENDING = 'pending'

class PRStatus(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class POStatus(str, Enum):
    DRAFT = 'draft'
    SENT = 'sent'
    ACKNOWLEDGED = 'acknowledged'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

class InvoiceStatus(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    PAID = 'paid'
    REJECTED = 'rejected'

class SalesOrderStatus(str, Enum):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    IN_PROGRESS = 'in_progress'
    READY_TO_SHIP = 'ready_to_ship'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'

# OEM-specific Enums
class OEMStatus(str, Enum):
    ACTIVE = 'Active'
    PENDING = 'Pending'
    INACTIVE = 'Inactive'

class OEMCategory(str, Enum):
    MANUFACTURER = 'Manufacturer'
    DISTRIBUTOR = 'Distributor'
    TECH_PARTNER = 'Tech Partner'

class OEMPriority(str, Enum):
    HIGH = 'High'
    MEDIUM = 'Medium'
    LOW = 'Low'

class AgreementStatus(str, Enum):
    ACTIVE = 'Active'
    EXPIRED = 'Expired'
    PENDING = 'Pending'

class SupplyType(str, Enum):
    IMPORT = 'Import'
    LOCAL = 'Local'


# ===========================================================================
# EXISTING PROCUREMENT MODELS (Unchanged)
# ===========================================================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # admin, manager, user, finance
    department = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Vendor(db.Model):
    __tablename__ = 'vendors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    gst_number = db.Column(db.String(50))
    vat_number = db.Column(db.String(50))
    bank_name = db.Column(db.String(100))
    bank_account = db.Column(db.String(50))
    ifsc_code = db.Column(db.String(20))
    status = db.Column(db.String(20), default=VendorStatus.PENDING.value)
    items_services = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    purchase_orders = db.relationship('PurchaseOrder', backref='vendor', lazy=True)
    invoices = db.relationship('Invoice', backref='vendor', lazy=True)


class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    sku = db.Column(db.String(50), unique=True)
    category = db.Column(db.String(100))
    unit = db.Column(db.String(20))
    current_stock = db.Column(db.Float, default=0)
    reorder_level = db.Column(db.Float, default=0)
    unit_price = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SalesOrder(db.Model):
    __tablename__ = 'sales_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_name = db.Column(db.String(200), nullable=False)
    customer_email = db.Column(db.String(120))
    customer_phone = db.Column(db.String(20))
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_delivery = db.Column(db.Date)
    status = db.Column(db.String(20), default=SalesOrderStatus.PENDING.value)
    total_amount = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('SalesOrderItem', backref='sales_order', lazy=True, cascade='all, delete-orphan')
    purchase_requisitions = db.relationship('PurchaseRequisition', backref='sales_order', lazy=True)


class SalesOrderItem(db.Model):
    __tablename__ = 'sales_order_items'
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)

    item = db.relationship('Item', backref='sales_order_items')


class PurchaseRequisition(db.Model):
    __tablename__ = 'purchase_requisitions'
    id = db.Column(db.Integer, primary_key=True)
    pr_number = db.Column(db.String(50), unique=True, nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    expected_delivery = db.Column(db.Date)
    estimated_cost = db.Column(db.Float)
    status = db.Column(db.String(20), default=PRStatus.PENDING.value)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department = db.Column(db.String(100))
    justification = db.Column(db.Text)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'))
    auto_generated = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approval_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    item = db.relationship('Item', backref='purchase_requisitions')
    requester = db.relationship('User', foreign_keys=[requested_by], backref='requisitions_created')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='requisitions_approved')
    purchase_orders = db.relationship('PurchaseOrder', backref='requisition', lazy=True)


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(50), unique=True, nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    requisition_id = db.Column(db.Integer, db.ForeignKey('purchase_requisitions.id'))
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_delivery = db.Column(db.Date)
    status = db.Column(db.String(20), default=POStatus.DRAFT.value)
    total_amount = db.Column(db.Float, default=0)
    terms_conditions = db.Column(db.Text)
    payment_terms = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy=True, cascade='all, delete-orphan')
    grn = db.relationship('GoodsReceipt', backref='purchase_order', lazy=True)
    creator = db.relationship('User', foreign_keys=[created_by], backref='purchase_orders_created')


class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)

    item = db.relationship('Item', backref='purchase_order_items')


class GoodsReceipt(db.Model):
    __tablename__ = 'goods_receipts'
    id = db.Column(db.Integer, primary_key=True)
    grn_number = db.Column(db.String(50), unique=True, nullable=False)
    po_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    receipt_date = db.Column(db.DateTime, default=datetime.utcnow)
    received_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    quality_check = db.Column(db.Boolean, default=False)
    quality_notes = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('GoodsReceiptItem', backref='goods_receipt', lazy=True, cascade='all, delete-orphan')
    receiver = db.relationship('User', foreign_keys=[received_by], backref='goods_received')


class GoodsReceiptItem(db.Model):
    __tablename__ = 'goods_receipt_items'
    id = db.Column(db.Integer, primary_key=True)
    grn_id = db.Column(db.Integer, db.ForeignKey('goods_receipts.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity_ordered = db.Column(db.Float, nullable=False)
    quantity_received = db.Column(db.Float, nullable=False)
    quantity_accepted = db.Column(db.Float)
    quantity_rejected = db.Column(db.Float)

    item = db.relationship('Item', backref='goods_receipt_items')


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    po_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'))
    invoice_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date)
    amount = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default=InvoiceStatus.PENDING.value)
    payment_date = db.Column(db.Date)
    payment_reference = db.Column(db.String(100))
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    purchase_order = db.relationship('PurchaseOrder', backref='invoices')
    verifier = db.relationship('User', foreign_keys=[verified_by], backref='invoices_verified')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='invoices_approved')


# ===========================================================================
#  OEM INTELLIGENCE MODULE  — Excel Sheet → DB Table Mapping
#
#  Sheet 1: OEM Master         → Table: oems                  (Primary)
#  Sheet 2: Product Master     → Table: oem_products          FK: oem_id → oems.id
#  Sheet 3: Pricing            → Table: oem_pricing           FK: product_id → oem_products.id  (1:1)
#  Sheet 4: Agreements         → Table: oem_agreements        FK: oem_id → oems.id              (1:Many)
#  Sheet 5: Marketing Assets   → Table: oem_marketing_assets  FK: product_id + oem_id           (1:1 per product)
#  Sheet 6: Training & Meeting → Table: oem_training_meetings FK: oem_id → oems.id              (1:Many)
#  Sheet 7: Tender Compliance  → Table: oem_tender_compliance FK: product_id + oem_id           (1:1 per product)
# ===========================================================================


# ---------------------------------------------------------------------------
# TABLE 1 — OEM Master  (Sheet: "OEM Master")
# Root / Parent table. Sabhi OEM tables isko refer karti hain.
# ---------------------------------------------------------------------------
class OEM(db.Model):
    __tablename__ = 'oems'

    id = db.Column(db.Integer, primary_key=True)
    oem_company_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))           # Manufacturer / Distributor / Tech Partner
    country = db.Column(db.String(100))
    website = db.Column(db.String(255))
    registered_address = db.Column(db.Text)
    primary_contact_name = db.Column(db.String(100))
    designation = db.Column(db.String(100))
    mobile = db.Column(db.String(30))
    email = db.Column(db.String(120))
    secondary_contact = db.Column(db.String(150))  # name + phone combined
    support_email = db.Column(db.String(120))
    support_phone = db.Column(db.String(30))
    status = db.Column(db.String(20), default=OEMStatus.PENDING.value)   # Active / Pending
    agreement_type = db.Column(db.String(100))
    agreement_signed_date = db.Column(db.Date)
    agreement_expiry_date = db.Column(db.Date)
    noc_for_marketing = db.Column(db.Boolean, default=False)             # Yes / No
    strategic_priority = db.Column(db.String(20), default=OEMPriority.MEDIUM.value)  # High / Medium / Low
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships (one OEM → many of everything below) ──
    products    = db.relationship('OEMProduct',         backref='oem', lazy=True, cascade='all, delete-orphan')
    agreements  = db.relationship('OEMAgreement',       backref='oem', lazy=True, cascade='all, delete-orphan')
    trainings   = db.relationship('OEMTrainingMeeting', backref='oem', lazy=True, cascade='all, delete-orphan')


# ---------------------------------------------------------------------------
# TABLE 2 — Product Master  (Sheet: "Product Master")
# One OEM can have MANY products.
# FK: oem_id → oems.id
# ---------------------------------------------------------------------------
class OEMProduct(db.Model):
    __tablename__ = 'oem_products'

    id = db.Column(db.Integer, primary_key=True)
    oem_id = db.Column(db.Integer, db.ForeignKey('oems.id', ondelete='CASCADE'), nullable=False)
    # ↑ FK: oem_products.oem_id → oems.id  (Many products belong to one OEM)

    product_category = db.Column(db.String(100))
    brand = db.Column(db.String(100))
    model_number = db.Column(db.String(100))
    series_make = db.Column(db.String(100))
    hsn_code = db.Column(db.String(20))
    serial_number_format = db.Column(db.String(100))
    product_description = db.Column(db.Text)
    key_features = db.Column(db.Text)
    technical_specifications = db.Column(db.Text)
    compliance = db.Column(db.String(200))         # BIS / STQC / CE / NDAA
    warranty_period = db.Column(db.String(50))
    warranty_type = db.Column(db.String(100))
    amc_available = db.Column(db.Boolean, default=False)
    datasheet_available = db.Column(db.Boolean, default=False)
    hd_images_available = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Child relationships (one product → one pricing, one compliance, one marketing) ──
    pricing            = db.relationship('OEMPricing',           backref='product', uselist=False, cascade='all, delete-orphan')
    marketing_asset    = db.relationship('OEMMarketingAsset',    backref='product', uselist=False, cascade='all, delete-orphan')
    tender_compliance  = db.relationship('OEMTenderCompliance',  backref='product', uselist=False, cascade='all, delete-orphan')


# ---------------------------------------------------------------------------
# TABLE 3 — Pricing  (Sheet: "Pricing")
# ONE-TO-ONE with OEMProduct. Each product has exactly one pricing row.
# FK: product_id → oem_products.id
# ---------------------------------------------------------------------------
class OEMPricing(db.Model):
    __tablename__ = 'oem_pricing'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('oem_products.id', ondelete='CASCADE'), nullable=False, unique=True)
    # ↑ FK: oem_pricing.product_id → oem_products.id  (unique = 1:1 with product)

    oem_price = db.Column(db.Float)
    distributor_price = db.Column(db.Float)
    reseller_price = db.Column(db.Float)
    suggested_mrp = db.Column(db.Float)
    standard_margin_pct = db.Column(db.Float)          # e.g. 25.0 means 25%
    currency = db.Column(db.String(10), default='INR')
    payment_terms = db.Column(db.String(200))
    moq = db.Column(db.Integer)                        # Minimum Order Quantity
    lead_time_days = db.Column(db.Integer)
    warehouse_location = db.Column(db.String(200))
    supply_type = db.Column(db.String(20))             # Import / Local
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# TABLE 4 — Agreements  (Sheet: "Agreements")
# ONE-TO-MANY with OEM. One OEM can have multiple agreements over time.
# FK: oem_id → oems.id
# ---------------------------------------------------------------------------
class OEMAgreement(db.Model):
    __tablename__ = 'oem_agreements'

    id = db.Column(db.Integer, primary_key=True)
    oem_id = db.Column(db.Integer, db.ForeignKey('oems.id', ondelete='CASCADE'), nullable=False)
    # ↑ FK: oem_agreements.oem_id → oems.id  (Many agreements per OEM)

    agreement_type = db.Column(db.String(100))         # Reseller / Distributor / OEM / Partner
    signed_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    renewal_reminder_date = db.Column(db.Date)
    agreement_document_location = db.Column(db.String(500))   # file path or URL
    legal_contact = db.Column(db.String(150))
    status = db.Column(db.String(20), default=AgreementStatus.PENDING.value)  # Active/Expired/Pending
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# TABLE 5 — Marketing Assets  (Sheet: "Marketing Assets")
# ONE-TO-ONE with OEMProduct AND references OEM for redundancy/querying.
# FK: product_id → oem_products.id   (primary)
#     oem_id     → oems.id           (for direct OEM-level queries)
# ---------------------------------------------------------------------------
class OEMMarketingAsset(db.Model):
    __tablename__ = 'oem_marketing_assets'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('oem_products.id', ondelete='CASCADE'), nullable=False, unique=True)
    # ↑ FK: oem_marketing_assets.product_id → oem_products.id  (1:1 per product)

    oem_id = db.Column(db.Integer, db.ForeignKey('oems.id', ondelete='CASCADE'), nullable=False)
    # ↑ FK: oem_marketing_assets.oem_id → oems.id  (for direct OEM queries without joining products)

    product_images_link = db.Column(db.String(500))
    datasheet_link = db.Column(db.String(500))
    case_study_link = db.Column(db.String(500))
    marketing_collateral_available = db.Column(db.Boolean, default=False)
    website_listed = db.Column(db.Boolean, default=False)
    brochure_included = db.Column(db.Boolean, default=False)
    social_media_ready = db.Column(db.Boolean, default=False)
    demo_unit_available = db.Column(db.Boolean, default=False)
    sample_unit_cost = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# TABLE 6 — Training & Meetings  (Sheet: "Training & Meetings")
# ONE-TO-MANY with OEM. Training sessions can happen multiple times per OEM.
# FK: oem_id → oems.id
# ---------------------------------------------------------------------------
class OEMTrainingMeeting(db.Model):
    __tablename__ = 'oem_training_meetings'

    id = db.Column(db.Integer, primary_key=True)
    oem_id = db.Column(db.Integer, db.ForeignKey('oems.id', ondelete='CASCADE'), nullable=False)
    # ↑ FK: oem_training_meetings.oem_id → oems.id  (Many training records per OEM)

    ceo_meeting_done = db.Column(db.Boolean, default=False)
    meeting_date = db.Column(db.Date)
    sales_training_conducted = db.Column(db.Boolean, default=False)
    training_date = db.Column(db.Date)
    trainer_name = db.Column(db.String(100))
    presales_support_contact = db.Column(db.String(150))
    demo_availability = db.Column(db.String(100))      # e.g. "On Request", "Always", "No"
    next_training_due = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# TABLE 7 — Tender Compliance  (Sheet: "Tender Compliance")
# ONE-TO-ONE with OEMProduct AND references OEM.
# FK: product_id → oem_products.id   (primary, unique = 1:1)
#     oem_id     → oems.id           (for direct OEM-level queries)
# ---------------------------------------------------------------------------
class OEMTenderCompliance(db.Model):
    __tablename__ = 'oem_tender_compliance'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('oem_products.id', ondelete='CASCADE'), nullable=False, unique=True)
    # ↑ FK: oem_tender_compliance.product_id → oem_products.id  (1:1 per product)

    oem_id = db.Column(db.Integer, db.ForeignKey('oems.id', ondelete='CASCADE'), nullable=False)
    # ↑ FK: oem_tender_compliance.oem_id → oems.id  (for direct OEM queries)

    psu_govt_approved = db.Column(db.Boolean, default=False)
    stqc_status = db.Column(db.String(100))           # e.g. "Certified", "Pending", "Not Applicable"
    tender_eligible = db.Column(db.Boolean, default=False)
    ndaa_compliance = db.Column(db.Boolean, default=False)
    security_certifications = db.Column(db.String(300))  # comma-separated certs
    past_project_references = db.Column(db.Text)
    used_in_psu_projects = db.Column(db.Boolean, default=False)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ===========================================================================
# NEW: VENDOR MULTI-LEVEL APPROVAL
# ===========================================================================

class VendorApproval(db.Model):
    __tablename__ = 'vendor_approvals'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    stage = db.Column(db.String(20), nullable=False)   # accounts, finance, management
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    approved_by_name = db.Column(db.String(100))
    approved_at = db.Column(db.DateTime)
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vendor = db.relationship('Vendor', backref='approvals')


# ===========================================================================
# NEW: PR QUOTES (3 quotes mandatory, PDF upload)
# ===========================================================================

class PRQuote(db.Model):
    __tablename__ = 'pr_quotes'
    id = db.Column(db.Integer, primary_key=True)
    pr_id = db.Column(db.Integer, db.ForeignKey('purchase_requisitions.id'), nullable=False)
    quote_number = db.Column(db.String(100))
    vendor_name = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float)
    pdf_data = db.Column(LONGTEXT)       # base64 encoded PDF
    pdf_filename = db.Column(db.String(255))
    notes = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    pr = db.relationship('PurchaseRequisition', backref='quotes')
