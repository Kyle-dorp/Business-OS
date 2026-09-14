#!/usr/bin/env python
"""
Make an existing user a platform admin.

    python scripts/grant_admin.py <username>
    python scripts/grant_admin.py <username> --revoke
    python scripts/grant_admin.py --list

Platform admin is the account that can read every workspace through /admin/*:
every customer's name, plan, spend and module list. That is not a grant an
HTTP endpoint should be able to hand out, so this runs against the database
directly and needs whatever access the database needs.

It replaces /auth/seed-businesses, which was public, guarded only by a header
string committed to a public repository, deleted every user and every business
in the database, and then created an admin account with a hardcoded password.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

# Run as `python scripts/grant_admin.py`, sys.path[0] is scripts/, not the
# repository root, so `backend.app...` would not resolve.
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Grant or revoke platform admin.")
    parser.add_argument("username", nargs="?", help="the account to change")
    parser.add_argument("--revoke", action="store_true", help="remove admin instead of granting it")
    parser.add_argument("--list", action="store_true", help="show the current platform admins")
    args = parser.parse_args()

    from sqlmodel import Session, select

    from backend.app.database import engine
    from backend.app.models import UserAccount

    with Session(engine) as session:
        if args.list:
            admins = session.exec(
                select(UserAccount).where(UserAccount.is_admin == True)  # noqa: E712
            ).all()
            if not admins:
                print("No platform admins.")
                return 0
            print(f"{len(admins)} platform admin(s):")
            for user in admins:
                state = "" if user.active else "  (inactive)"
                print(f"  {user.username}{state}")
            return 0

        if not args.username:
            parser.error("a username is required unless --list is given")

        user = session.exec(
            select(UserAccount).where(UserAccount.username == args.username)
        ).first()
        if not user:
            print(f"No account named {args.username!r}.", file=sys.stderr)
            print("Create the account through normal signup first, then run this.",
                  file=sys.stderr)
            return 1

        wanted = not args.revoke
        if user.is_admin == wanted:
            print(f"{user.username} is already {'an admin' if wanted else 'not an admin'}.")
            return 0

        # Never leave the platform with no way in. Revoking the last admin means
        # /admin/* becomes unreachable for everybody, and the only way back is
        # this script plus database access.
        if args.revoke:
            others = session.exec(
                select(UserAccount).where(
                    UserAccount.is_admin == True,  # noqa: E712
                    UserAccount.id != user.id,
                    UserAccount.active == True,  # noqa: E712
                )
            ).all()
            if not others:
                print(f"{user.username} is the only platform admin. Grant it to "
                      "somebody else first.", file=sys.stderr)
                return 1

        user.is_admin = wanted
        session.add(user)
        session.commit()

    verb = "revoked from" if args.revoke else "granted to"
    print(f"Platform admin {verb} {args.username}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
