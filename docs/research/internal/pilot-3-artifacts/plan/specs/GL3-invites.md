# GL3-invites — crew invitations via single-use tokens

## Context

greenlane (multi-tenant landscaping SaaS; FastAPI + Jinja2 + SQLAlchemy).
Auth exists (GL2): Company/User models, sessions, `security.py` with
`current_user`, `require_owner`, `check_csrf`, tenant-scoped `get_or_404`,
uniform-404 convention for cross-tenant probes. Roles: `owner`, `crew`. This
task lets an owner invite crew members by email. There is **no real email
sending** — outbound mail is rows in an outbox table (stub pinned by plan
decision D12/D16).

## Models (add to `app/models.py`)

- `Invite`: `id`, `company_id` (FK, indexed), `email` (lowercase), `name`,
  `token_hash` (sha256 hex of the raw token — raw token is NEVER stored),
  `created_at`, `expires_at` (= created_at + 7 days), `used_at` (nullable),
  `revoked_at` (nullable).
- `OutboxEmail`: `id`, `company_id`, `to_email`, `subject`, `body` (text),
  `kind` (str, here `"invite"`), `created_at`. (Invoicing reuses this table
  later — keep it generic.)

## Behavior & routes (in `app/routes/invites.py` — this path is floored critical; do not put these handlers anywhere else)

- `GET /team` (owner only): lists company users (name, email, role) and
  pending invites (email, created, expires) with revoke buttons.
- `POST /team/invites` (owner, CSRF): form `email`, `name`. Generates raw
  token = `secrets.token_urlsafe(32)`; stores only its sha256; writes an
  OutboxEmail whose body contains the absolute accept path
  `/invite/<raw-token>`; re-renders /team. Inviting an email that already
  belongs to a user **in this company** or has a pending (unexpired,
  unused, unrevoked) invite → form error, no new row.
- `POST /team/invites/{id}/revoke` (owner, CSRF, tenant-scoped 404): sets
  `revoked_at`; a revoked token can never be accepted.
- `GET /invite/{token}` (PUBLIC, no session): hash the presented token,
  look up. Valid (exists, unused, unrevoked, unexpired) → form asking for
  password (min 8). Invalid in ANY way → **404** with a generic
  "invite invalid or expired" page — same response for wrong/used/revoked/
  expired (no oracle distinguishing them).
- `POST /invite/{token}`: same validity check, then creates User (`role=
  "crew"`, email/name from the invite, company from the invite), stamps
  `used_at`, logs the new user in, 303 → `/`. Single-use: the check and
  stamp happen atomically in one transaction; a second POST with the same
  token → 404. If a user with that email now exists globally → 404 (treat
  as spent).
- Invite acceptance is exempt from CSRF (no session yet) but the accept POST
  must only ever act on the token in the URL path.

**Standing invariant:** the project is typed strict on both sides — mypy config is pinned in `pilot/greenlane/pyproject.toml` and strict JSDoc/tsc config in `pilot/greenlane/tsconfig.json`. Fully annotate all new application code: `python -m mypy app` and `npm run typecheck` (both from `pilot/greenlane/`) must stay at zero errors; any `.js` you add under `app/static/` must be JSDoc-typed.

## Acceptance criteria

1. Owner invites → OutboxEmail row exists containing a token that accepts
   successfully; resulting user has role `crew`, correct company, bcrypt
   password; invite marked used.
2. The DB never contains a raw token (grep the invites table: 64-hex hashes
   only).
3. Accept fails with 404 for: unknown token, already-used token, revoked
   token, expired token (freeze time or backdate `expires_at`), and each
   failure leaves user count unchanged.
4. Crew member requesting `GET /team` → 403. Owner of company A revoking a
   company-B invite id → 404, invite untouched.
5. Inviting a duplicate pending email creates no second invite row.

## Non-goals

No real SMTP, no invite resend, no crew removal/deactivation, no role
changes. Do not touch anything outside `pilot/greenlane/`.
