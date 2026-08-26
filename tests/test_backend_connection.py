import pytest

from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)


def test_get_user_by_id_valid(seeded_user_id):
    user = get_user_by_id(seeded_user_id)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert len(user["member_since"].split()) == 2  # "Month YYYY"


def test_get_user_by_id_missing(isolated_db):
    assert get_user_by_id(999999) is None


def test_get_summary_stats_with_expenses(seeded_user_id):
    stats = get_summary_stats(seeded_user_id)
    assert stats["total_spent"] == pytest.approx(5353.00)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Shopping"


def test_get_summary_stats_no_expenses(empty_user_id):
    stats = get_summary_stats(empty_user_id)
    assert stats["total_spent"] == 0
    assert stats["transaction_count"] == 0
    assert stats["top_category"] == "—"


def test_get_recent_transactions_ordered(seeded_user_id):
    txs = get_recent_transactions(seeded_user_id)
    assert len(txs) == 8
    dates = [t["date"] for t in txs]
    assert dates == sorted(dates, reverse=True)
    assert set(txs[0].keys()) == {"date", "description", "category", "amount"}


def test_get_recent_transactions_empty(empty_user_id):
    assert get_recent_transactions(empty_user_id) == []


def test_get_category_breakdown(seeded_user_id):
    cats = get_category_breakdown(seeded_user_id)
    assert len(cats) == 7
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    assert sum(c["pct"] for c in cats) == 100


def test_get_category_breakdown_empty(empty_user_id):
    assert get_category_breakdown(empty_user_id) == []


def test_profile_redirects_when_logged_out(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_authenticated(client, seeded_user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = seeded_user_id
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹" in body
    assert "5353.00" in body
    assert "Shopping" in body


def test_profile_new_user_zero_state(client, empty_user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = empty_user_id
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "0.00" in body
