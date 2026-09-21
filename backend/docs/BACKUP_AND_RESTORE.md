# PostgreSQL & Object Storage Backup & Disaster Recovery Playbook

## 1. Overview
This document defines the production backup, disaster recovery, and dual-consistency verification procedures for the **CRPF Tender Evaluation & Eligibility Analysis Platform**.

---

## 2. Backup Strategy

### 2.1 Backup Types & Frequency
- **Full Logical Database Backups (`pg_dump`)**: Nightly automated execution at 02:00 IST.
- **Continuous Archiving / Write-Ahead Logging (WAL)**: Enabled via `archive_mode = on` for Point-in-Time Recovery (PITR).
- **Object Storage Snapshots (MinIO / S3)**: Continuous sync and cross-region replication of the `tender-documents` bucket.
- **Atomic Dual Snapshotting**: Prior to any major system upgrade or schema migration, take a simultaneous snapshot of both PostgreSQL and Object Storage.

### 2.2 Retention Policy
- Daily backups retained for 30 days.
- Weekly backups retained for 12 weeks.
- Monthly backups retained for 7 years (Mandated by Government Procurement Compliance).
- Encrypted at rest using AES-256 (GPG / AWS KMS).

---

## 3. Automated Backup Procedures

### 3.1 Logical Database Backup Script
```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/crpf_tender"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/tender_db_${TIMESTAMP}.dump"
ENCRYPTED_FILE="${BACKUP_FILE}.gpg"

mkdir -p "${BACKUP_DIR}"

# 1. Execute compressed custom-format pg_dump
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
  -h "${POSTGRES_SERVER}" \
  -p "${POSTGRES_PORT}" \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  -F c -b -v -f "${BACKUP_FILE}"

# 2. Encrypt backup archive with GPG
gpg --batch --yes --encrypt --recipient "crpf-procurement-security@crpf.gov.in" \
  --output "${ENCRYPTED_FILE}" "${BACKUP_FILE}"

# 3. Securely remove unencrypted raw dump
rm -f "${BACKUP_FILE}"

# 4. Sync to offsite immutable/WORM storage
aws s3 cp "${ENCRYPTED_FILE}" "s3://crpf-tender-backups/database/${TIMESTAMP}/" --sse aws:kms

echo "[SUCCESS] Backup completed: ${ENCRYPTED_FILE}"
```

### 3.2 Object Storage Bucket Replication
```bash
#!/usr/bin/env bash
set -euo pipefail

# Sync primary tender documents bucket to backup snapshot repository
aws s3 sync s3://tender-documents s3://crpf-tender-backups/storage-snapshots/$(date +"%Y%m%d")/ \
  --exact-timestamps \
  --sse aws:kms
```

---

## 4. Disaster Recovery & Restoration Procedure

### 4.1 Prerequisites
- Target PostgreSQL 16+ instance with `pgvector` extension installed.
- S3/MinIO target bucket created and accessible.
- Decryption key for the GPG-encrypted dump file.

### 4.2 Step-by-Step Restoration
```bash
# 1. Download and decrypt the target database backup
aws s3 cp "s3://crpf-tender-backups/database/20260918_020000/tender_db_20260918_020000.dump.gpg" ./
gpg --decrypt --output tender_db.dump tender_db_20260918_020000.dump.gpg

# 2. Terminate active database connections
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h localhost -U postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='tender_evaluation' AND pid <> pg_backend_pid();"

# 3. Restore PostgreSQL schema and data
PGPASSWORD="${POSTGRES_PASSWORD}" pg_restore \
  -h localhost \
  -p 5432 \
  -U postgres \
  -d tender_evaluation \
  --clean --if-exists --no-owner --no-privileges -v tender_db.dump

# 4. Restore corresponding Object Storage binaries
aws s3 sync s3://crpf-tender-backups/storage-snapshots/20260918/ s3://tender-documents/

# 5. Run Alembic migration check
alembic upgrade head

# 6. Clean up unencrypted local dump
rm -f tender_db.dump
```

---

## 5. Dual-Consistency Verification & Integrity Drills
Quarterly automated disaster recovery drills must verify:
1. **Row Count Parity**: Verify matching entity counts across `tenders`, `tender_versions`, `documents`, `bidder_submissions`, `tender_criteria`, `bidder_evidence`, and `evaluation_reports`.
2. **SHA-256 Checksum Verification**: Every restored document's stored hash matches the byte-by-byte SHA-256 computation of the object in storage.
3. **Audit Trail Continuity**: Cryptographic integrity validation of append-only audit events with zero sequence gaps.
