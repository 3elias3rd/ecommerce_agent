"""
Run this script to generate the AUTH_USERS value for your .env file.

Usage:
    python scripts/generate_auth_users.py

Then copy the output into your .env as:
    AUTH_USERS=<output>

And set in Koyeb environment variables as:
    AUTH_USERS=<output>
"""

import json
import bcrypt

# ── Define your test users here ───────────────────────────────
# Format: {"username": "plaintext_password"}
# Change these before running!
USERS = {
    "user_1": "password123",
    "user_2": "password456",
    "user_3": "password789",
    "user_4": "password101",
    "user_5": "password112"
}

# ──────────────────────────────────────────────────────────────

def main():
    hashed = {
        username: bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        for username, password in USERS.items()
    }
    output = json.dumps(hashed)
    print("\n✅ Copy this into your .env or Koyeb environment variables:\n")
    print(f'AUTH_USERS={output}')
    print()

if __name__ == "__main__":
    main()


