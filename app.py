import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = "dev"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not name or "@" not in email or "." not in email.split("@")[-1] or len(password) < 8:
        return render_template(
            "register.html",
            error="Please check your details and try again.",
        )

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return render_template(
            "register.html",
            error="An account with that email already exists.",
        )
    finally:
        conn.close()

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    conn = get_db()
    user = conn.execute(
        "SELECT id, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Anjali Mehta",
        "email": "anjali.mehta@example.com",
        "initials": "AM",
        "member_since": "March 2025",
    }
    stats = {
        "total_spent": 18450.00,
        "transaction_count": 42,
        "top_category": "Food",
    }
    transactions = [
        {"date": "2026-08-24", "description": "Dinner with friends", "category": "Food", "amount": 275.00},
        {"date": "2026-08-19", "description": "Miscellaneous", "category": "Other", "amount": 120.00},
        {"date": "2026-08-15", "description": "New shoes", "category": "Shopping", "amount": 1999.00},
        {"date": "2026-08-12", "description": "Pharmacy", "category": "Health", "amount": 350.00},
        {"date": "2026-08-08", "description": "Movie night", "category": "Entertainment", "amount": 899.00},
        {"date": "2026-08-05", "description": "Electricity bill", "category": "Bills", "amount": 1200.00},
    ]
    categories = [
        {"name": "Food", "total": 7250.00, "percent": 39},
        {"name": "Bills", "total": 4100.00, "percent": 22},
        {"name": "Shopping", "total": 3200.00, "percent": 17},
        {"name": "Entertainment", "total": 2100.00, "percent": 11},
        {"name": "Health", "total": 1800.00, "percent": 10},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
