#!/usr/bin/env bash
#
# Create an administrator, or promote an existing account to one.
#
# Registration through the site always produces a `viewer`: register_user() hard-codes
# the role, and there is no bootstrap anywhere that mints the first administrator. So a
# fresh deployment has an admin area that nobody can open. This is that bootstrap.
#
#   sudo bash deploy/make-admin.sh you@example.com                  # promote, or create
#   sudo bash deploy/make-admin.sh you@example.com 'a-password'     # set the password too
#   sudo bash deploy/make-admin.sh you@example.com '' admin         # a plain admin
#
# Roles that open the admin area:
#
#   super_admin   everything, including changing other people's roles and deleting
#                 users, and the submitted-articles CSV export
#   admin         the admin pages -- users, audit log, models, analytics -- but not
#                 role changes, user deletion, or the export
#
# Passwords are hashed with the application's own hash_password(), so an account made
# here logs in exactly like one made through the site. If no password is given for a
# new account, one is generated and printed once.
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/somali-nlp}"
EMAIL="${1:-}"
PASSWORD="${2:-}"
ROLE="${3:-super_admin}"

[[ -n "$EMAIL" ]] || { echo "usage: sudo bash $0 you@example.com [password] [role]" >&2; exit 1; }
[[ -x "$APP_DIR/.venv/bin/python" ]] || { echo "no venv at $APP_DIR/.venv -- run setup-shared.sh first" >&2; exit 1; }

case "$ROLE" in
  super_admin|admin|analyst|researcher|viewer) ;;
  *) echo "role must be one of: super_admin admin analyst researcher viewer" >&2; exit 1 ;;
esac

cd "$APP_DIR/web"
EMAIL="$EMAIL" PASSWORD="$PASSWORD" ROLE="$ROLE" "$APP_DIR/.venv/bin/python" - <<'PY'
import os, secrets, sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
from backend.config import get_settings
from backend.utils.security import hash_password
from pymongo import MongoClient

settings = get_settings()
email = os.environ["EMAIL"].strip().lower()
password = os.environ["PASSWORD"]
role = os.environ["ROLE"]

db = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)[settings.mongo_db_name]
db.command("ping")

existing = db.users.find_one({"email": email})

if existing:
    updates = {"role": role, "is_active": True}
    if password:
        updates["password"] = hash_password(password)
    db.users.update_one({"email": email}, {"$set": updates})
    was = existing.get("role", "?")
    print(f"\n  promoted  {email}")
    print(f"  role      {was} -> {role}")
    if password:
        print("  password  reset to the one you supplied")
    else:
        print("  password  unchanged")
else:
    generated = ""
    if not password:
        # 24 bytes of urlsafe base64: long enough that it need not be memorable,
        # because it is printed here and then changed on the site.
        generated = secrets.token_urlsafe(18)
        password = generated
    # Same shape register_user() writes, so nothing downstream can tell the
    # difference between an account made here and one made through the site.
    # -1 is the unlimited sentinel used throughout ROLE_LIMITS.
    db.users.insert_one({
        "email": email,
        "name": "",
        "password": hash_password(password),
        "role": role,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "last_login": None,
        "daily_prediction_count": 0,
        "monthly_prediction_count": 0,
        "daily_prediction_limit": -1,
        "monthly_prediction_limit": -1,
        "max_text_length": -1,
        "last_count_reset": "",
        "last_month_reset": "",
    })
    print(f"\n  created   {email}")
    print(f"  role      {role}")
    if generated:
        print(f"  password  {generated}")
        print("            ^ shown once. Change it on the site after logging in.")
    else:
        print("  password  the one you supplied")

print()
print("  all accounts now:")
for u in db.users.find({}, {"email": 1, "role": 1, "is_active": 1}).sort("email", 1):
    state = "" if u.get("is_active", True) else "  (suspended)"
    print(f"    {u.get('role', '?'):<12} {u['email']}{state}")
print()
PY
