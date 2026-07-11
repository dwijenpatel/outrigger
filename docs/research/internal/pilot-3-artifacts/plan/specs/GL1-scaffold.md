# GL1-scaffold — app skeleton, DB wiring, health route, test rig

## Context

You are building the first slice of **greenlane**, a multi-tenant SaaS web app
for small landscaping companies. Stack (pinned): Python 3, FastAPI, Jinja2
server-rendered templates, SQLAlchemy + SQLite, pytest + `fastapi.testclient`.
No JS build step, no external services, no Alembic. All product code lives
under `pilot/greenlane/`.

## Deliverables (pinned layout)

```
pilot/greenlane/
  requirements.txt          # fastapi, uvicorn, jinja2, sqlalchemy, passlib[bcrypt],
                            # itsdangerous, python-multipart, pytest, httpx,
                            # mypy, pydantic (plugin dep)
  pyproject.toml            # [tool.mypy] config — exact content pinned below
  tsconfig.json             # strict checkJs config — exact content pinned below
  package.json              # devDependency: typescript; script: typecheck
  package-lock.json         # committed (deterministic installs)
  .gitignore                # node_modules/ — the toolchain dir must never
                            # dirty the tree (git status is gate input)
  app/__init__.py           # create_app() factory
  app/config.py
  app/db.py
  app/models.py             # Base only for now (later tasks add tables)
  app/routes/__init__.py
  app/services/__init__.py
  app/templates/base.html
  app/static/styles.css
  tests/conftest.py
  tests/test_health.py
  run.py                    # uvicorn entrypoint for local dev
```

**This layout is an interface, not a suggestion.** The project's risk floors
key on these paths: all HTTP route modules live in `app/routes/<domain>.py`
(later tasks add `auth.py`, `invites.py`, `customers.py`, `schedules.py`,
`visits.py`, `quotes.py`, `invoices.py`, `payments.py` — each task's spec
names its file), all domain logic modules in `app/services/`
(`generator.py`, `billing.py`), and session/CSRF/tenancy plumbing in
`app/security.py`. Code placed elsewhere escapes its mandated validation
profile — never relocate these directories or modules.

## Behavior

- `create_app() -> FastAPI` builds the app: mounts `/static`, configures a
  Jinja2Templates instance on `app.state.templates` pointing at
  `app/templates/`, and calls `Base.metadata.create_all` on the configured
  engine at startup.
- `app/config.py`: settings read from env with defaults —
  `GREENLANE_DB` (default `sqlite:///greenlane.db`),
  `GREENLANE_SECRET` (default `"dev-secret-change-me"`).
- `app/db.py`: engine + `SessionLocal` factory built from `GREENLANE_DB`;
  a `get_db` FastAPI dependency yielding a session and closing it after the
  request. For SQLite, use `connect_args={"check_same_thread": False}`.
- `app/models.py`: SQLAlchemy `Base` (DeclarativeBase). No domain tables yet.
- `GET /health` → JSON `{"status": "ok"}`, HTTP 200.
- `base.html`: minimal responsive layout (viewport meta, one content block
  named `content`, links `styles.css`). Must render on a phone-width screen.
- **Asset rule (project-wide interface):** all static assets are vendored
  under `app/static/`; templates must never reference external URLs — no
  CDN scripts, stylesheets, fonts, or images. Use semantic HTML and keep
  ALL styling in `styles.css`, with colors/spacing/type defined as CSS
  custom properties (design tokens) at `:root` — a later restyle must be
  possible by editing CSS alone.
- `tests/conftest.py`: fixtures `app` (fresh app wired to a brand-new
  in-memory SQLite DB per test — pattern: `sqlite://` StaticPool engine
  injected before create_all) and `client` (TestClient). Later tasks extend
  this file; keep the fixtures generic.

## Type checking (pinned config)

Create `pilot/greenlane/pyproject.toml` with exactly this mypy
configuration (strict from day one — greenfield code, no adoption ladder):

```toml
[tool.mypy]
python_version = "3.14"
strict = true
warn_unreachable = true
warn_unused_configs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = "passlib.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_untyped_decorators = false
```

All application code you write must be fully annotated so
`python -m mypy app` (run from `pilot/greenlane/`) reports zero errors.
This check is a standing invariant for every later task in this project.

## Frontend type checking (pinned config)

Frontend JS is plain `.js` served as-is (no build step, no bundler) but
**strictly typed via JSDoc annotations**, checked by the TypeScript
compiler in no-emit mode. Create `pilot/greenlane/tsconfig.json` with
exactly:

```json
{
  "compilerOptions": {
    "allowJs": true,
    "checkJs": true,
    "noEmit": true,
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "target": "es2022",
    "module": "es2022",
    "lib": ["es2022", "dom", "dom.iterable"],
    "types": []
  },
  "include": ["app/static/**/*.js"]
}
```

and `package.json` with typescript (^5) as the sole devDependency and a
`typecheck` script running `tsc --noEmit`. Commit `package-lock.json`;
gitignore `node_modules/`. Any `.js` under `app/static/` must pass
`npm run typecheck` with zero errors — a standing invariant for every
later task, mirroring mypy. (If this task ships no JS at all, the config
must still exist and the check must still pass on the empty set.)

## Acceptance criteria

1. `pip install -r pilot/greenlane/requirements.txt` then
   `python -m pytest pilot/greenlane/tests` passes, and
   `python -m mypy app` (from `pilot/greenlane/`) reports zero errors.
1b. `npm install` then `npm run typecheck` (from `pilot/greenlane/`)
   exits 0; `git status` stays clean afterwards (node_modules ignored).
2. `GET /health` on a TestClient returns 200 with body `{"status": "ok"}`.
3. Two `create_app()` calls with different `GREENLANE_DB` values do not share
   state (engine is per-app, not module-global-mutated).
4. `run.py` starts uvicorn on port 8000 when executed directly.

## Non-goals

No auth, no domain models, no navigation links, no CSS beyond a readable
baseline. Do not touch anything outside `pilot/greenlane/`.
