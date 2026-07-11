# GL4-customers-properties — customer & property CRUD (owner-only)

## Context

greenlane (multi-tenant landscaping SaaS; FastAPI + Jinja2 + SQLAlchemy).
Auth/tenancy exists (GL2): `current_user`, `require_owner`, `check_csrf`,
tenant-scoped `get_or_404` (cross-tenant or missing → uniform 404). A
Customer is the billed party; each customer has **1..N Properties** (service
addresses) — work always attaches to a property, money rolls up to the
customer. All screens in this task are **owner-only** (crew gets 403).

## Models (add to `app/models.py`)

- `Customer`: `id`, `company_id` (FK, indexed), `name` (non-empty), `email`
  (nullable), `phone` (nullable), `notes` (nullable text), `created_at`.
- `Property`: `id`, `company_id` (FK, indexed), `customer_id` (FK, indexed),
  `address` (non-empty), `notes` (nullable text), `created_at`. `company_id`
  is denormalized on Property (and on every later work/billing table) so
  scoping never needs a join.

## Routes (in `app/routes/customers.py`; all owner-only, mutating ones CSRF-checked)

- `GET /customers` — list (name, phone, property count), newest first, plus
  a "new customer" link. No pagination (small-shop scale is hundreds).
- `GET /customers/new`, `POST /customers/new` — the form includes the fields
  of the **first property** (address, notes) so a one-address customer is one
  step; creates Customer + Property in one transaction. Empty name or empty
  address → re-render with error, nothing created.
- `GET /customers/{id}` — detail: contact info, notes, all properties, and
  an "add property" form (`POST /customers/{id}/properties`, requires
  non-empty address).
- `GET /customers/{id}/edit`, `POST /customers/{id}/edit` — name/email/
  phone/notes.
- `GET /properties/{id}/edit`, `POST /properties/{id}/edit` — address/notes.
- No delete routes for either entity (plan decision D21 — archive is a later
  phase).

**Standing invariant:** the project is typed strict on both sides — mypy config is pinned in `pilot/greenlane/pyproject.toml` and strict JSDoc/tsc config in `pilot/greenlane/tsconfig.json`. Fully annotate all new application code: `python -m mypy app` and `npm run typecheck` (both from `pilot/greenlane/`) must stay at zero errors; any `.js` you add under `app/static/` must be JSDoc-typed.

## Acceptance criteria

1. Creating a customer via the form yields exactly one Customer and one
   Property, linked, both carrying the owner's `company_id`.
2. A second property added via the detail page appears there; the customer
   list shows property count 2.
3. Every route 404s for ids belonging to another company and 403s for crew
   sessions; POSTs without valid CSRF → 400.
4. Validation failures (blank name, blank address) re-render with an error
   and write nothing.
5. Property edit cannot move the property to another customer or company —
   `customer_id`/`company_id` are not form fields and remain unchanged even
   if smuggled into the POST body.

## Non-goals

No search/filtering, no archive/delete, no CSV import, no customer-facing
anything, no schedules or visits (later tasks). Do not touch anything
outside `pilot/greenlane/`.
