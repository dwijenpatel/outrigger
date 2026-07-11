# GL9-payments — manual payment recording + collections view

## Context

greenlane (multi-tenant landscaping SaaS; FastAPI + Jinja2 + SQLAlchemy).
Exists: auth/tenancy (GL2), customers (GL4), invoices with statuses
`draft | sent | paid | void`, computed totals, and the frozen-after-send
rule (GL8). This task records money received — **manually**: the customer
paid by cash/check/card-outside-the-app; there is no payment processor.
Full payment only, no partials (plan decision D12). Owner-only screens.

## Model (add to `app/models.py`)

- `Payment`: `id`, `company_id` (FK, indexed), `invoice_id` (FK, **unique**
  — one payment per invoice, ever), `amount_cents` (int — always the
  invoice total at recording time), `method` (str enum: `cash` | `check` |
  `card` | `other`), `paid_on` (date — user-entered, defaults to today in
  company tz), `note` (nullable), `created_at`.

## Routes (in `app/routes/payments.py` — floored high; owner-only, CSRF-checked mutations, cross-tenant → 404)

- `POST /invoices/{id}/payments` — form: `method` (must be one of the four
  enums, else form error), `paid_on` (valid date, form default today),
  optional `note`. Legal only from status `sent` (draft → 409 "send it
  first"; paid/void → 409). In one transaction: creates the Payment with
  `amount_cents` = the invoice's current total, sets invoice status =
  `paid`. 303 → the invoice page, which now shows the payment block
  (method, date, note) instead of action buttons.
- `GET /invoices/unpaid` — the collections list: all `sent` invoices,
  oldest `sent_at` first, columns customer / total / sent date / days
  outstanding (today − sent_at date, company tz), each linking to the
  invoice. Header shows count + summed total. Empty state: "No unpaid
  invoices." The `/invoices` list page links here.
- Customer detail page (GL4's `GET /customers/{id}`) gains an invoice
  history section: every non-draft invoice for the customer (status,
  total, sent/paid dates), newest first. (Draft invoices appear only in
  `/invoices?status=draft`.)

**Standing invariant:** the project is typed strict on both sides — mypy config is pinned in `pilot/greenlane/pyproject.toml` and strict JSDoc/tsc config in `pilot/greenlane/tsconfig.json`. Fully annotate all new application code: `python -m mypy app` and `npm run typecheck` (both from `pilot/greenlane/`) must stay at zero errors; any `.js` you add under `app/static/` must be JSDoc-typed.

## Acceptance criteria

1. sent → record payment (check, backdated `paid_on`) → invoice `paid`,
   payment row carries the invoice total; the unpaid list no longer shows
   it; the customer page shows it as paid.
2. Second payment attempt on the same invoice → 409, still exactly one
   Payment row (unique constraint holds even under a double-POST).
3. Payment on draft → 409 and no row; on void → 409; bad method value or
   garbage date → form error, no row, invoice still `sent`.
4. Voiding a paid invoice remains impossible (GL8 rule — re-assert here:
   paid is terminal).
5. Unpaid list: three sent invoices with different sent_at order oldest
   first with correct day counts; paid/void/draft excluded.
6. Crew → 403 on all of it; company A recording payment on company B's
   invoice id → 404, no row; bad CSRF → 400.

## Non-goals

No partial payments, no refunds (void covers pre-payment mistakes;
post-payment corrections are out of scope for phase 1), no Stripe/online
payment, no overdue reminders or dunning email, no CSV export. Do not
touch anything outside `pilot/greenlane/`.
