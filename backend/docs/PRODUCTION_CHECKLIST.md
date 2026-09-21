# CRPF Tender Evaluation Platform — Production Readiness Checklist

## 1. Security & Cryptography
- [x] **Secret Hygiene**: Zero hardcoded passwords, tokens, or JWT secrets in repository.
- [x] **Production Secret Validation**: Application halts if default `change-me` JWT secret is used with `ENVIRONMENT=production`.
- [x] **Authentication & RBAC**: Strict JWT validation, password hashing with bcrypt, role-permission verification on all endpoints.
- [x] **IDOR & Scope Isolation**: Tender version, bidder, submission, and document isolation enforced across all APIs.
- [x] **Security Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `HSTS` active.
- [x] **CORS Hardening**: Wildcard `*` disallowed with credentials in production.
- [x] **Rate Limiting**: Sliding-window rate limiter preventing brute-force login, upload abuse, and report scraping.
- [x] **Upload Security**: Magic-byte signature verification, path traversal prevention, SHA-256 integrity hashing, page count limits.

## 2. Database & Storage
- [x] **Alembic Migrations**: Complete migrations (0001 through 0013) verify from empty DB to latest head cleanly.
- [x] **Connection Pooling**: Configurable connection pool size, overflow, timeout, and recycle limits.
- [x] **Index Coverage**: B-tree indexes across all foreign keys, lookup codes, and search queries.
- [x] **Private Storage**: MinIO / S3 buckets configured with private access and server-side encryption.
- [x] **Backup Playbook**: Documented logical dump, WAL archiving, GPG encryption, and restore verification.

## 3. Deterministic AI & OPA Decision Architecture
- [x] **AI Separation**: LLM extraction is restricted to document parsing and evidence structuring; LLM cannot make eligibility decisions.
- [x] **Deterministic Rules**: OPA / Rego is the sole deterministic decision engine.
- [x] **Review & Override**: Human officers make final procurement decisions without mutating underlying automated evaluation snapshots.

## 4. Audit, Provenance & Reporting
- [x] **Append-Only Audit**: All critical actions logged with actor identity, timestamp, and state snapshots.
- [x] **20-Point Explainability**: Complete provenance linking Tender -> Version -> Criteria -> Evidence -> OPA -> Review -> Report.
- [x] **Report Integrity**: Multi-page PDF reports generated with ReportLab and stamped with SHA-256 integrity checksums.

## 5. Reliability & Observability
- [x] **Health Probes**: Distinct `/health/live` (process alive) and `/health/ready` (dependency checks).
- [x] **Structured Logging**: Timestamped, leveled, correlation-tracked (`X-Request-ID`), with sensitive data masking.
- [x] **Worker Recovery**: Background worker automatically recovers stalled jobs after crashes.
- [x] **Graceful Shutdown**: Signal handling for `SIGINT` and `SIGTERM`.
