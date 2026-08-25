# Spec: Login and Logout

## Overview
Implements session-based authentication for Spendly. Right now `/login` (`app.py`) only renders `templates/login.html` on GET — the form posts to `/login` but there is no `POST` handler, so no credentials are ever checked and no session is created. `/logout` is a placeholder returning the plain string `"Logout — coming in Step 3"`. This step adds real sign-in (verify email/password against the `users` table, establish a Flask session) and real sign-out (clear the session), plus a nav that reflects whether a visitor is logged in. This gives later steps (profile, expense CRUD) a session to read "the current user" from.

## Depends on
- Step 1 — Database setup (`database/db.py` with working `get_db()`/`init_db()`/`users` table). Complete.
- Step 2 — Registration (`POST /register` creates hashed-password rows in `users`). Complete.

## Routes
- `POST /login` – validate submitted email/password against `users`, verify the password hash, set `session["user_id"]`, redirect to `/` on success or re-render `login.html` with an error on failure — public
- `GET /login` – already implemented, unchanged
- `GET /logout` – replace the placeholder: clear the session and redirect to `/` — logged-in (safe to hit while logged out too; it just becomes a no-op redirect)

## Database changes
No database changes. `users` table (`database/db.py`) already has `email` (UNIQUE) and `password_hash`. Use `get_db()` and `SELECT id, password_hash FROM users WHERE email = ?`, then `werkzeug.security.check_password_hash`.

## Templates
- Create: none
- Modify: `templates/base.html` — the `<nav>` currently always shows "Sign in" / "Get started". Make it conditional on `session`: logged out keeps the current two links; logged in shows a link to `/profile` and a link to `/logout` instead. `login.html` and `register.html` need no changes (their forms/markup already work).

## Files to change
- `app.py` —
  - Set `app.secret_key` (a fixed dev string is fine — there's no env-based config in this project yet) so Flask sessions work.
  - Replace the GET-only `login()` view with one that also handles `POST`: read `email`/`password`, look up the user, verify with `check_password_hash`, set `session["user_id"]` and redirect to `url_for("landing")` on success, or re-render `login.html` with a generic error ("Invalid email or password.") on any failure — do not reveal whether the email exists.
  - Replace the `logout()` placeholder: `session.pop("user_id", None)` then redirect to `url_for("landing")`.
- `templates/base.html` — wrap the nav links in `{% if session.get('user_id') %}...{% else %}...{% endif %}` (or pass an `is_logged_in`-style value from each route); logged-in nav points to `/profile` and `/logout`.

## Files to create
None.

## New dependencies
No new dependencies. Flask's built-in `session` and `werkzeug.security.check_password_hash` (same module already used for hashing in `database/db.py` and `app.py`) cover everything needed.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (already done at registration) and verified with `check_password_hash` — never compare plaintext
- Use CSS variables – never hardcode hex values
- All templates extend `base.html`
- Store only `user_id` in the session — never the password hash
- Use one generic error message for both "email not found" and "wrong password" so login failures don't leak which part was wrong
- Do not add `@login_required`-style route protection or build out `/profile` in this step — it stays the existing placeholder string; only the nav link target changes
- Do not change how `/register` behaves (it already redirects to `/login`, not into a session)

## Definition of done
- [ ] Logging in with a correct email/password (e.g. the seeded `demo@spendly.com` / `demo123`) redirects to `/` and the nav now shows the logged-in links
- [ ] Logging in with a correct email but wrong password re-renders `login.html` with an error and does not set a session
- [ ] Logging in with an email that doesn't exist re-renders `login.html` with the same generic error and does not set a session
- [ ] `GET /login` still renders the form normally with no error
- [ ] Visiting `/logout` after logging in clears the session, redirects to `/`, and the nav reverts to the logged-out links
- [ ] Visiting `/logout` while already logged out redirects to `/` without erroring
- [ ] App starts and runs with no errors (`python app.py`)
