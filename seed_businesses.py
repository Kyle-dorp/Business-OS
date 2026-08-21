#!/usr/bin/env python3
"""
Seed script to create three business profiles with test users and modules.
Run this ONCE to set up: McAlister's, BAMS, PupCuts
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.models import UserAccount, Business, Membership, BusinessModule
from app.auth import hash_password
from app.database import engine, create_db_and_tables
from sqlmodel import Session, select


def seed_businesses():
    print("🌱 Creating Business-EOS profiles...")

    # Create tables
    create_db_and_tables()

    with Session(engine) as session:
        # Clear existing data
        print("🗑️  Clearing existing data...")
        for user in session.exec(select(UserAccount)).all():
            session.delete(user)
        for biz in session.exec(select(Business)).all():
            session.delete(biz)
        session.commit()

        # Define businesses with their configs
        businesses = [
            {
                "name": "McAlister's",
                "legal_name": "McAlister's LLC",
                "industry": "barbershop",
                "username": "mcalister",
                "password": "Password1",
                "modules": ["scheduler", "team", "assistant"],  # Scheduler only
            },
            {
                "name": "BAMS",
                "legal_name": "Boutique Artisan Markets & Sales",
                "industry": "retail",
                "username": "bams.manager",
                "password": "Password1",
                "modules": ["sales", "inventory", "assistant"],  # Sales + Inventory
            },
            {
                "name": "PupCuts",
                "legal_name": "PupCuts Grooming",
                "industry": "services",
                "username": "pupcuts",
                "password": "Password1",
                "modules": ["booking", "sales", "team", "assistant"],  # Sales + Booker
            },
        ]

        # Create each business
        for biz_config in businesses:
            print(f"\n📍 Setting up {biz_config['name']}...")

            # Create business
            business = Business(
                name=biz_config["name"],
                legal_name=biz_config["legal_name"],
                industry=biz_config["industry"],
                currency="USD",
                active=True,
            )
            session.add(business)
            session.flush()

            # Create user
            user = UserAccount(
                username=biz_config["username"],
                password_hash=hash_password(biz_config["password"]),
                role="manager",
                active=True,
            )
            session.add(user)
            session.flush()

            # Create membership
            membership = Membership(
                business_id=business.id,
                user_id=user.id,
                role="owner",
                active=True,
            )
            session.add(membership)
            session.flush()

            # Enable modules
            for module_key in biz_config["modules"]:
                module = BusinessModule(
                    business_id=business.id,
                    module_key=module_key,
                    enabled=True,
                )
                session.add(module)

            session.commit()

            print(f"  ✅ Business: {biz_config['name']}")
            print(f"  ✅ User: {biz_config['username']}")
            print(f"  ✅ Password: {biz_config['password']}")
            print(f"  ✅ Modules: {', '.join(biz_config['modules'])}")

        print("\n" + "="*60)
        print("🎉 SETUP COMPLETE!")
        print("="*60)
        print("\n📱 Login Credentials:")
        print("\n🏪 McAlister's (Barbershop - Scheduler only)")
        print("   Username: mcalister")
        print("   Password: Password1")
        print("\n🛍️  BAMS (Retail - Sales + Inventory)")
        print("   Username: bams.manager")
        print("   Password: Password1")
        print("\n🐕 PupCuts (Grooming - Sales + Booker)")
        print("   Username: pupcuts")
        print("   Password: Password1")
        print("\n" + "="*60)


if __name__ == "__main__":
    try:
        seed_businesses()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
