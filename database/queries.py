"""Pure DB query helpers for Spendly. No Flask imports here."""

from datetime import datetime

from database.db import get_db


def _date_range_clause(date_from, date_to):
    return " AND date BETWEEN ? AND ?" if date_from and date_to else ""


def _date_range_params(date_from, date_to):
    return [date_from, date_to] if date_from and date_to else []


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    created_at = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    initials = "".join(part[0].upper() for part in row["name"].split()[:2]) or "?"

    return {
        "name": row["name"],
        "email": row["email"],
        "initials": initials,
        "member_since": created_at.strftime("%B %Y"),
    }


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    conn = get_db()
    query = """
        SELECT id, date, description, category, amount
        FROM expenses
        WHERE user_id = ?
    """
    query += _date_range_clause(date_from, date_to)
    query += " ORDER BY date DESC, id DESC LIMIT ?"
    params = [user_id] + _date_range_params(date_from, date_to)
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_expense_by_id(expense_id, user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, user_id, amount, category, date, description "
        "FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_summary_stats(user_id, date_from=None, date_to=None):
    conn = get_db()

    totals_query = "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt FROM expenses WHERE user_id = ?"
    top_query = """
        SELECT category, SUM(amount) AS cat_total
        FROM expenses
        WHERE user_id = ?
    """
    clause = _date_range_clause(date_from, date_to)
    totals_query += clause
    top_query += clause
    top_query += " GROUP BY category ORDER BY cat_total DESC LIMIT 1"
    params = [user_id] + _date_range_params(date_from, date_to)

    totals = conn.execute(totals_query, params).fetchone()
    top = conn.execute(top_query, params).fetchone()
    conn.close()

    return {
        "total_spent": totals["total"],
        "transaction_count": totals["cnt"],
        "top_category": top["category"] if top else "—",
    }


def insert_expense(user_id, amount, category, expense_date, description):
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    conn.close()


def update_expense(expense_id, user_id, amount, category, expense_date, description):
    conn = get_db()
    conn.execute(
        "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
        "WHERE id = ? AND user_id = ?",
        (amount, category, expense_date, description, expense_id, user_id),
    )
    conn.commit()
    conn.close()


def delete_expense(expense_id, user_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    )
    conn.commit()
    conn.close()


def get_category_breakdown(user_id, date_from=None, date_to=None):
    conn = get_db()
    query = """
        SELECT category, SUM(amount) AS cat_total
        FROM expenses
        WHERE user_id = ?
    """
    query += _date_range_clause(date_from, date_to)
    query += " GROUP BY category ORDER BY cat_total DESC"
    params = [user_id] + _date_range_params(date_from, date_to)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        return []

    grand_total = sum(row["cat_total"] for row in rows)
    percentages = [round(row["cat_total"] / grand_total * 100) for row in rows]
    percentages[0] += 100 - sum(percentages)  # largest category absorbs rounding remainder

    return [
        {"name": row["category"], "amount": row["cat_total"], "pct": pct}
        for row, pct in zip(rows, percentages)
    ]
