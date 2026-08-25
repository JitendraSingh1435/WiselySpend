import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.security import generate_password_hash

from database.db import get_db

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Rohan", "Karan", "Siddharth", "Arjun",
    "Rahul", "Amit", "Vikram", "Ananya", "Priya", "Sneha", "Neha", "Pooja",
    "Divya", "Kavya", "Meera", "Isha", "Riya", "Farhan", "Imran", "Zoya",
    "Ayesha", "Manpreet", "Harpreet", "Gurpreet", "Suresh", "Ramesh",
    "Lakshmi", "Deepika", "Nikhil", "Sanjay", "Anjali", "Shreya",
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Mehta", "Patel", "Shah", "Reddy", "Rao",
    "Nair", "Menon", "Iyer", "Iyengar", "Chatterjee", "Banerjee", "Mukherjee",
    "Das", "Kapoor", "Malhotra", "Chopra", "Khanna", "Singh", "Kaur",
    "Bhat", "Joshi", "Deshmukh", "Kulkarni", "Pillai", "Agarwal", "Bose",
    "Chauhan",
]

EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com"]


def generate_user():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    number = random.randint(10, 999)
    domain = random.choice(EMAIL_DOMAINS)
    email = f"{first.lower()}.{last.lower()}{number}@{domain}"
    return name, email


def main():
    conn = get_db()
    try:
        while True:
            name, email = generate_user()
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if not existing:
                break

        password_hash = generate_password_hash("password123")
        created_at = datetime.now().isoformat(sep=" ", timespec="seconds")

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, created_at),
        )
        conn.commit()
        user_id = cursor.lastrowid

        print("User seeded successfully:")
        print(f"  id:    {user_id}")
        print(f"  name:  {name}")
        print(f"  email: {email}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
