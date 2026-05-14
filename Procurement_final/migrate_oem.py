"""
Safe OEM Migration Script
--------------------------
Yeh script sirf NAYI OEM tables banati hai.
Existing data (vendors, items, orders, etc.) BILKUL safe rehta hai.

Usage:
  python migrate_oem.py
"""

from app import app, db
from models import (
    OEM,
    OEMProduct,
    OEMPricing,
    OEMAgreement,
    OEMMarketingAsset,
    OEMTrainingMeeting,
    OEMTenderCompliance,
)

def migrate():
    with app.app_context():
        print("=" * 60)
        print("  OEM Intelligence — Safe Migration")
        print("=" * 60)
        print("\n⏳ Checking existing tables & creating only new ones...")

        # db.create_all() is 100% SAFE:
        # ✅ Nayi tables create karta hai
        # ✅ Already existing tables ko TOUCH nahi karta
        # ✅ Existing data DELETE nahi hota
        db.create_all()

        print("\n✅ Migration complete! Following tables created (if not existed):")
        print("   → oems                   (OEM Master)")
        print("   → oem_products           (Product Master)")
        print("   → oem_pricing            (Pricing)")
        print("   → oem_agreements         (Agreements)")
        print("   → oem_marketing_assets   (Marketing Assets)")
        print("   → oem_training_meetings  (Training & Meetings)")
        print("   → oem_tender_compliance  (Tender Compliance)")
        print("\n✅ Existing data (vendors, items, orders) is UNTOUCHED.")
        print("=" * 60)

if __name__ == '__main__':
    migrate()