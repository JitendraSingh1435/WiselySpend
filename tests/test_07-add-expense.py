"""
Tests for Step 7: Add Expense.

Spec: .claude/specs/07-add-expense.md

Scope (per spec):
- GET /expenses/add and POST /expenses/add are logged-in only; unauthenticated
  requests to either must redirect to /login.
- GET /expenses/add (authenticated) renders a form with:
    - a category <select> containing exactly the 7 fixed categories
    - a <form ...> with method POST
- POST /expenses/add (authenticated) validates:
    - amount: required, must parse as float() and be > 0
    - category: required, must be one of the 7 fixed categories
    - date: required, must be a valid YYYY-MM-DD date
    - description: optional; blank/whitespace-only -> stored as NULL
  On any validation failure the form is re-rendered (200) with an error
  message and the previously submitted values retained. On success the
  request redirects (302) to /profile and a new row is inserted for the
  current user.
- `insert_expense(user_id, amount, category, date, description)` in
  database/queries.py is a thin, parameterised INSERT helper; unit-tested
  directly against the DB (bypassing Flask) for both a fully-populated row
  and a `description=None` row.

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
                          this file creates; every DB assertion in this file
                          scopes by user_id, and route tests use a
                          freshly-created user with zero pre-existing
                          expenses, so the seeded rows never interfere)

Login is done the same way test_backend_connection.py / test_06 do it —
writing `user_id` directly into the session via `client.session_transaction()`
— since that's the session key the app actually uses (`session["user_id"]`)
and avoids coupling these tests to password hashing/login-form details that
are out of scope for this feature.

Route paths are hardcoded as string literals ("/expenses/add", "/profile",
"/login") to match the existing convention in this test suite, rather than
resolving them via `url_for()`.
"""

from database.db import get_db
from database.queries import insert_expense

ALLOWED_CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

# ------------------------------------------------------------------ #
# Local test data helpers (not fixtures — plain functions so each test
# controls exactly which users/expenses/dates it needs).
# ------------------------------------------------------------------ #


def _create_user(email, name="Add Expense Test User"):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, "not-a-real-hash"),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def _login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _expenses_for_user(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, user_id, amount, category, date, description FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ------------------------------------------------------------------ #
# Unit tests: database/queries.py::insert_expense
# ------------------------------------------------------------------ #


class TestInsertExpenseUnit:
    def test_insert_expense_valid_row_is_persisted(self, isolated_db):
        user_id = _create_user("insert-valid@example.com")

        insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

        rows = _expenses_for_user(user_id)
        assert len(rows) == 1, "Expected exactly one row to be inserted"
        row = rows[0]
        assert row["user_id"] == user_id
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_insert_expense_with_description_none_stores_null(self, isolated_db):
        user_id = _create_user("insert-null-desc@example.com")

        insert_expense(user_id, 25.5, "Transport", "2026-04-01", None)

        rows = _expenses_for_user(user_id)
        assert len(rows) == 1, "Expected exactly one row to be inserted"
        assert rows[0]["description"] is None, "description=None must be stored as NULL, not a string"


# ------------------------------------------------------------------ #
# Auth guards
# ------------------------------------------------------------------ #


class TestAuthGuard:
    def test_get_add_expense_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/expenses/add")
        assert resp.status_code == 302, "Unauthenticated GET must redirect, not render the form"
        assert "/login" in resp.headers["Location"]

    def test_post_add_expense_unauthenticated_redirects_to_login(self, client):
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food", "date": "2026-03-20", "description": "Lunch"},
        )
        assert resp.status_code == 302, "Unauthenticated POST must redirect, not insert a row"
        assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# GET /expenses/add — authenticated happy path (form rendering)
# ------------------------------------------------------------------ #


class TestGetAddExpenseAuthenticated:
    def test_get_add_expense_authenticated_returns_200(self, client, isolated_db):
        user_id = _create_user("get-form@example.com")
        _login_as(client, user_id)

        resp = client.get("/expenses/add")

        assert resp.status_code == 200

    def test_get_add_expense_form_contains_all_seven_categories(self, client, isolated_db):
        user_id = _create_user("get-categories@example.com")
        _login_as(client, user_id)

        resp = client.get("/expenses/add")
        body = resp.get_data(as_text=True)

        assert "<select" in body, "Expected a <select> element for category"
        for category in ALLOWED_CATEGORIES:
            assert category in body, f"Expected category option '{category}' in the form"

    def test_get_add_expense_form_has_post_method(self, client, isolated_db):
        user_id = _create_user("get-form-method@example.com")
        _login_as(client, user_id)

        resp = client.get("/expenses/add")
        body = resp.get_data(as_text=True)

        assert "<form" in body, "Expected a <form> element"
        assert "POST" in body.upper(), "Expected the form to submit via POST"


