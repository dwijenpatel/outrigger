# greenlane — plan (pilot #2)

Field-service SaaS for small landscaping companies (owner-operator to ~3 crews).
Product code lives in `pilot/greenlane/`. Planned 2026-07-04 via the plan-build
interview; research inputs: general small-shop FSM baseline (Jobber, Housecall
Pro, ServiceTitan) and landscaping-niche products (Yardbook, SingleOps, LMN,
Service Autopilot).

## Goal & wedge

**The wedge is the recurring-visit engine**: recurring maintenance schedules
(every-N-weeks mowing) that auto-materialize visits, crew day-lists to work
them, and the visit → invoice pipeline with two billing modes (per-visit and
fixed-monthly) plus idempotent month-end batch invoicing. This targets the
documented market hole between free Yardbook and $119/mo Jobber Connect:
automated recurrence + batch invoicing without enterprise surface. One-off
jobs (cleanups) are the degenerate single-visit case. Quotes are a simple
internal front door. Everything else is later-phase or OUT.

## Decisions log

| # | Decision | Answer | Source |
|---|---|---|---|
| D1 | Pilot scope | Landscaping domain, revised scope (not a restart of pilot-1's exact shape) | operator |
| D2 | Wedge | Recurring-visit engine → billing (see above) | operator (rec confirmed) |
| D3 | Users & roles | Owner + crew members; **no customer login** | operator (rec confirmed) |
| D4 | Tenancy | Multi-tenant SaaS; company = tenant; every record tenant-scoped; cross-tenant access is the #1 invariant | operator (rec confirmed) |
| D5 | Auth | Email+password (bcrypt); server-side signed httpOnly SameSite=Lax session cookie; crew onboarding via single-use 7-day emailed invite tokens (hashed at rest); no OAuth; password reset is P2 | operator (rec confirmed) |
| D6 | Customer model | Customer has 1..N Properties; work attaches to a property; invoices roll up to the customer | operator (rec confirmed) |
| D7 | Assignment | Visits assigned to individual users (optional); no Crew entity (P3) | operator (rec confirmed) |
| D8 | Recurrence rules | Every N weeks (N=1–4) on one weekday; start date; optional end date; no RRULE/monthly (P3) | operator (rec confirmed) |
| D9 | Visit materialization | Idempotent horizon generator: materializes Visit rows through today+28 days; re-runs never duplicate; never touches touched visits | operator (rec confirmed) |
| D10 | Visit lifecycle | scheduled → completed \| skipped; single-visit reschedule; **bulk move of a day's still-scheduled visits** (rain day) in phase 1 | operator (rec confirmed) |
| D11 | Batch invoicing | "Generate invoices for month M": per-visit mode sweeps completed uninvoiced visits dated ≤ end of M; fixed-monthly bills schedules active any day of M, **no proration**; one draft invoice per customer; idempotent (exactly-once per visit / per (schedule, month)) | operator (rec confirmed) |
| D12 | Invoice lifecycle | draft (editable) → sent (frozen; outbox stub) → paid (manual full payment: date+method) ; void from draft/sent releases lines; no partials; no Stripe (P2); no overdue automation | operator (rec confirmed) |
| D13 | Quotes | Internal only: draft→sent→accepted/declined recorded by owner; accepted quote converts to schedule and/or one-off visit; public approval link is P2 | operator (rec confirmed) |
| D14 | Tech stack | Python 3 / FastAPI / Jinja server-rendered / SQLAlchemy / SQLite; sessions via signed cookie; no JS build step; responsive CSS; held-out tests drive HTTP via TestClient | operator (rec confirmed) |
| D15 | Time model | Visits are **date-only** with an integer day-order position; no clock times (P3); company has one IANA timezone used to resolve "today" and month boundaries | operator (rec confirmed) |
| D16 | Security floor | bcrypt; CSRF token on every mutating form; SameSite=Lax httpOnly cookie; invite tokens single-use/7d/hashed; server-side role enforcement; tenant scoping from session only; uniform 404 for cross-tenant probes; no rate limiting/2FA/audit log (P3) | operator (rec confirmed) |
| D17 | Risk map | Auth/tenancy/invites **critical**; billing engine, payments, models, visit generator **high**; CRUD/views/quotes **elevated**; scaffold/seed **routine** | operator (rec confirmed) |
| D18 | Name | **greenlane** (`pilot/greenlane/`) | operator |
| D19 | One-off jobs | DECISION (delegated): standalone Visit rows — nullable schedule link; own description + price required when standalone; swept into per-visit invoicing on completion | operator confirmed pin |
| D20 | Crew visibility | DECISION (delegated): crew sees only visits assigned to them; day-list shows address/service/notes, never prices; customers/quotes/invoices/schedule-pricing owner-only. Visits keep immutable `occurrence_date` (generator dedup key) separate from mutable `date` | operator confirmed pin |
| D21 | Deletes | DECISION (delegated): no hard deletes in phase 1 — schedules end via end_date; customers/properties/quotes undeletable (archive P2); draft invoices deletable (lines return to uninvoiced pool) | operator confirmed pin |
| D22 | Sales tax | None in phase 1; totals = sum of lines; money stored as **integer cents**; single flat company tax rate is a named P2 item | operator (rec confirmed) |
| D23 | Ad-hoc invoicing | DECISION (delegated): mid-month per-customer invoice sweeps only completed uninvoiced visits dated ≤ today; fixed-monthly charges bill **only** via the month batch | planner, ratified with plan |
| D24 | Migrations | DECISION (delegated): no Alembic — `create_all` on startup; SQLite file path from `GREENLANE_DB` env, tests use in-memory/tmp DBs | planner, ratified with plan |
| D25 | Type checking | mypy `strict = true` + `warn_unreachable`/`warn_unused_configs`, pydantic plugin, passlib stub override, relaxed untyped-defs for tests only; `python -m mypy app` clean at the end of every task (config: Tech stack section) | operator |
| D26 | Frontend assets & restyle path | All static assets vendored under `app/static/` — **no CDN/external URLs in templates** (zero-external-services posture). Templates use semantic HTML with all styling in `app/static/styles.css` behind CSS custom properties (design tokens), so the planned later **UI polish pass** (fast, modern, responsive — operator priority) is a CSS/asset-only effort, not a template or backend rework. A SPA rewrite is explicitly not the polish path. | operator |
| D27 | Frontend JS typing | JSDoc-annotated plain `.js` checked by `tsc --noEmit` with `strict: true` + `checkJs` (same strict engine as real TS, zero build step — D14/D26 intact; the served file IS the source, no output drift). Node + typescript are dev-only check dependencies, the frontend mirror of mypy. Config pinned in GL1 (`tsconfig.json`); `npm run typecheck` clean is a standing invariant alongside mypy. If the P2 UI polish pass ever needs real `.ts`, flipping is additive (rename + drop `checkJs`), not an unwind. | operator |

## OUT list

**OUT with a named later product phase:** Stripe payment links (P2) ·
public quote-approval page (P2) · real email/SMS delivery — outbox table only
(P2) · password reset (P2) · sales tax (P2) · customer/property archive (P2) ·
Crew entity/grouping (P3) · map route ordering & optimization (P3) ·
photos/attachments (P3) · QuickBooks export (P3) · timed appointments (P3) ·
rate limiting, 2FA, audit log (P3).

**OUT entirely (no phase):** customer portal/login · GPS tracking · time
tracking · job costing · materials/property-size estimating · chemical
tracking · snow operations · marketing automation · reporting dashboards ·
multi-company membership per user · i18n · native mobile apps · online
booking widget.

## Tech stack

Python 3 (repo toolchain) · FastAPI + Starlette session middleware ·
Jinja2 server-rendered templates, plain forms, minimal vanilla JS ·
SQLAlchemy + SQLite (`create_all`, no migrations) · passlib[bcrypt] ·
pytest + fastapi TestClient · **mypy in strict mode** (below). One process,
zero external services. Postgres and deployment are provisional later
concerns.

### Type checking (mypy)

Greenfield code, so full strictness from day one — no gradual-adoption
ladder. Config lives in `pilot/greenlane/pyproject.toml`; the check is
`python -m mypy app` run from `pilot/greenlane/`, and it must stay clean
(zero errors) at the end of every task.

```toml
[tool.mypy]
python_version = "3.14"
strict = true                 # the standard umbrella; enables the full
                              # optional-check set: disallow_untyped_defs,
                              # disallow_incomplete_defs, check_untyped_defs,
                              # disallow_any_generics, disallow_subclassing_any,
                              # disallow_untyped_calls, disallow_untyped_decorators,
                              # warn_redundant_casts, warn_unused_ignores,
                              # warn_return_any, no_implicit_reexport,
                              # strict_equality, extra_checks
warn_unreachable = true       # common addition: dead-code detection
warn_unused_configs = true    # common addition: catches stale overrides
plugins = ["pydantic.mypy"]   # FastAPI request/response models

[[tool.mypy.overrides]]
module = "passlib.*"          # ships no type stubs
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "tests.*"            # standard test-code relaxation: pytest
disallow_untyped_defs = false # fixtures/decorators stay unannotated
disallow_untyped_decorators = false
```

SQLAlchemy 2.x ships inline types (no plugin needed). `strict = true` is
the community-standard umbrella (per the mypy docs its exact flag list can
grow across releases — that ratchet is accepted deliberately); the
individual flags above are only documented so spec-readers know what the
umbrella implies.

### Frontend type checking (tsc, no build step)

Frontend JS stays plain `.js` served directly from `app/static/` (D26),
typed via JSDoc annotations and checked by the TypeScript compiler in
no-emit mode — identical strict semantics to real TS with no compile step
(D27). Config lives in `pilot/greenlane/tsconfig.json`; the check is
`npm run typecheck` (`tsc --noEmit`) from `pilot/greenlane/`, clean at the
end of every task, mirroring mypy.

```jsonc
// tsconfig.json
{
  "compilerOptions": {
    "allowJs": true, "checkJs": true, "noEmit": true,
    "strict": true,                    // the umbrella: noImplicitAny,
                                       // strictNullChecks, strictFunctionTypes,
                                       // strictBindCallApply, alwaysStrict, ...
    "noUncheckedIndexedAccess": true,  // common strictness additions
    "noImplicitOverride": true,        // beyond the umbrella
    "noFallthroughCasesInSwitch": true,
    "target": "es2022", "module": "es2022",
    "lib": ["es2022", "dom", "dom.iterable"], "types": []
  },
  "include": ["app/static/**/*.js"]
}
```

`package.json` carries typescript as the only devDependency with a
`typecheck` script; `package-lock.json` is committed, `node_modules/` is
gitignored (P1-5 class: an untracked toolchain dir must never dirty the
tree the gate judges).

## Phase map

| Phase | Content | Status |
|---|---|---|
| **1 — walking skeleton** | scaffold → auth/tenancy → invites → customers/properties → schedules+generator → visits/day-lists/bulk-move (GL1–GL6) | ledgered, specced |
| **2 — the billing wedge** | quotes → batch invoicing → payments → seed/demo (GL7–GL10) | ledgered, specced |
| P2 (product, provisional) | Stripe links, public quote approval, real email sending, password reset, sales tax, archive, **UI polish pass** (modern styling/design system, optional vendored htmx sprinkles — CSS/asset-only per D26) | planning-only |
| P3 (product, provisional) | Crew entity, route ordering/optimization, photos, QuickBooks export, timed visits, rate limiting/2FA/audit | planning-only |

## Where each risk lives

- **Cross-tenant leakage** → `app/security.py` scoping helpers + every route; floored critical on auth surfaces, high on models.
- **Auth/session/invite abuse** → `routes/auth.py`, `routes/invites.py`, `security.py`; critical.
- **Double-billing / missed billing** → `services/billing.py` idempotency invariants; high.
- **Visit duplication/loss** → `services/generator.py` idempotency + occurrence-key semantics; high.
- **Wrong-but-plausible money math** → integer cents everywhere; high floors on invoice/payment routes.
