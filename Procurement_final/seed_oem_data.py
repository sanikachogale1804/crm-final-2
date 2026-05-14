"""
OEM Demo Data Seeder
---------------------
Excel file ka saara data database mein insert karta hai.
Existing data safe rehta hai.

Usage:
  python seed_oem_data.py
"""

from app import app, db
from models import (
    OEM, OEMProduct, OEMPricing,
    OEMAgreement, OEMMarketingAsset,
    OEMTrainingMeeting, OEMTenderCompliance
)
from datetime import date

def seed():
    with app.app_context():
        print("=" * 60)
        print("  OEM Demo Data Seeder")
        print("=" * 60)

        # ── Check if already seeded ──────────────────────────────
        if OEM.query.filter_by(oem_company_name='CogentX').first():
            print("\n⚠️  CogentX already exists. Skipping to avoid duplicates.")
            print("   Agar firse seed karna hai toh pehle manually delete karo.")
            return

        # ────────────────────────────────────────────────────────
        # TABLE 1: OEM Master
        # ────────────────────────────────────────────────────────
        oem = OEM(
            oem_company_name    = 'CogentX',
            category            = 'Security Products',
            country             = 'India',
            website             = 'www.cogent.com',
            registered_address  = 'Powai Andheri Mumbai',
            primary_contact_name= 'MSOOD',
            designation         = 'CEO',
            mobile              = '123456',
            email               = 'mohan@cogent.com',
            secondary_contact   = 'Sukhi',
            support_email       = 'support@cogent.com',
            support_phone       = '987654',
            status              = 'Onboarded',
            agreement_type      = 'Business Partner',
            agreement_signed_date  = date(2026, 3, 4),
            agreement_expiry_date  = date(2027, 3, 3),
            noc_for_marketing   = False,
            strategic_priority  = 'Medium',
            notes               = 'Keep it open upto 200 characters'
        )
        db.session.add(oem)
        db.session.flush()   # oem.id milega bina commit ke
        print(f"\n✅ OEM Master created → ID: {oem.id}  ({oem.oem_company_name})")

        # ────────────────────────────────────────────────────────
        # TABLE 2: Product Master
        # ────────────────────────────────────────────────────────
        product = OEMProduct(
            oem_id               = oem.id,
            product_category     = 'CCTV',
            brand                = 'CogX',
            model_number         = 'AB12CC34',
            series_make          = 'XTREME',
            hsn_code             = 'HS1234',
            serial_number_format = '987654321',
            product_description  = '4MP IP CAMERA SD CARD AI MODE MOTION DETC HUMAN DETECTION',
            key_features         = 'SD CARD, AI MODE, MOTION DETECTION, HUMAN DETECTION',
            technical_specifications = '2.7 mm lens, 360 deg view, 50 mtrs range, IR LED SUPPORT NIGHT VISION',
            compliance           = 'Yes',
            warranty_period      = '2 yrs',
            warranty_type        = 'Only Technical fault',
            amc_available        = True,
            datasheet_available  = True,
            hd_images_available  = True,
        )
        db.session.add(product)
        db.session.flush()
        print(f"✅ Product Master created → ID: {product.id}  ({product.brand} {product.model_number})")

        # ────────────────────────────────────────────────────────
        # TABLE 3: Pricing
        # ────────────────────────────────────────────────────────
        pricing = OEMPricing(
            product_id           = product.id,
            oem_price            = 1234,
            distributor_price    = 0,
            reseller_price       = 0,
            suggested_mrp        = 0,
            standard_margin_pct  = 0,
            currency             = 'INR',
            payment_terms        = '30 / 60 / 0',
            moq                  = 2,
            lead_time_days       = 7,
            warehouse_location   = 'Chennai',
            supply_type          = 'Local',
        )
        db.session.add(pricing)
        print(f"✅ Pricing created → Product ID: {product.id}  (₹{pricing.oem_price})")

        # ────────────────────────────────────────────────────────
        # TABLE 4: Agreements
        # ────────────────────────────────────────────────────────
        agreement = OEMAgreement(
            oem_id               = oem.id,
            agreement_type       = 'Business Partner',
            signed_date          = date(2026, 3, 4),
            expiry_date          = date(2027, 3, 3),
            renewal_reminder_date= date(2027, 1, 1),
            agreement_document_location = 'Attach & Save',
            legal_contact        = 'MSOOD',
            status               = 'Active',
            remarks              = 'NOC for Marketing: NO',
        )
        db.session.add(agreement)
        print(f"✅ Agreement created → OEM ID: {oem.id}  ({agreement.agreement_type})")

        # ────────────────────────────────────────────────────────
        # TABLE 5: Marketing Assets
        # ────────────────────────────────────────────────────────
        marketing = OEMMarketingAsset(
            oem_id=oem.id,
            product_id=product.id,
            datasheet_link="https://example.com/datasheet.pdf",
            product_images_link="https://example.com/images",
            marketing_collateral_available=True,
            brochure_included=True,
            website_listed=True,
            social_media_ready=False,
            demo_unit_available=True,
            sample_unit_cost=5000
        )

        db.session.add(marketing)
        print(f"✅ Marketing Assets created → Product ID: {product.id}")

        # ────────────────────────────────────────────────────────
        # TABLE 6: Training & Meetings
        # ────────────────────────────────────────────────────────
        training = OEMTrainingMeeting(
            oem_id                   = oem.id,
            ceo_meeting_done         = True,
            meeting_date             = date(2026, 2, 27),
            sales_training_conducted = True,
            training_date            = date(2026, 3, 3),
            trainer_name             = 'Ganesh',
            presales_support_contact = '9999999',
            demo_availability        = 'Yes',
            notes                    = 'Cogent Product Code: Auto Generate',
        )
        db.session.add(training)
        print(f"✅ Training & Meeting created → OEM ID: {oem.id}")

        # ────────────────────────────────────────────────────────
        # TABLE 7: Tender Compliance
        # ────────────────────────────────────────────────────────
        tender = OEMTenderCompliance(
            product_id            = product.id,
            oem_id                = oem.id,
            psu_govt_approved     = True,
            stqc_status           = 'Approved',
            tender_eligible       = True,
            ndaa_compliance       = False,
            security_certifications = 'Approved',
            past_project_references = 'Keep it open upto 200 characters',
            used_in_psu_projects  = True,
            remarks               = 'WIP / Onboarded',
        )
        db.session.add(tender)
        print(f"✅ Tender Compliance created → Product ID: {product.id}")

        # ── Final commit ─────────────────────────────────────────
        db.session.commit()

        print("\n" + "=" * 60)
        print("  ✅ ALL DATA INSERTED SUCCESSFULLY!")
        print("=" * 60)
        print(f"\n  OEM:       {oem.oem_company_name}  (ID: {oem.id})")
        print(f"  Product:   {product.brand} {product.model_number}  (ID: {product.id})")
        print(f"  Tables filled: oems, oem_products, oem_pricing,")
        print(f"                 oem_agreements, oem_marketing_assets,")
        print(f"                 oem_training_meetings, oem_tender_compliance")
        print("=" * 60)

if __name__ == '__main__':
    seed()