# ------------------------------------------------------------------ #
# POST /expenses/add — authenticated happy path
# ------------------------------------------------------------------ #


class TestPostAddExpenseValid:
    def test_post_valid_data_redirects_to_profile(self, client, isolated_db):
        user_id = _create_user("post-valid@example.com")
        _login_as(client, user_id)

        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food", "date": "2026-03-20", "description": "Lunch"},
        )

        assert resp.status_code == 302
        assert "/profile" in resp.headers["Location"]

    def test_post_valid_data_inserts_row_for_current_user(self, client, isolated_db):
        user_id = _create_user("post-valid-db@example.com")
        _login_as(client, user_id)

        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food", "date": "2026-03-20", "description": "Lunch"},
        )

        rows = _expenses_for_user(user_id)
        assert len(rows) == 1, "Expected the new expense to be inserted for this user"
        row = rows[0]
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_post_without_description_redirects_to_profile(self, client, isolated_db):
        user_id = _create_user("post-no-desc@example.com")
        _login_as(client, user_id)

        resp = client.post(
            "/expenses/add",
            data={"amount": "75.0", "category": "Bills", "date": "2026-05-01", "description": ""},
        )

        assert resp.status_code == 302
        assert "/profile" in resp.headers["Location"]

    def test_post_without_description_stores_null(self, client, isolated_db):
        user_id = _create_user("post-no-desc-db@example.com")
        _login_as(client, user_id)

        client.post(
            "/expenses/add",
            data={"amount": "75.0", "category": "Bills", "date": "2026-05-01", "description": ""},
        )

        rows = _expenses_for_user(user_id)
        assert len(rows) == 1
        assert rows[0]["description"] is None, "Blank description must be stored as NULL"


# ------------------------------------------------------------------ #
# POST /expenses/add — validation errors
# ------------------------------------------------------------------ #


class TestPostAddExpenseValidation:
    def test_post_missing_amount_rerenders_form_with_error(self, client, isolated_db):
        user_id = _create_user("missing-amount@example.com")
        _login_as(client, user_id)

        resp = client.post(
            "/expenses/add",
            data={"amount": "", "category": "Food", "date": "2026-03-20", "description": "Lunch"},
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200, "Validation failure must re-render the form, not redirect"
        assert "error" in body.lower(), "Expected an error message in the re-rendered form"
        assert _expenses_for_user(user_id) == [], "No row should be inserted on validation failure"

    def test_post_zero_amount_rerenders_form_with_error(self, client, isolated_db):
        user_id = _create_user("zero-amount@example.com")
        _login_as(client, user_id)

        resp = client.post(
            "/expenses/add",
            data={"amount": "0", "category": "Food", "date": "2026-03-20", "description": "Lunch"},
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "error" in body.lower(), "Expected an error message for a zero amount"
        assert _expenses_for_user(user_id) == [], "No row should be inserted for a zero amount"

    def test_post_non_numeric_amount_rerenders_form_with_error(self, client, isolated_db):
        user_id = _create_user("non-numeric-amount@example.com")
        _login_as(client, user_id)

        resp = client.post(
            "/expenses/add",
            data={"amount": "not-a-number", "category": "Food", "date": "2026-03-20", "description": "Lunch"},
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "error" in body.lower(), "Expected an error message for a non-numeric amount"
        assert _expenses_for_user(user_id) == [], "No row should be inserted for a non-numeric amount"

    def test_post_invalid_category_rerenders_form_with_error(self, client, isolated_db):
        user_id = _create_user("invalid-category@example.com")
        _login_as(client, user_id)

        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "NotARealCategory", "date": "2026-03-20", "description": "Lunch"},
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "error" in body.lower(), "Expected an error message for an invalid category"
        assert _expenses_for_user(user_id) == [], "No row should be inserted for an invalid category"

    def test_post_invalid_date_rerenders_form_with_error(self, client, isolated_db):
        user_id = _create_user("invalid-date@example.com")
        _login_as(client, user_id)

        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food", "date": "not-a-date", "description": "Lunch"},
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "error" in body.lower(), "Expected an error message for a malformed date"
        assert _expenses_for_user(user_id) == [], "No row should be inserted for an invalid date"

    def test_post_validation_error_retains_previously_submitted_values(self, client, isolated_db):
        """Definition of done: 'previously entered values retained' on a validation error."""
        user_id = _create_user("retain-values@example.com")
        _login_as(client, user_id)

        resp = client.post(
            "/expenses/add",
            data={"amount": "", "category": "Bills", "date": "2026-07-04", "description": "Rent"},
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "Bills" in body, "Previously selected category should remain pre-filled"
        assert "2026-07-04" in body, "Previously entered date should remain pre-filled"
        assert "Rent" in body, "Previously entered description should remain pre-filled"
