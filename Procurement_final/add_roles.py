"""
Run this once:  python add_roles.py
Yeh script DB mein accounts aur management role ke users add karega.
"""

from app import app
from models import User
from extensions import db

with app.app_context():

    # ── 1. Accounts user add karo ─────────────────────────────────
    if not User.query.filter_by(role='accounts').first():
        accounts_user = User(
            username='accounts',
            email='accounts@cogentsecurity.ai',   
            role='accounts',
            department='Accounts'
        )
        accounts_user.set_password('accounts123')
        db.session.add(accounts_user)
        print("Accounts user created")
    else:
        print("Accounts user already exists")

    # ── 2. Management user add karo ───────────────────────────────
    if not User.query.filter_by(role='management').first():
        mgmt_user = User(
            username='management',
            email='management@cogentsecurity.ai',  
            role='management',
            department='Management'
        )
        mgmt_user.set_password('management123')
        db.session.add(mgmt_user)
        print("Management user created")
    else:
        print("Management user already exists")

    db.session.commit()

    # ── 3. Verify all roles ───────────────────────────────────────
    print("\n─── All Users in DB ───────────────────────────────────")
    for u in User.query.order_by(User.role).all():
        print(f"  Role: {u.role:15} | Email: {u.email:35} | Name: {u.username}")

    print("\n─── Email will go to: ─────────────────────────────────")
    print(f"  New Vendor added   → accounts role users get [Action Required]")
    print(f"  Accounts approved  → finance role users get [Your Turn]")
    print(f"  Finance approved   → management role users get [Your Turn]")
    print(f"  All 3 approved     → all teams + vendor get [Activated]")
