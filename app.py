import calendar
import math
import sqlite3
from datetime import date, datetime

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db
from database.queries import (
    delete_expense as delete_expense_row,
    get_category_breakdown,
    get_expense_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
    insert_expense,
    update_expense,
)

app = Flask(__name__)
app.secret_key = "dev"

ALLOWED_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]
INVALID_AMOUNT_ERROR = "Enter a valid amount greater than 0."
DESCRIPTION_MAX_LENGTH = 200

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


def _months_before(d, months):
    total = d.month - 1 - months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _date_presets():
    today = date.today()
    return {
        "this_month": (today.replace(day=1).isoformat(), today.isoformat()),
        "last_3_months": (_months_before(today, 3).isoformat(), today.isoformat()),
        "last_6_months": (_months_before(today, 6).isoformat(), today.isoformat()),
        "all_time": (None, None),
    }


def _parse_date_range(args):
    raw_from = args.get("date_from")
    raw_to = args.get("date_to")

    if not (raw_from and raw_to):
        return None, None, None

    try:
        parsed_from = datetime.strptime(raw_from, "%Y-%m-%d").date()
        parsed_to = datetime.strptime(raw_to, "%Y-%m-%d").date()
    except ValueError:
        return None, None, None

    if parsed_from > parsed_to:
        return None, None, "Start date must be before end date."

    return parsed_from.isoformat(), parsed_to.isoformat(), None


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    presets = _date_presets()
    date_from, date_to, error = _parse_date_range(request.args)

    active_preset = None
    for name, (preset_from, preset_to) in presets.items():
        if preset_from == date_from and preset_to == date_to:
            active_preset = name
            break
    else:
        # No preset matched (loop completed without a break) — a genuine custom range.
        if date_from and date_to:
            active_preset = "custom"

    user = get_user_by_id(user_id)
    stats = get_summary_stats(user_id, date_from, date_to)
    transactions = get_recent_transactions(user_id, date_from=date_from, date_to=date_to)
    categories = [
        {"name": c["name"], "total": c["amount"], "percent": c["pct"]}
        for c in get_category_breakdown(user_id, date_from, date_to)
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        presets=presets,
        active_preset=active_preset,
        date_from=date_from,
        date_to=date_to,
        error=error,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    return render_template("analytics.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

def _validate_expense_form(amount_raw, category, date_raw):
    """Returns (amount, error) — amount is None when error is set."""
    try:
        amount = float(amount_raw)
    except ValueError:
        return None, INVALID_AMOUNT_ERROR
    if not math.isfinite(amount) or amount <= 0:
        return None, INVALID_AMOUNT_ERROR

    if category not in ALLOWED_CATEGORIES:
        return None, "Please select a valid category."

    try:
        datetime.strptime(date_raw, "%Y-%m-%d")
    except ValueError:
        return None, "Enter a valid date."

    return amount, None


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=ALLOWED_CATEGORIES,
            amount="",
            category="",
            date=date.today().isoformat(),
            description="",
            error=None,
        )

    amount_raw = request.form.get("amount", "")
    category = request.form.get("category", "")
    date_raw = request.form.get("date", "")
    description_raw = request.form.get("description", "")

    def render_error(message):
        return render_template(
            "add_expense.html",
            categories=ALLOWED_CATEGORIES,
            amount=amount_raw,
            category=category,
            date=date_raw,
            description=description_raw,
            error=message,
        )

    amount, error = _validate_expense_form(amount_raw, category, date_raw)
    if error:
        return render_error(error)

    description = description_raw.strip()[:DESCRIPTION_MAX_LENGTH] or None

    insert_expense(session["user_id"], amount, category, date_raw, description)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "edit_expense.html",
            expense=expense,
            categories=ALLOWED_CATEGORIES,
            amount=expense["amount"],
            category=expense["category"],
            date=expense["date"],
            description=expense["description"] or "",
            error=None,
        )

    amount_raw = request.form.get("amount", "")
    category = request.form.get("category", "")
    date_raw = request.form.get("date", "")
    description_raw = request.form.get("description", "")

    def render_error(message):
        return render_template(
            "edit_expense.html",
            expense=expense,
            categories=ALLOWED_CATEGORIES,
            amount=amount_raw,
            category=category,
            date=date_raw,
            description=description_raw,
            error=message,
        )

    amount, error = _validate_expense_form(amount_raw, category, date_raw)
    if error:
        return render_error(error)

    description = description_raw.strip()[:DESCRIPTION_MAX_LENGTH] or None
    update_expense(id, user_id, amount, category, date_raw, description)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    delete_expense_row(id, user_id)
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
