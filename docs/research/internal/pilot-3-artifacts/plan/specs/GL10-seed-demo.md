# GL10-seed-demo — deterministic demo seed + smoke walkthrough

## Context

greenlane (multi-tenant landscaping SaaS; FastAPI + Jinja2 + SQLAlchemy +
SQLite) is functionally complete for phase 1+2: auth/tenancy, invites,
customers/properties, recurring schedules + generator, day-lists/visit
lifecycle/bulk move, quotes, batch invoicing, payments. This task makes the
app demonstrable in one command and documents the end-to-end walkthrough an
operator (or manual verifier) follows. Read `app/models.py` and the
services first — the seed must go through **public service functions and
model invariants, not raw SQL**.

## Deliverables

### `pilot/greenlane/seed.py`

`python pilot/greenlane/seed.py [--db PATH] [--today YYYY-MM-DD]` —
`--db` defaults to the `GREENLANE_DB` env/default; `--today` (default:
real today) is the reference date, making the output deterministic for
any fixed value. Refuses to run (non-zero exit, clear message) if the
target DB already contains any Company.

Seeds ONE demo company ("Demo Lawn Co", timezone `America/New_York`):

- owner `owner@demo.test` / password `demo-password`; crew member
  `crew@demo.test` / `demo-password` (created directly with role `crew`,
  as if an invite had been accepted).
- 4 customers, one with 2 properties (5 properties total, real-looking
  addresses).
- 3 recurring schedules: weekly per-visit mowing ($45) assigned to the
  crew member; bi-weekly per-visit mowing ($60) unassigned; one
  fixed-monthly maintenance contract ($300/mo) started ~2 months before
  `--today`.
- Visits: run the real generator for the window; additionally backfill
  LAST month's occurrences for all three schedules (create them directly
  with correct `occurrence_date`s since the generator only looks forward)
  and mark most of them completed, one skipped, so billing has history.
- 1 standalone one-off cleanup visit ($150), completed last month.
- Quotes: one draft, one sent, one accepted-and-converted (to the
  bi-weekly schedule above — i.e. create that quote first, convert it).
- Billing: run the real month batch for LAST month; mark one resulting
  invoice paid (check), leave one sent/unpaid, leave any remainder draft.
- Prints a summary table (counts per entity) and the two login pairs.

### `pilot/greenlane/WALKTHROUGH.md`

Step-by-step manual smoke script an operator follows after
`python pilot/greenlane/seed.py && python pilot/greenlane/run.py`:
login as owner → today's day list → complete a visit → rain-day bulk move
→ create a quote → accept → convert → generate this month's invoices →
send one → record payment → check `/invoices/unpaid` → login as crew →
`/my-day` shows only assigned, priceless visits. Each step names the URL,
the action, and what the reader should see.

**Standing invariant:** the project is typed strict on both sides — mypy config is pinned in `pilot/greenlane/pyproject.toml` and strict JSDoc/tsc config in `pilot/greenlane/tsconfig.json`. Fully annotate all new application code: `python -m mypy app` and `npm run typecheck` (both from `pilot/greenlane/`) must stay at zero errors; any `.js` you add under `app/static/` must be JSDoc-typed.

## Acceptance criteria

1. On a fresh DB, seed exits 0 and a subsequent run exits non-zero without
   modifying anything.
2. With `--today` fixed, two seeds into two fresh DBs produce identical
   entity counts; the printed summary matches queried reality.
3. Both seeded logins work through the real login form; the crew user's
   `/my-day` (on a date with their visits) is non-empty and priceless.
4. Seeded state is internally consistent by the app's own rules: no
   completed visit lacking `completed_at`/`completed_by`, no visit billed
   twice, the paid invoice has exactly one Payment matching its total,
   generator re-run after seeding creates 0 duplicates.
5. Every URL named in WALKTHROUGH.md resolves (no 404s) when followed in
   order against a seeded instance.

## Non-goals

No new product behavior, no schema changes, no test-fixture refactoring,
no Faker dependency (hardcode the demo data). Do not touch anything
outside `pilot/greenlane/`.
