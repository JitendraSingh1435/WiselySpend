# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Spendly — a personal expense tracker built with Flask, server-rendered Jinja2 templates, and vanilla JS/CSS (no frontend framework, no build step). This is a learning project (CampusX course) built incrementally in numbered steps; several routes and the entire database layer are intentionally unimplemented stubs (see below), not bugs.

## Running the app

```
python app.py
```

The app runs on `http://localhost:5001` with `debug=True`.

**Interpreter note:** the repo's `.venv` may not have `flask`/`werkzeug`/`pytest` installed even though they're in `requirements.txt`. If `python app.py` fails with `ModuleNotFoundError: No module named 'flask'`, check `pip list` in `.venv` — if the packages are missing there, fall back to a system Python that has them installed rather than assuming the app is broken.

## Testing

```
pytest
```

Uses `pytest` + `pytest-flask` (per `requirements.txt`). No test files exist yet.

## Architecture

- **`app.py`** — single-file Flask app; all routes are defined here directly (no blueprints). Routes render templates via `render_template`, no view logic yet beyond that.
- **`database/db.py`** — currently an empty stub. Per its header comment, it is meant to hold:
  - `get_db()` — SQLite connection with `row_factory` and foreign keys enabled
  - `init_db()` — creates tables with `CREATE TABLE IF NOT EXISTS`
  - `seed_db()` — inserts sample dev data
  - The SQLite file (`expense_tracker.db`) is gitignored — it's created locally, not committed.
- **`templates/base.html`** — the shared layout (nav, footer, `{% block content %}`). All pages extend this. Every page template (`landing.html`, `login.html`, `register.html`, `terms.html`) follows the `{% extends "base.html" %}` / `{% block title %}` / `{% block content %}` pattern — match this when adding new pages instead of duplicating the `<nav>`/`<footer>` markup.
- **`static/css/style.css`** — single global stylesheet for all pages (no per-page CSS files, no preprocessor).
- **`static/js/main.js`** — single global vanilla-JS file. No JS framework or bundler is used anywhere in the project; keep new interactive behavior (modals, form handling, etc.) as plain JS appended here or in inline `{% block scripts %}`.

### Current route state (`app.py`)

Implemented (render a template): `/` (landing), `/register`, `/login`, `/terms`.

Explicit placeholders returning plain strings, awaiting later steps: `/logout`, `/profile`, `/expenses/add`, `/expenses/<int:id>/edit`, `/expenses/<int:id>/delete`. Don't "fix" these into real implementations unless asked — they're deliberately staged for future steps (auth, DB-backed CRUD) that depend on `database/db.py` being built out first.

## Conventions observed in this repo

- When asked to redesign or add to a specific section of a page (e.g. "only the hero section"), keep the change scoped exactly as requested — sibling sections and unrelated files are expected to stay untouched (see `prompt.txt` for the actual style of instructions this project is driven by).
- Placeholder links/content (e.g. `href="#"`) get wired up to real routes only when the corresponding page/route is explicitly built.
