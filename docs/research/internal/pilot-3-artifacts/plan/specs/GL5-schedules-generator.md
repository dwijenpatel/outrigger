# GL5-schedules-generator — recurring schedules + idempotent visit generator

## Context

greenlane (multi-tenant landscaping SaaS; FastAPI + Jinja2 + SQLAlchemy).
Exists already: auth/tenancy (GL2 — `current_user`, `require_owner`,
`check_csrf`, tenant-scoped `get_or_404`, uniform 404), customers with 1..N
properties (GL4). This task is the heart of the product: **recurring
maintenance schedules** ("every 1 week on Tuesday: mowing at 12 Elm St, $45
per visit") and the **generator** that materializes Visit rows from them.
Dates are date-only — visits have no clock times. "Today" is resolved in the
**company's IANA timezone** (`Company.timezone`, via `zoneinfo`).

## Models (add to `app/models.py`)

- `Schedule`: `id`, `company_id` (FK, indexed), `property_id` (FK),
  `service` (non-empty str, e.g. "Mowing"), `interval_weeks` (int 1–4),
  `weekday` (int 0–6, Monday=0), `start_date` (date), `end_date` (date,
  nullable; if set must be ≥ start_date), `default_assignee_id` (nullable FK
  → users.id, must belong to same company), `billing_mode` (str:
  `per_visit` | `fixed_monthly`), `price_cents` (int > 0 — per-visit price
  or monthly price per the mode), `created_at`.
- `Visit`: `id`, `company_id` (FK, indexed), `schedule_id` (FK, **nullable**
  — standalone one-off visits come in GL6), `property_id` (FK),
  `occurrence_date` (date, nullable for standalone — the slot the generator
  created this visit for; IMMUTABLE once set), `date` (date — where the
  visit currently sits; starts equal to occurrence_date, moves on
  reschedule), `position` (int ≥ 0 — order within its date+assignee list),
  `assignee_id` (nullable FK), `service` (str — copied from schedule at
  generation; owned by the visit for standalones), `price_cents` (nullable
  int — copied for per_visit schedules; NULL for fixed_monthly visits;
  required for standalones), `status` (str: `scheduled` | `completed` |
  `skipped`), `completed_at` (nullable UTC datetime), `completed_by_id`
  (nullable FK), `note` (nullable), `created_at`.
  Unique constraint on (`schedule_id`, `occurrence_date`) — the generator's
  dedup key.

## The generator (`app/services/generator.py`)

`generate_visits(db, company_id, today: date) -> int` (returns # created):

- For every schedule of the company: occurrence dates are `first, first +
  interval_weeks*7, ...` where `first` = the earliest date ≥ `start_date`
  falling on `weekday`.
- Materialize a Visit for every occurrence in the window
  `[today, today + 28 days]`, also bounded by `end_date` when set. Do NOT
  create occurrences before `today` (no retroactive backfill).
- **Idempotent**: an occurrence that already has a Visit row (any status,
  any current `date` — the unique key is on `occurrence_date`) is never
  recreated. Rescheduling a visit to another date must not cause a hole the
  generator refills; completing/skipping must not either.
- New visits get: `date = occurrence_date`, `assignee_id = schedule.
  default_assignee_id`, `service`/`price_cents` copied per the model note,
  `status = scheduled`, `position` = 1 + max(position) among visits already
  on that (`date`, `assignee_id`) within the company, else 0.
- Called automatically after schedule create and edit, and exposed to the
  owner as `POST /schedules/generate` (CSRF) which runs it with today in
  company tz and redirects back to `/schedules`.

## Routes (in `app/routes/schedules.py`; owner-only, mutating ones CSRF-checked)

- `GET /schedules` — list: property address, service, human rule ("every 2
  weeks on Tuesday"), billing mode + price (dollars), start/end, active?
  (active = start_date reached ≤ any remaining occurrences; simply: no
  end_date or end_date ≥ today).
- `GET /schedules/new`, `POST /schedules/new` — property select (company's
  properties), service, interval_weeks (1–4), weekday, start_date, optional
  end_date, optional default assignee (company users), billing_mode, price
  in dollars (parsed to cents; invalid/≤0 → form error). On success:
  create, run generator, 303 → `/schedules`.
- `GET /schedules/{id}/edit`, `POST /schedules/{id}/edit` — same fields
  except `billing_mode` is immutable after creation (render read-only;
  smuggled values ignored). Edits affect only FUTURE materialization:
  existing visits keep their copied service/price/assignee; the generator
  runs after the edit for new slots only (the unique key already prevents
  regeneration of existing occurrences).
- `POST /schedules/{id}/end` — form field `end_date` (≥ today); sets it and
  **deletes** this schedule's still-`scheduled` visits with
  `occurrence_date > end_date` (completed/skipped rows are history — never
  touched).

**Standing invariant:** the project is typed strict on both sides — mypy config is pinned in `pilot/greenlane/pyproject.toml` and strict JSDoc/tsc config in `pilot/greenlane/tsconfig.json`. Fully annotate all new application code: `python -m mypy app` and `npm run typecheck` (both from `pilot/greenlane/`) must stay at zero errors; any `.js` you add under `app/static/` must be JSDoc-typed.

## Acceptance criteria

1. Weekly schedule, start on a Wednesday, weekday=Tuesday → first visit is
   the following Tuesday; window [today, today+28] contains exactly the
   right dates (5 or fewer rows), each with copied service/price/assignee.
2. Running `generate_visits` twice back-to-back creates rows once (second
   run returns 0). Completing one visit, rescheduling another to a
   different date, then re-running: still 0 new rows.
3. Bi-weekly (interval 2): consecutive occurrence_dates differ by exactly
   14 days.
4. `end_date` set mid-window → future scheduled visits past it are gone;
   a completed visit past it survives.
5. `fixed_monthly` schedule → its visits have `price_cents` NULL;
   `per_visit` → visits carry the schedule price at generation time even
   after the schedule's price is later edited.
6. All routes: cross-tenant ids → 404; crew → 403; bad CSRF → 400;
   interval 0 or 5, end < start, price "abc" → form error, no writes.

## Non-goals

No visit views/day-lists, no complete/skip/reschedule endpoints, no
standalone visits, no bulk move (all GL6). No invoicing. No cron — the
generator is invoked synchronously. Do not touch anything outside
`pilot/greenlane/`.
