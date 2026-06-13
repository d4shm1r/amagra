# Security Policy

Amagra is a self-hosted, local-first AI runtime. By default everything runs on your own hardware and no data leaves the machine. Still, the project ships an HTTP API, an auth layer, and an agent runtime — so we take security reports seriously.

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅ |
| < 1.0   | ❌ (pre-release internal builds) |

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately via one of:

- GitHub's **[Report a vulnerability](https://github.com/d4shm1r/amagra/security/advisories/new)** (Security → Advisories), or
- Email **d4shm1r@hotmail.com** with the subject `SECURITY: amagra`.

Include: affected version/commit, a description, reproduction steps or a proof of concept, and the impact you believe it has. We aim to acknowledge within a few days and to coordinate a fix and disclosure timeline with you.

## Scope & hardening notes

- The API is **deny-by-default** when `REQUIRE_AUTH=1` — only the `_PUBLIC_PATHS` allowlist is reachable without an API key. The admin surface additionally requires `ADMIN_TOKEN`.
- Run with `REQUIRE_AUTH=1`, a locked `ALLOWED_ORIGINS` (no wildcard), and a strong `ADMIN_TOKEN` in any networked deployment.
- Treat the SQLite databases and uploaded documents as sensitive — they hold memory, decisions, and file context.
- Reports about reachable RCE, auth bypass, path traversal in document/file handling, or tenant-scope leakage are highest priority.

Thank you for helping keep Amagra and its users safe.
