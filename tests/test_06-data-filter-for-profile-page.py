"""
Tests for Step 6: Date Filter for Profile Page.

Spec: .claude/specs/06-data-filter-for-profile-page.md

Scope (per spec, GET /profile only — no new routes):
- date_from / date_to query params, ISO "YYYY-MM-DD"
- absent/malformed params -> silent fallback to "All Time" (unfiltered)
- date_from > date_to -> flash-style error "Start date must be before end date."
  and fallback to unfiltered
- all three data sections (summary stats, recent transactions, category
  breakdown) must respect the active filter
- filtering must never leak another user's expenses

Fixture strategy:
This suite reuses `tests/conftest.py`'s existing fixtures rather than
redefining them:
  - `isolated_db`      -> points database.db.DATABASE at a fresh temp sqlite
                          file per test and creates tables (see conftest.py)
  - `app` / `client`   -> fresh `app` module import per test, running on the
                          isolated temp DB (conftest.py's `app` fixture pops
                          "app" from sys.modules and re-imports it, which also
                          re-runs app.py's module-level `seed_db()` against
                          the isolated DB — so a "Demo User" + 8 sample
                          expenses will always exist alongside whatever users
                          this file creates; queries are scoped by user_id so
                          this is harmless, but distinctive category names
                          are used here to avoid any ambiguous substring
                          matches against the seed data)

Login is done the same way test_backend_connection.py does it — writing
`user_id` directly into the session via `client.session_transaction()` —
since that's the session key the app actually uses (`session["user_id"]`)
and avoids coupling these tests to password hashing/login-form details that
are out of scope for this feature.

Route paths are hardcoded as string literals ("/profile", "/login") to match
the existing convention in tests/test_backend_connection.py, rather than
resolving them via `url_for()` (which would require extra app/request
context boilerplate not used elsewhere in this suite).
"""

from datetime import date, timedelta

from database.db import get_db

# ------------------------------------------------------------------ #
# Local test data helpers (not fixtures — plain functions so each test
# controls exactly which users/expenses/dates it needs).
# ------------------------------------------------------------------ #


