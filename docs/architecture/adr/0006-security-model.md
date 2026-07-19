# ADR 0006 — Security model: JWT + Argon2id + RBAC + audit

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
NexGuard is an enterprise security product handling sensitive telemetry. It must
be treated as a hardened application from the first slice, not retrofitted.

## Decision
- **Passwords:** Argon2id (memory-hard) via `argon2-cffi`. Never store or log
  plaintext; never a fast hash (bcrypt acceptable fallback, Argon2id preferred).
- **AuthN:** short-lived access JWTs (signed, `exp`, `iat`, `jti`) + refresh
  token rotation. Secret is env-injected; algorithm pinned; tokens validated on
  every request.
- **AuthZ:** RBAC with roles `admin` / `analyst` / `viewer`, enforced by a
  FastAPI dependency at the router level (least privilege — e.g. only `analyst`+
  can label feedback, only `admin` can change thresholds/config).
- **Audit:** every privileged action writes an append-only `audit_logs` row
  (actor, action, resource, ip, timestamp, metadata).
- **Transport/headers:** CSP, HSTS, X-Frame-Options, X-Content-Type-Options via
  middleware.
- **Input validation:** all external input is Pydantic-validated; errors return
  RFC-9457 `problem+json`.
- **Rate limiting:** per-identity token-bucket in Redis; sensible auth-endpoint
  limits to blunt brute force.
- **Secrets:** `pydantic-settings` from env; `.env` git-ignored; `.env.example`
  documents required vars with no real values.

## Consequences
- Security is on the request path from slice one.
- Adds middleware + dependencies + an audit write — accepted, non-negotiable for
  this product class.
