# Security Policy

NexGuard is a security product, so it holds itself to the bar it sets. This
document summarizes the threat model, the controls in place, and how to report a
vulnerability.

## Reporting a vulnerability

Please report security issues privately (do not open a public issue): email the
maintainer or open a GitHub Security Advisory. We aim to acknowledge within 72
hours. Include reproduction steps and impact.

## Threat model (summary)

NexGuard ingests sensitive security telemetry and drafts incident reports with a
local LLM. The primary assets are: the telemetry/log data, analyst accounts, and
the integrity of alerts/reports. Key threats and mitigations:

| Threat | Mitigation |
|--------|------------|
| Credential theft / brute force | Argon2id hashing, short-lived JWTs, per-IP auth rate limiting, timing-equalized login |
| Privilege escalation | RBAC (`admin`/`analyst`/`viewer`) enforced at every mutating route |
| Data exfiltration to third parties | **Local-first**: no cloud APIs; the LLM is a local Ollama model |
| **LLM hallucination / fabricated evidence** | Hard verification gate rejects any report citing hosts/timestamps/events/components absent from real evidence; MITRE techniques are structurally hypotheses only |
| Injection (SQL/NoSQL/template) | Parameterized SQLAlchemy, Pydantic-validated input, no string-built queries |
| Clickjacking / XSS | `frame-ancestors 'none'`, CSP, `X-Content-Type-Options: nosniff` |
| Secret leakage | Env-injected secrets, `.env` git-ignored, production rejects a weak/default JWT secret at startup |
| Untrusted deserialization | Model weights loaded with `weights_only=True`; joblib artifacts loaded only from the operator-controlled artifact dir |

## Controls

- **AuthN:** JWT (HS256), short-lived access tokens (15 min default) + refresh token
  rotation (`POST /api/v1/auth/refresh`), unique `jti` per token for future revocation.
- **AuthZ:** role hierarchy enforced by a FastAPI dependency; least privilege.
- **Passwords:** Argon2id (memory-hard); never stored or logged in plaintext.
- **Transport/headers:** CSP, HSTS, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy` on both API and frontend.
- **Rate limiting:** per-identity token buckets; stricter budget on auth endpoints.
- **Audit:** append-only audit log of every privileged action (actor, action,
  resource, ip, timestamp).
- **Input validation:** Pydantic v2 on every request and on all LLM output;
  errors returned as RFC-9457 `problem+json`.
- **Supply chain:** pinned lockfiles (`uv.lock`, `package-lock.json`); CI runs
  `pip-audit`, `npm audit`, and a secrets scan.

## Known limitations

- Rate limiting is per-process in-memory; a multi-instance deployment should back
  it with Redis.
- CSP uses `'unsafe-inline'`/`'unsafe-eval'` for Next.js runtime; nonce-based CSP
  is the production hardening step.
- The compose demo ships a demo JWT secret and Grafana credentials — replace both
  for any real deployment.
