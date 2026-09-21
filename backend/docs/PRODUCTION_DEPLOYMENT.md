# CRPF Tender Evaluation Platform — Production Deployment Guide

## 1. System Architecture

```text
               Internet / Intranet
                       │
             ┌─────────▼─────────┐
             │    Reverse Proxy  │ (Nginx / TLS 1.3 / Port 80/443)
             │   (nginx/nginx.conf)
             └─────────┬─────────┘
                       │ HTTP (Internal Isolated Bridge Network)
             ┌─────────▼─────────┐
             │   FastAPI Backend │ (Uvicorn / Non-root Container / Port 8000)
             │   (backend_prod)  │
             └────┬────┬────┬────┘
                  │    │    │
       ┌──────────┘    │    └──────────┐
       ▼               ▼               ▼
┌──────────────┐┌──────────────┐┌──────────────┐
│  PostgreSQL  ││ MinIO / S3   ││  OPA Engine  │
│ 16+ pgvector ││Object Storage││ (Port 8181)  │
└──────▲───────┘└──────▲───────┘└──────────────┘
       │               │
       └───────┬───────┘
               │
     ┌─────────┴─────────┐
     │  Document Worker  │ (Async Queue Daemon / Atomic Lock / Crash Recovery)
     └───────────────────┘
```

---

## 2. Production Prerequisites

1. **Host Environment**:
   - Enterprise Linux (RHEL 9 / Rocky Linux 9 / Debian 12 / Ubuntu 22.04 LTS).
   - Docker Engine 24.0+ & Docker Compose v2.20+.
   - Dedicated persistent volume mount points for `/var/lib/postgresql/data` and `/data`.
2. **Network & Ingress**:
   - Outbound egress restricted to authorized LLM endpoints if remote AI extraction is enabled.
   - Inbound ingress on Ports 80 and 443 only.
   - Internal microservice ports (`5432`, `9000`, `9001`, `8181`) bound strictly to internal Docker bridge networks.
3. **Security Prerequisites (Phase 19)**:
   - Secret hygiene: `JWT_SECRET_KEY` generated via `openssl rand -hex 32`.
   - Strong database and storage credentials configured in `.env`.
   - CORS origin set to official CRPF procurement domain (e.g. `https://tender.crpf.gov.in`).
   - Rate limiting and security response headers enabled.

---

## 3. Deployment Sequence (Step-by-Step)

### Step 1: Environment & Secrets Provisioning
```bash
cd /opt/crpf-tender/backend

# Create production environment file from template
cp .env.example .env
chmod 600 .env

# Populate real production secrets (DB password, S3 credentials, JWT key)
vim .env
```

### Step 2: Build Hardened Container Images
```bash
docker compose -f docker-compose.prod.yml build --no-cache
```

### Step 3: Start Core Data & Policy Services
```bash
docker compose -f docker-compose.prod.yml up -d postgres minio opa

# Verify services have reached healthy state
docker compose -f docker-compose.prod.yml ps
```

### Step 4: Execute Database Migrations
```bash
# Apply all version-controlled migrations deterministically
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# Verify migration state
docker compose -f docker-compose.prod.yml run --rm backend alembic current
```

### Step 5: Launch API Backend, Document Workers & Ingress Gateway
```bash
docker compose -f docker-compose.prod.yml up -d backend document-worker nginx
```

### Step 6: Verify Service Readiness
```bash
# Check process liveness
curl -s -f http://localhost:8000/api/v1/health/live | jq .

# Check dependency readiness (PostgreSQL, MinIO/S3, OPA)
curl -s -f http://localhost:8000/api/v1/health/ready | jq .
```

---

## 4. Database Migration Management

All database schema evolutions must be tracked through version-controlled Alembic migrations.
- **Never** use `SQLAlchemy.metadata.create_all()` in production.
- **Applying Migrations**:
  ```bash
  docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
  ```
- **Checking Migration History**:
  ```bash
  docker compose -f docker-compose.prod.yml run --rm backend alembic history --verbose
  ```
- **Verifying Target Revision**:
  ```bash
  docker compose -f docker-compose.prod.yml run --rm backend alembic check
  ```

---

## 5. Rollback Strategy

In the event of a deployment failure or regression:

### 5.1 Application Code Rollback
```bash
# Roll back to the previous stable Docker image tag
docker compose -f docker-compose.prod.yml down backend document-worker
docker compose -f docker-compose.prod.yml up -d backend document-worker
```

### 5.2 Database Migration Rollback Guidelines
- **Rule**: Never blindly roll database migrations backwards (`alembic downgrade -1`) in an active production environment, as this risks catastrophic data loss.
- **Forward-Fix Rollback**:
  - Prefer applying a new forward-compatible migration (`alembic upgrade head`) that restores previous column behaviors safely without dropping existing tables or records.
- **Disaster Recovery Restore**:
  - If a destructive schema change corrupted data, follow the recovery procedure in [BACKUP_AND_RESTORE.md](file:///d:/tender/backend/docs/BACKUP_AND_RESTORE.md) using a pre-deployment database snapshot.

---

## 6. Service Management & Maintenance

### Restarting the Entire Stack Gracefully
```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Viewing Logs with Security Filter Verification
```bash
docker compose -f docker-compose.prod.yml logs -f --tail=50 backend
docker compose -f docker-compose.prod.yml logs -f --tail=50 document-worker
```
