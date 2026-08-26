import sys

import pytest

from database import db as db_module


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Point database.db.DATABASE at a fresh temp sqlite file and create tables."""
    monkeypatch.setattr(db_module, "DATABASE", str(tmp_path / "test_spendly.db"))
    db_module.init_db()
    yield


@pytest.fixture()
def seeded_user_id(isolated_db):
    db_module.seed_db()
    conn = db_module.get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)).fetchone()
    conn.close()
    return row["id"]


@pytest.fixture()
def empty_user_id(isolated_db):
    conn = db_module.get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("No Expenses", "no-expenses@example.com", "x"),
    )
    conn.commit()
    conn.close()
    return cursor.lastrowid


@pytest.fixture()
def app(isolated_db):
    sys.modules.pop("app", None)
    import app as app_module
    app_module.app.config.update(TESTING=True)
    yield app_module.app
    sys.modules.pop("app", None)


@pytest.fixture()
def client(app):
    return app.test_client()
