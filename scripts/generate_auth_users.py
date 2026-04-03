"""
Run this script to generate AUTH_USER_N / AUTH_PASS_N values for your environment.

Usage:
    python scripts/generate_auth_users.py

Then set each line as a separate environment variable in Koyeb
(or copy all lines into your .env file for local use).
"""

import bcrypt

# ── Define your users here ────────────────────────────────────
# Format: {"username": "plaintext_password"}
# Change these before running!
USERS = {
    "user_1": "password123",
    "user_2": "password456",
    "user_3": "password789",
    "user_4": "password101",
    "user_5": "password112"
}

# ─────────────────────────────────────────────────────────────

def main():
    print("\n✅ Set these as individual environment variables in Koyeb:\n")
    for i, (username, password) in enumerate(USERS.items(), start=1):
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        print(f"AUTH_USER_{i}={username}")
        print(f"AUTH_PASS_{i}={hashed}")
        print()

if __name__ == "__main__":
    main()
    