def _create_user(email, name="Filter Test User"):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, "not-a-real-hash"),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def _create_expense(user_id, amount, category, expense_date, description=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    conn.close()


def _login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


ERROR_TEXT = "Start date must be before end date."


# ------------------------------------------------------------------ #
# Auth guard
# ------------------------------------------------------------------ #


class TestAuthGuard:
    def test_profile_with_filter_params_unauthenticated_redirects_to_login(self, client):
        """Query-string filtering must not bypass the existing login requirement."""
        resp = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31")
        assert resp.status_code == 302, "Expected redirect for unauthenticated request"
        assert "/login" in resp.headers["Location"], "Expected redirect target to be /login"


# ------------------------------------------------------------------ #
# No query params -> unfiltered ("All Time")
# ------------------------------------------------------------------ #


class TestUnfilteredView:
    def test_no_query_params_shows_all_expenses(self, client, isolated_db):
        user_id = _create_user("unfiltered@example.com")
        _create_expense(user_id, 100, "TESTCAT_OLD", "2020-01-01", "very old expense")
        _create_expense(user_id, 200, "TESTCAT_NEW", date.today().isoformat(), "today's expense")
        _login_as(client, user_id)

        resp = client.get("/profile")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "300.00" in body, "Expected unfiltered total (100 + 200) to include both expenses"
        assert "TESTCAT_OLD" in body, "Old expense's category should still appear when unfiltered"
        assert "TESTCAT_NEW" in body, "New expense's category should still appear when unfiltered"
        assert ERROR_TEXT not in body, "No error should be shown when no filter is applied"

    def test_no_query_params_matches_all_time_preset_clean_url(self, client, isolated_db):
        """Spec: 'The All Time preset must pass no query params (clean /profile URL)' —
        so a bare GET /profile must be indistinguishable from an explicit All Time click."""
        user_id = _create_user("alltime@example.com")
        _create_expense(user_id, 50, "TESTCAT_A", "2019-06-15", "ancient expense")
        _login_as(client, user_id)

        resp = client.get("/profile")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "50.00" in body
        assert "TESTCAT_A" in body


# ------------------------------------------------------------------ #
# Valid custom date range narrows all three sections
# ------------------------------------------------------------------ #


class TestValidDateRange:
    def test_valid_range_narrows_stats_transactions_and_categories(self, client, isolated_db):
        user_id = _create_user("rangeuser@example.com")
        _create_expense(user_id, 100, "TESTCAT_BEFORE", "2026-01-01", "before range")
        _create_expense(user_id, 250, "TESTCAT_MIDDLE", "2026-02-15", "inside range")
        _create_expense(user_id, 400, "TESTCAT_AFTER", "2026-03-30", "after range")
        _login_as(client, user_id)

        resp = client.get("/profile", query_string={"date_from": "2026-02-01", "date_to": "2026-02-28"})
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        # Summary stats: only the middle expense should count
        assert "250.00" in body, "Filtered total should equal only the in-range expense"
        assert "400.00" not in body, "Out-of-range expense amount should not appear"
        assert "100.00" not in body, "Out-of-range expense amount should not appear"
        # Recent transactions
        assert "TESTCAT_MIDDLE" in body
        assert "TESTCAT_BEFORE" not in body
        assert "TESTCAT_AFTER" not in body
        # Category breakdown: only the in-range category should show
        assert ERROR_TEXT not in body


# ------------------------------------------------------------------ #
# Partial params / malformed params / inverted range
# ------------------------------------------------------------------ #


class TestPartialAndMalformedParams:
    def test_only_date_from_present_treated_as_absent(self, client, isolated_db):
        user_id = _create_user("partial-from@example.com")
        _create_expense(user_id, 111, "TESTCAT_PARTIAL", "2020-05-05", "old")
        _login_as(client, user_id)

        resp = client.get("/profile", query_string={"date_from": "2026-01-01"})
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "111.00" in body, "A lone date_from must not filter anything out"
        assert ERROR_TEXT not in body

    def test_only_date_to_present_treated_as_absent(self, client, isolated_db):
        user_id = _create_user("partial-to@example.com")
        _create_expense(user_id, 222, "TESTCAT_PARTIAL2", "2020-05-05", "old")
        _login_as(client, user_id)

        resp = client.get("/profile", query_string={"date_to": "2026-01-01"})
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "222.00" in body, "A lone date_to must not filter anything out"
        assert ERROR_TEXT not in body

    def test_malformed_date_string_falls_back_silently_without_crashing(self, client, isolated_db):
        user_id = _create_user("malformed@example.com")
        _create_expense(user_id, 333, "TESTCAT_MALFORMED", "2020-05-05", "old")
        _login_as(client, user_id)

        resp = client.get(
            "/profile",
            query_string={"date_from": "not-a-date", "date_to": "2026-08-10"},
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200, "Malformed date must not cause a 500/crash"
        assert "333.00" in body, "Malformed filter must fall back to unfiltered data"
        assert ERROR_TEXT not in body, "Malformed date is a silent fallback, not the ordering error"

    def test_date_from_after_date_to_shows_error_and_falls_back(self, client, isolated_db):
        user_id = _create_user("inverted@example.com")
        _create_expense(user_id, 444, "TESTCAT_INVERTED", "2020-05-05", "old")
        _login_as(client, user_id)

        resp = client.get(
            "/profile",
            query_string={"date_from": "2026-08-20", "date_to": "2026-08-10"},
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert ERROR_TEXT in body, "Inverted range must surface the exact spec error message"
        assert "444.00" in body, "After an inverted range, data must fall back to unfiltered"


# ------------------------------------------------------------------ #
# Quick-select presets
# ------------------------------------------------------------------ #


class TestPresets:
    def test_this_month_preset_filters_to_current_calendar_month(self, client, isolated_db):
        today = date.today()
        first_of_month = today.replace(day=1)
        last_month_day = first_of_month - timedelta(days=1)

        user_id = _create_user("thismonth@example.com")
        _create_expense(user_id, 60, "TESTCAT_THISMONTH", today.isoformat(), "in current month")
        _create_expense(user_id, 90, "TESTCAT_LASTMONTH", last_month_day.isoformat(), "previous month")
        _login_as(client, user_id)

        resp = client.get(
            "/profile",
            query_string={
                "date_from": first_of_month.isoformat(),
                "date_to": today.isoformat(),
            },
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "60.00" in body, "Current-month expense should be included"
        assert "TESTCAT_LASTMONTH" not in body, "Previous month's expense should be excluded"

    def test_last_3_months_preset_filters_recent_window(self, client, isolated_db):
        today = date.today()
        recent = today - timedelta(days=30)
        # 150 days is well past any reasonable "3 months" cutoff (~89-92 days)
        stale = today - timedelta(days=150)

        user_id = _create_user("last3months@example.com")
        _create_expense(user_id, 70, "TESTCAT_RECENT3", recent.isoformat(), "within 3 months")
        _create_expense(user_id, 80, "TESTCAT_STALE3", stale.isoformat(), "older than 3 months")
        _login_as(client, user_id)

        resp = client.get(
            "/profile",
            query_string={
                "date_from": (today - timedelta(days=90)).isoformat(),
                "date_to": today.isoformat(),
            },
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "70.00" in body, "Expense within the last 3 months should be included"
        assert "TESTCAT_STALE3" not in body, "Expense older than 3 months should be excluded"

    def test_last_6_months_preset_filters_recent_window(self, client, isolated_db):
        today = date.today()
        recent = today - timedelta(days=60)
        # 250 days is well past any reasonable "6 months" cutoff (~180-184 days)
        stale = today - timedelta(days=250)

        user_id = _create_user("last6months@example.com")
        _create_expense(user_id, 55, "TESTCAT_RECENT6", recent.isoformat(), "within 6 months")
        _create_expense(user_id, 65, "TESTCAT_STALE6", stale.isoformat(), "older than 6 months")
        _login_as(client, user_id)

        resp = client.get(
            "/profile",
            query_string={
                "date_from": (today - timedelta(days=180)).isoformat(),
                "date_to": today.isoformat(),
            },
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "55.00" in body, "Expense within the last 6 months should be included"
        assert "TESTCAT_STALE6" not in body, "Expense older than 6 months should be excluded"

    def test_all_time_preset_shows_everything(self, client, isolated_db):
        user_id = _create_user("alltimepreset@example.com")
        _create_expense(user_id, 10, "TESTCAT_ANCIENT", "2010-01-01", "ancient")
        _create_expense(user_id, 20, "TESTCAT_TODAY", date.today().isoformat(), "today")
        _login_as(client, user_id)

        # "All Time" preset link passes no query params at all (clean /profile URL)
        resp = client.get("/profile")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "30.00" in body, "All Time must include every expense regardless of age"


# ------------------------------------------------------------------ #
# Edge cases: empty range, cross-user leakage
# ------------------------------------------------------------------ #


class TestEdgeCases:
    def test_no_expenses_in_selected_range_returns_zeroed_stats_without_error(self, client, isolated_db):
        user_id = _create_user("zerorange@example.com")
        _create_expense(user_id, 500, "TESTCAT_OUTSIDE", date.today().isoformat(), "outside the query window")
        _login_as(client, user_id)

        resp = client.get(
            "/profile",
            query_string={"date_from": "2000-01-01", "date_to": "2000-01-02"},
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200, "Empty result range must not error out"
        assert "0.00" in body, "Zero-result range should show a zeroed total (₹0.00 per spec)"
        assert "₹" in body, "Currency symbol must still be present even with zero results"
        assert "TESTCAT_OUTSIDE" not in body, "Expense outside the range must not be listed"

    def test_unfiltered_view_never_leaks_other_users_expenses(self, client, isolated_db):
        user_a = _create_user("alpha@example.com", name="User Alpha")
        user_b = _create_user("bravo@example.com", name="User Bravo")
        _create_expense(user_a, 100, "TESTCAT_ALPHA_ONLY", date.today().isoformat(), "alpha's expense")
        _create_expense(user_b, 999, "TESTCAT_BRAVO_ONLY", date.today().isoformat(), "bravo's expense")

        _login_as(client, user_a)
        resp = client.get("/profile")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "100.00" in body
        assert "999.00" not in body, "User A must never see User B's amounts"
        assert "TESTCAT_BRAVO_ONLY" not in body, "User A must never see User B's categories"

    def test_filtered_view_never_leaks_other_users_expenses(self, client, isolated_db):
        """A wide date filter that would technically cover both users' expenses
        must still be scoped to the logged-in user only."""
        user_a = _create_user("alpha2@example.com", name="User Alpha 2")
        user_b = _create_user("bravo2@example.com", name="User Bravo 2")
        shared_date = date.today().isoformat()
        _create_expense(user_a, 150, "TESTCAT_ALPHA2_ONLY", shared_date, "alpha's expense")
        _create_expense(user_b, 777, "TESTCAT_BRAVO2_ONLY", shared_date, "bravo's expense")

        _login_as(client, user_a)
        resp = client.get(
            "/profile",
            query_string={"date_from": "2000-01-01", "date_to": "2100-01-01"},
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "150.00" in body
        assert "777.00" not in body, "A wide date filter must not leak User B's amounts"
        assert "TESTCAT_BRAVO2_ONLY" not in body, "A wide date filter must not leak User B's categories"
