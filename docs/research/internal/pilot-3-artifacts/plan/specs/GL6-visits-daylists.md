# GL6-visits-daylists — day lists, visit lifecycle, one-offs, rain-day bulk move

## Context

greenlane (multi-tenant landscaping SaaS; FastAPI + Jinja2 + SQLAlchemy).
Exists: auth/tenancy + roles owner/crew (GL2/GL3), customers/properties
(GL4), schedules + the Visit model + idempotent generator (GL5 — read
`app/models.py` and `app/services/generator.py` first; Visit already has
`occurrence_date` (immutable), `date` (mutable), `position`, `assignee_id`,
`status` in {scheduled, completed, skipped}, nullable `schedule_id` and
`price_cents`). This task adds every screen and transition around visits.
Dates are date-only; "today" = today in the company's IANA timezone.

## Role rules (enforce server-side, everywhere)

- **Owner** sees and can act on all company visits.
- **Crew** sees ONLY visits assigned to them; crew views show property
  address, customer name, service, notes — **never any price**. Crew can
  `complete` and `reschedule` their own visits; everything else (skip,
  create, bulk move, other people's visits) → owner-only. Crew acting on a
  visit not assigned to them → 404 (uniform with cross-tenant).

## Routes (in `app/routes/visits.py`; the `GET /` override may live where GL2 put it)

- `GET /` (replaces GL2 placeholder): owner → 303 to `/day/{today}`;
  crew → 303 to `/my-day`.
- `GET /day/{date}` (owner; date `YYYY-MM-DD`, else 404): all visits with
  `date` = that day, grouped by assignee (unassigned group first), each
  group ordered by `position`. Each row: customer, address, service, price
  (dollars, blank for fixed-monthly visits), status, assignee, action
  buttons per lifecycle below. Prev/next day links. Shows a "move all N
  remaining visits" form when any `scheduled` visits exist (see bulk move).
- `GET /my-day` and `GET /my-day/{date}` (crew or owner): the session
  user's own assigned visits for the date (default today), ordered by
  `position`, priceless rendering, complete/reschedule actions only.
- `POST /visits/new` (owner, CSRF): standalone one-off visit — form:
  property (company's), date, service (non-empty), price in dollars
  (required, > 0, parsed to cents), optional assignee, optional note.
  Creates Visit with `schedule_id = NULL`, `occurrence_date = NULL`,
  `status = scheduled`, position appended at end of its (date, assignee)
  list. (Blank/invalid service, price, or date → form error, no write.)
- `POST /visits/{id}/complete` (owner or assigned crew, CSRF): only from
  `scheduled` → sets status, `completed_at` (UTC now), `completed_by_id`,
  optional `note`. From any other status → 409, unchanged.
- `POST /visits/{id}/skip` (owner, CSRF): only from `scheduled` → `skipped`
  with optional note; else 409. Skipped visits are history: never invoiced,
  never regenerated (the occurrence key already guarantees that), shown
  greyed on day views.
- `POST /visits/{id}/reschedule` (owner or assigned crew, CSRF): form
  `date` (valid date) — only `scheduled` visits (else 409). Sets `date`,
  appends position at end of the target (date, assignee) list.
  `occurrence_date` NEVER changes.
- `POST /day/{date}/move` (owner, CSRF) — **the rain-day op**: form
  `target_date`. Moves ALL company visits with `date = {date}` and
  `status = scheduled` to `target_date` in one transaction, preserving
  their relative order, appended after any visits already on the target
  (date, assignee) lists. Completed/skipped visits on the day stay.
  Response 303 → `/day/{target_date}`. Zero movable visits → still 303,
  no-op, no error.

**Standing invariant:** the project is typed strict on both sides — mypy config is pinned in `pilot/greenlane/pyproject.toml` and strict JSDoc/tsc config in `pilot/greenlane/tsconfig.json`. Fully annotate all new application code: `python -m mypy app` and `npm run typecheck` (both from `pilot/greenlane/`) must stay at zero errors; any `.js` you add under `app/static/` must be JSDoc-typed.

## Acceptance criteria

1. Crew A's `/my-day` never contains visits assigned to crew B, unassigned
   visits, or any price string; owner's `/day/{d}` shows all three groups.
2. Lifecycle: complete and skip are terminal (second transition → 409 and
   no field changes); reschedule moves `date` but a subsequent generator
   run creates nothing for the vacated slot.
3. Standalone visit: created with null schedule/occurrence, appears on its
   day, completes normally; form rejects missing price.
4. Bulk move of a day with a mix (scheduled ×3 across two assignees,
   1 completed, 1 skipped): the 3 land on the target date in order after
   existing target visits; the 2 stay put; re-running the same move is a
   harmless no-op.
5. Crew completing someone else's visit → 404; every mutating route with
   bad CSRF → 400; cross-tenant visit ids → 404 everywhere.

## Non-goals

No invoicing (visit `price_cents` is consumed by GL8), no photos, no clock
times, no route/map ordering UI beyond `position`, no notifications. Do not
touch anything outside `pilot/greenlane/`.
