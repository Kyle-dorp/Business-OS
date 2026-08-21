#!/usr/bin/env python3
"""
Admin script to provision a new tenant (Business + Location + Manager).

Usage:
    python provision_tenant.py

This script will prompt you for the business details and create a new tenant
with all necessary configuration.
"""

import os
import sys
from datetime import datetime, timezone

# Add the backend app to the path
sys.path.insert(0, os.path.dirname(__file__))

from backend.app.auth import hash_password, username_exists
from backend.app.database import create_db_and_tables, engine
from backend.app.models import (
    Business,
    BusinessModule,
    Location,
    ManagerSettings,
    Membership,
    UserAccount,
)
from sqlmodel import Session


def provision_tenant():
    """Interactively provision a new tenant."""
    print("\n" + "=" * 60)
    print("  TENANT PROVISIONING SCRIPT")
    print("=" * 60 + "\n")

    # Collect input
    business_name = input("Business name (e.g., 'Mile High Delis'): ").strip()
    location_name = input("Location name (e.g., 'South Broadway'): ").strip()
    store_name = input(
        "Store display name [default: same as location]: "
    ).strip() or location_name
    timezone = input("Timezone [default: America/Denver]: ").strip() or "America/Denver"
    manager_username = input("Manager username: ").strip()
    manager_password = input("Manager password: ").strip()

    # Validation
    if not business_name or not location_name or not manager_username or not manager_password:
        print("\n❌ Error: All fields are required.")
        return False

    if len(manager_username) < 3:
        print("\n❌ Error: Username must be at least 3 characters.")
        return False

    if len(manager_password) < 8:
        print("\n❌ Error: Password must be at least 8 characters.")
        return False

    if username_exists(manager_username):
        print(f"\n❌ Error: Username '{manager_username}' already exists.")
        return False

    # Ensure database tables exist
    create_db_and_tables()

    # Provision the tenant
    try:
        with Session(engine) as session:
            print("\n⏳ Creating business...")
            business = Business(
                name=business_name,
                legal_name="",
                industry="restaurant",
                currency="USD",
                active=True,
            )
            session.add(business)
            session.flush()

            print("⏳ Creating location...")
            location = Location(
                business_id=business.id,
                name=location_name,
                address="",
                timezone=timezone,
                active=True,
            )
            session.add(location)

            print("⏳ Creating manager account...")
            manager_user = UserAccount(
                username=manager_username,
                password_hash=hash_password(manager_password),
                role="manager",
                active=True,
            )
            session.add(manager_user)
            session.flush()

            print("⏳ Creating membership...")
            membership = Membership(
                business_id=business.id,
                user_id=manager_user.id,
                role="owner",
                active=True,
            )
            session.add(membership)

            print("⏳ Configuring manager settings...")
            manager_settings = ManagerSettings(
                business_id=business.id,
                store_name=store_name,
                employee_hourly_rate=18.20,
                shift_lead_hourly_rate=19.20,
                gm_hourly_rate=19.20,
                min_labor_percent=18.0,
                max_labor_percent=20.0,
                default_labor_percent=19.0,
                schedule_extra_with_trainee=True,
                store_open_time="10:30",
                store_close_time="21:00",
            )
            session.add(manager_settings)

            print("⏳ Enabling Scheduler module...")
            scheduler_module = BusinessModule(
                business_id=business.id,
                module_key="scheduler",
                enabled=True,
            )
            session.add(scheduler_module)

            session.commit()

            print("\n" + "=" * 60)
            print("  ✅ TENANT PROVISIONED SUCCESSFULLY")
            print("=" * 60)
            print(f"\nTenant Details:")
            print(f"  Business ID:        {business.id}")
            print(f"  Business Name:      {business.name}")
            print(f"  Location ID:        {location.id}")
            print(f"  Location Name:      {location.name}")
            print(f"  Manager ID:         {manager_user.id}")
            print(f"  Manager Username:   {manager_user.username}")
            print(f"  Timezone:           {timezone}")
            print(f"  Scheduler Enabled:  Yes")
            print("\n")

            return True

    except Exception as e:
        print(f"\n❌ Error provisioning tenant: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = provision_tenant()
    sys.exit(0 if success else 1)
