# CRPF Tender Evaluation Platform — Operational Runbook

## 1. System Overview & Service Topology
The platform operates as a secure, distributed system composed of:
1. **API Gateway / Ingress**: Nginx (TLS 1.3, rate limiting, request buffer tuning).
2. **Backend API**: FastAPI running under non-root Uvicorn workers.
3. **Database Layer**: PostgreSQL 16 with `pgvector` extension for transactional metadata and hybrid retrieval embeddings.
4. **Object Storage**: S3-compatible storage (MinIO / AWS S3) for original tender PDFs, bidder submissions, extracted JSON artifacts, and signed evaluation reports.
5. **Deterministic Policy Engine**: Open Policy Agent (OPA) evaluating locked Rego policies for eligibility determination.
6. **Async Document Worker**: Python background daemon polling PostgreSQL for queued document ingestion jobs.

---

## 2. Common Operational Tasks

### 2.1 Starting the Production Stack
```bash
# Verify environment configuration and secrets
test -f .env || { echo "Missing .env file"; exit 1; }

# Start infrastructure services (PostgreSQL, MinIO, OPA)
docker compose -f docker-compose.prod.yml up -d postgres minio opa

# Execute database migrations
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# Start API backend and Document Workers
docker compose -f docker-compose.prod.yml up -d backend document-worker nginx
```

### 2.2 Verifying Service Health & Readiness
```bash
# 1. Check Liveness (Process is responding)
curl -s -f http://localhost:8000/api/v1/health/live | jq .

# 2. Check Readiness (Database, Object Storage, OPA are connected)
curl -s -f http://localhost:8000/api/v1/health/ready | jq .
```
Expected readiness output:
```json
{
  "status": "ready",
  "components": {
    "database": { "status": "connected" },
    "storage": { "status": "ready" },
    "opa": { "status": "ready" }
  }
}
```

---

## 3. Incident Response & Troubleshooting

### Scenario A: Database Unreachable or Connection Pool Exhaustion
**Symptoms**: `/health/ready` returns HTTP 503 with `"database": {"status": "unreachable"}`.
**Action**:
1. Check PostgreSQL container status and logs:
   ```bash
   docker compose -f docker-compose.prod.yml logs --tail=100 postgres
   ```
2. Verify connection count:
   ```sql
   SELECT count(*), state FROM pg_stat_activity GROUP BY state;
   ```
3. Adjust pool settings in `.env` if legitimate load exceeds capacity:
   ```env
   DB_POOL_SIZE=20
   DB_MAX_OVERFLOW=30
   ```
4. Restart backend gracefully:
   ```bash
   docker compose -f docker-compose.prod.yml restart backend
   ```

### Scenario B: Object Storage Outage
**Symptoms**: Upload/download operations fail with storage connection errors.
**Action**:
1. Verify storage health probe:
   ```bash
   docker compose -f docker-compose.prod.yml logs --tail=100 minio
   ```
2. Ensure target bucket exists:
   ```bash
   # Using AWS CLI / MinIO Client
   mc ls myminio/tender-documents
   ```
3. Check permissions and credentials configured in `.env`.

### Scenario C: OPA Policy Engine Failure
**Symptoms**: Evaluation requests fail or return 500 error indicating policy evaluation failure.
**Action**:
1. Verify OPA container health:
   ```bash
   curl -f http://localhost:8181/health
   ```
2. Verify policy package compilation:
   ```bash
   docker compose -f docker-compose.prod.yml exec opa opa check /policies
   ```
3. Restart OPA service:
   ```bash
   docker compose -f docker-compose.prod.yml restart opa
   ```

### Scenario D: Stalled Document Ingestion Jobs
**Symptoms**: Documents remain in `QUEUED` or `PROCESSING` state for longer than `PROCESSING_TIMEOUT_SECONDS` (120s).
**Action**:
1. Inspect Document Worker logs:
   ```bash
   docker compose -f docker-compose.prod.yml logs -f document-worker
   ```
2. The worker automatically recovers stalled jobs on startup using `recover_stalled_jobs(db)`. To trigger recovery, restart the worker container:
   ```bash
   docker compose -f docker-compose.prod.yml restart document-worker
   ```

---

## 4. Database & Object Storage Consistency Reconciliation

### 4.1 Consistency Principles
- **PostgreSQL** holds authoritative relational records and metadata.
- **Object Storage** holds binary blobs (original documents, normalized artifacts, PDF reports).
- **Rule**: PostgreSQL records reference `storage_key`. Binary files must never be modified in place.
- **Integrity**: Every document record contains a `sha256_hash` computed upon upload.

### 4.2 Detecting Inconsistencies
Run the periodic audit script or query missing storage objects:
```python
# Periodic integrity scan script
from app.db.session import SessionLocal
from app.db.models.document import Document
from app.storage.service import get_storage_service

storage = get_storage_service()
with SessionLocal() as db:
    docs = db.query(Document).all()
    for doc in docs:
        if not storage.exists(doc.storage_key):
            print(f"[ALERT] Missing object storage key for Document ID {doc.id}: {doc.storage_key}")
```

### 4.3 Recovery Without Silent Deletions
1. Never delete database records when an object is missing, as this destroys the legal audit trail.
2. Flag the document status as `STORAGE_INCONSISTENCY` in PostgreSQL.
3. Retrieve the missing object from the immutable WORM backup snapshot using the matching `sha256_hash`.
4. Restore the blob to `storage_key` and verify SHA-256 checksum match.

---

## 5. Scaling Strategy

### 5.1 Horizontal API Scaling
The FastAPI backend is completely stateless:
```bash
# Scale API backend to 3 replicas
docker compose -f docker-compose.prod.yml up -d --scale backend=3
```
- Nginx upstream balances load round-robin across replicas.
- Session state is purely JWT-driven; no sticky sessions required.

### 5.2 Worker Concurrency Scaling
Heavy OCR and document parsing workloads are handled by document workers:
```bash
# Scale workers to 4 instances
docker compose -f docker-compose.prod.yml up -d --scale document-worker=4
```
- PostgreSQL atomic job queue locking (`FOR UPDATE SKIP LOCKED`) guarantees exactly-once job pickup across concurrent worker instances.

### 5.3 Database Connection Pool Sizing
When scaling backend and worker replicas:
$$\text{Max PostgreSQL Connections} \ge (\text{Backend Replicas} \times (\text{DB\_POOL\_SIZE} + \text{DB\_MAX\_OVERFLOW})) + (\text{Worker Replicas} \times 10) + 20$$

---

## 6. Logging & Observability

- All logs adhere to structured key-value formatting.
- `X-Request-ID` is assigned at the Nginx edge and propagated through FastAPI and downstream logging.
- Sensitive information (passwords, JWTs, Bearer headers, database credentials) is masked with `***REDACTED***` by `SensitiveDataMaskingFilter`.
