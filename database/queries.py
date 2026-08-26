"""Pure DB query helpers for Spendly. No Flask imports here."""

from datetime import datetime

from database.db import get_db


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


def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT date, description, category, amount
        FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_summary_stats(user_id):
    conn = get_db()
    totals = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    top = conn.execute(
        """
        SELECT category, SUM(amount) AS cat_total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY cat_total DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    conn.close()

    return {
        "total_spent": totals["total"],
        "transaction_count": totals["cnt"],
        "top_category": top["category"] if top else "—",
    }


def get_category_breakdown(user_id):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT category, SUM(amount) AS cat_total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY cat_total DESC
        """,
        (user_id,),
    ).fetchall()
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
