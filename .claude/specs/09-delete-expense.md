# Spec: Delete Expense

## Overview
Step 9 lets a logged-in user permanently remove one of their own expenses from
`/expenses/<id>/delete`. This replaces the current placeholder route with a
real `POST`-only handler that deletes the row from the database and redirects
back to the profile page. Ownership is enforced exactly like Step 8's edit
flow: a user can only delete expenses that belong to them. One new query
helper, `delete_expense`, is added to `database/queries.py`. The transactions
table in `profile.html` gains a "Delete" action next to the existing "Edit"
link, submitted via a small inline form with a JavaScript confirmation prompt
so a stray click can't destroy data.

## Depends on
- Step 1: Database setup (`expenses` table exists with all required columns)
- Step 3: Login / Logout (`session["user_id"]` is set and enforced)
- Step 5: Profile page renders transactions (the delete action lives there)
- Step 8: Edit Expense (establishes the ownership-scoped mutation pattern and
  the "Actions" column in the transactions table)

## Routes
- `POST /expenses/<int:id>/delete` – delete the expense if it belongs to the
  current user, then redirect to `/profile` – logged-in only

The existing route accepts `GET`; this step changes it to `POST`-only so the
deletion cannot be triggered by a plain link, prefetch, or crawler.

## Database changes
No new tables or columns. Deletion uses the existing `expenses` table's `id`
and `user_id` columns, both already present.

## Templates
- **Modify**: `templates/profile.html`
  - In the "Actions" cell added by Step 8, add a delete form next to the
    existing "Edit" link:
    ```html
    <form method="POST" action="{{ url_for('delete_expense', id=tx.id) }}"
          class="tx-delete-form" onsubmit="return confirm('Delete this expense?');">
        <button type="submit" class="tx-delete-link">Delete</button>
    </form>
    ```

## Files to change
- `database/queries.py`
  - Add `delete_expense(expense_id, user_id)` — issues a parameterised
    `DELETE` scoped to both `id` and `user_id` for ownership safety
- `app.py`
  - Import `delete_expense` from `database.queries`
  - Replace the placeholder `/expenses/<int:id>/delete` route:
    - Change the decorator to `methods=["POST"]` only
    - Require `session.get("user_id")`; redirect to `/login` if absent
    - Call `get_expense_by_id(id, user_id)`; `abort(404)` if not found or not
      owned by the current user
    - Call `delete_expense(id, user_id)`
    - Redirect to `url_for("profile")`
- `templates/profile.html`
  - Add the delete form described above to each transaction row's Actions cell
- `static/css/style.css`
  - Add `.tx-delete-form` (inline-block, matches spacing next to `.tx-edit-link`)
    and `.tx-delete-link` (styled as a link-like button using `var(--danger)`
    for its color, matching the existing `.tx-edit-link` treatment)

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (unaffected by this step, no password handling here)
- `delete_expense` must scope its query to `id = ? AND user_id = ?` to prevent
  one user deleting another user's expense
- Reuse `get_expense_by_id` (from Step 8) to check existence and ownership
  before deleting, so a missing or foreign expense returns 404 instead of a
  silent no-op delete
- Unauthenticated access must redirect to `/login`
- If the expense does not exist or belongs to another user, return a 404
- The route must only accept `POST` — no `GET` handler, so the deletion cannot
  happen from a plain hyperlink
- The delete control must be a `<form>` + `<button>`, not an `<a href>`, since
  it performs a `POST`
- Require a JavaScript confirmation (`confirm()`) before the form submits, to
  prevent accidental deletion
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency must always display as ₹ — never £ or $

## Definition of done
- [ ] Visiting `/profile` while logged in shows a "Delete" action next to "Edit" for every transaction
- [ ] Clicking "Delete" shows a browser confirmation prompt before submitting
- [ ] Confirming deletion removes the expense from the database and redirects to `/profile`
- [ ] The deleted expense no longer appears in the transaction list, stats, or category breakdown after redirect
- [ ] Cancelling the confirmation prompt leaves the expense untouched
- [ ] Sending `POST /expenses/<id>/delete` while logged out redirects to `/login`
- [ ] Sending `POST /expenses/<id>/delete` for a non-existent expense id returns 404
- [ ] Sending `POST /expenses/<id>/delete` for another user's expense returns 404 and leaves that row in the database
- [ ] Sending `GET /expenses/<id>/delete` no longer works (405 Method Not Allowed)
