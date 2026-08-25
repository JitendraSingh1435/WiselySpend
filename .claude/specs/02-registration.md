# Spec: Registration

## Overview
Implements account creation for Spendly. Right now `/register` (`app.py`) only renders `templates/register.html` on GET — there is no handler for the form's `POST /register` submission, so new users can't actually be created. This step adds the `POST` handling: validate the submitted name/email/password, hash the password, insert a new row into `users`, and route the user onward. Login/logout and session-based auth are out of scope here (staged for the next step — see the `Logout — coming in Step 3` placeholder in `app.py`); registration ends by sending the user to the login page, not by logging them in.

## Depends on
- Step 1 — Database setup (`database/db.py` with working `get_db()`/`init_db()`/`users` table). Complete.

## Routes
- `POST /register` – accept the registration form, validate, create the user, redirect to `/login` on success or re-render the form with an error — public
- `GET /register` – already implemented, unchanged

## Database changes
No database changes. `users` table (`database/db.py`) already has the columns this needs: `name`, `email` (UNIQUE), `password_hash`. Use `get_db()` and a parameterized `INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)`.

## Templates
- Create: none
- Modify: `templates/register.html` — no structural changes expected; it already posts to `/register` with `name`/`email`/`password` fields and already renders `{% if error %}{{ error }}{% endif %}`. Only touch it if server-side validation needs a field-specific message it doesn't already support.

## Files to change
- `app.py` — replace the GET-only `register()` view with one that also handles `POST`: read form fields, validate, hash password with `werkzeug.security.generate_password_hash`, insert via `get_db()`, handle `sqlite3.IntegrityError` for duplicate email, redirect to `/login` on success.

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security` is already used in `database/db.py`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend base.html
- Validate on the server even though the form has `required`/`type=email`/etc. client-side attributes: reject empty name, malformed email, and password under 8 characters
- On duplicate email, re-render `register.html` with a clear `error` message and a 400-range or normal status — do not leak whether it's the email specifically causing a DB-level failure vs. validation failure in ambiguous wording
- Do not implement login, sessions, or `current_user`-style state in this step

## Definition of done
- [ ] Submitting the register form with a new name/email/password creates a row in `users` with a hashed (not plaintext) password
- [ ] After a successful registration, the browser is redirected to `/login`
- [ ] Submitting with an email that already exists in `users` re-renders `register.html` showing an error, and does not create a duplicate row
- [ ] Submitting with an empty name, invalid email format, or password under 8 characters re-renders `register.html` with an error and does not insert a row
- [ ] `GET /register` still renders the form normally with no error
- [ ] App starts and runs with no errors (`python app.py`)
