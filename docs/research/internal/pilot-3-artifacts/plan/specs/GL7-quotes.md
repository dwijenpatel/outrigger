# GL7-quotes — internal quotes with conversion to work

## Context

greenlane (multi-tenant landscaping SaaS; FastAPI + Jinja2 + SQLAlchemy).
Exists: auth/tenancy (GL2), customers/properties (GL4), schedules +
generator (GL5), standalone one-off visits via `POST /visits/new` semantics
(GL6). Quotes here are **internal records** — the customer answers by phone;
the owner records the outcome. There is no public/customer-facing quote
page (that is a later product phase). All quote screens are owner-only;
money is integer cents, entered as dollars.

## Models (add to `app/models.py`)

- `Quote`: `id`, `company_id` (FK, indexed), `customer_id` (FK),
  `property_id` (FK — must belong to that customer), `status` (str:
  `draft` | `sent` | `accepted` | `declined`), `notes` (nullable),
  `created_at`, `sent_at`/`accepted_at`/`declined_at` (nullable datetimes).
- `QuoteLine`: `id`, `quote_id` (FK, indexed), `company_id`, `description`
  (non-empty), `qty` (int ≥ 1), `unit_price_cents` (int ≥ 0), `position`.
  Line total = qty × unit_price; quote total = sum of line totals.

## Routes (in `app/routes/quotes.py`; owner-only, mutating ones CSRF-checked)

- `GET /quotes` — list: customer, property, status, total, created; filter
  tabs by status (`?status=draft` etc.; bad value = no filter).
- `GET /quotes/new`, `POST /quotes/new` — customer select → property select
  (any property of the company; must belong to the chosen customer, else
  form error), optional notes. Creates a `draft` quote with no lines,
  303 → its detail page.
- `GET /quotes/{id}` — detail: lines with totals, status timeline, and the
  actions legal for its status (below).
- Lines, only while `draft`:
  `POST /quotes/{id}/lines` (description, qty, unit price in dollars),
  `POST /quotes/{id}/lines/{line_id}/edit`,
  `POST /quotes/{id}/lines/{line_id}/delete`.
  Any line mutation on a non-draft quote → 409.
- Status transitions (each stamps its timestamp; anything else → 409):
  `POST /quotes/{id}/send`: draft → sent. Requires ≥ 1 line.
  `POST /quotes/{id}/accept`: sent → accepted.
  `POST /quotes/{id}/decline`: sent → declined.
  No transitions out of accepted/declined.
- `GET /quotes/{id}/convert` (only when `accepted`, else 409): form with
  `kind` radio — `schedule` or `one_off` — pre-filled from the quote:
  service description = the first line's description (editable), price in
  dollars = the **quote total** (editable), property fixed to the quote's
  property. For `schedule`: plus interval_weeks/weekday/start_date/
  billing_mode fields (GL5 semantics). For `one_off`: plus date field.
  `POST /quotes/{id}/convert` creates the Schedule (and runs the generator)
  or the standalone Visit (GL6 semantics: null schedule_id, price
  required), then 303 → the new object's page. Converting twice is allowed
  (idempotency is not required here — the owner may split a quote into a
  schedule AND a one-off cleanup); each POST creates exactly what it says.

**Standing invariant:** the project is typed strict on both sides — mypy config is pinned in `pilot/greenlane/pyproject.toml` and strict JSDoc/tsc config in `pilot/greenlane/tsconfig.json`. Fully annotate all new application code: `python -m mypy app` and `npm run typecheck` (both from `pilot/greenlane/`) must stay at zero errors; any `.js` you add under `app/static/` must be JSDoc-typed.

## Acceptance criteria

1. draft → send (with lines) → accept → convert-to-schedule produces a
   Schedule whose price equals the edited form value and visits via the
   generator; timestamps recorded at each hop.
2. Sending a lineless quote → 409/form error and status stays draft;
   editing lines after send → 409, lines unchanged.
3. accept on a draft (not yet sent) → 409; decline after accept → 409.
4. Convert with `kind=one_off` creates a standalone Visit on the given
   date with the given price, no schedule.
5. Totals: 2 × $45.00 line + 1 × $30.00 line renders quote total $120.00
   (12000 cents internally); dollar parsing rejects negatives and garbage.
6. Crew → 403 on every quote route; cross-tenant quote/customer/property
   ids → 404; bad CSRF → 400.

## Non-goals

No public approval link, no emailing quotes (no outbox rows), no PDF, no
quote expiry, no discounts/tax. Do not touch anything outside
`pilot/greenlane/`.
