# AI-Based Tender Evaluation & Eligibility Analysis Platform for CRPF Procurement — Backend

This repository contains the backend API and database infrastructure for the **AI-Based Tender Evaluation & Eligibility Analysis Platform for CRPF Procurement**. The platform provides an evidence-driven, deterministic evaluation system where AI extracts structured criteria and evidence from procurement documents, deterministic rules evaluate compliance, and human procurement officers retain final approval authority.

---

## Architecture & Principles

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 with modern SQLAlchemy 2.x ORM
- **Migrations**: Alembic with declarative schema tracking
- **Driver**: Psycopg 3 (`postgresql+psycopg://`)
- **Authentication**: JWT access tokens (PyJWT) with Argon2id password hashing
- **Authorization**: Granular Role-Based Access Control (RBAC) with normalized database entities
- **Configuration**: Pydantic Settings with environment variable support
- **Logging**: Centralized, structured standard logging
- **Error Handling**: Centralized exception handlers ensuring sanitized API responses
- **Containerization**: Docker & Docker Compose with persistent named volumes

---

## Authentication & RBAC Architecture

### 1. Relational Model

```text
User ────< user_roles >──── Role ────< role_permissions >──── Permission
```

### 2. Predefined Roles & Capabilities

- **`ADMIN`**: Full platform administrative permissions (user management, system configuration, all tender & review operations).
- **`PROCUREMENT_OFFICER`**: Tender lifecycle and criteria approval operations (`TENDER_CREATE`, `TENDER_APPROVE`, `DOCUMENT_UPLOAD`, `REVIEW_APPROVE`, etc.).
- **`REVIEWER`**: Evidence review, verification, and evaluation assessment (`TENDER_READ`, `EVIDENCE_READ`, `EVALUATION_READ`, `REVIEW_CREATE`, `REPORT_READ`).

### 3. Password Security

- Passwords are hashed using **Argon2id** (`argon2-cffi`).
- Minimum password length policy enforced server-side.
- Plaintext passwords and password hashes are never returned via API responses or logged.

---

## Tender Management & Versioning Architecture (Phase 4)

### 1. Relational Model

```text
Tender ────< 1:N >──── TenderVersion
```

- **`Tender`**: Represents the root procurement opportunity entity with a unique, business-scoped `tender_number`, lifecycle status (`DRAFT`, `PUBLISHED`, `CLOSED`, `CANCELLED`), and metadata.
- **`TenderVersion`**: Represents a specific version snapshot of the tender specifications, criteria, and requirements. Contains a sequentially scoped `version_number` (1, 2, 3...) per tender, change summary, and an `is_active` flag.

### 2. Versioning Mechanics & Rules

- **Atomic Creation**: Creating a tender automatically and atomically initializes `Version 1` as the active version.
- **Single Active Version**: Exactly one `TenderVersion` per `Tender` is active at any time. Activating a new version automatically deactivates the previous active version.
- **Historical Immutability**: Previous versions are preserved with their original requirements, metadata, and timestamps.
- **Concurrency Safety**: New version creation uses row-level locking (`with_for_update()`) on the parent tender to guarantee strictly monotonic version numbers under concurrent load.

---

## Secure Document Ingestion & Object Storage Architecture (Phase 5)

### 1. Dual-Storage Architecture

```text
Client Upload
     ↓
FastAPI Backend (Authentication, RBAC, Multi-layer Validation, SHA-256)
     ├── Actual Binary Files ───────> Object Storage (MinIO / AWS S3)
     └── Document Metadata & Hash ──> PostgreSQL Database
```

- **PostgreSQL**: Stores metadata only (`id`, `tender_id`, `tender_version_id`, `filename`, `content_type`, `file_extension`, `file_size`, `sha256_hash`, `storage_key`, `document_type`, `processing_status`, `uploaded_by`, `timestamps`). Raw file binaries are never stored in PostgreSQL.
- **Object Storage**: S3-compatible object storage (MinIO locally in Docker, AWS S3 in production) stores original binaries under deterministic, server-generated keys:
  `documents/tender/{tender_id}/version/{tender_version_id}/{document_id}/{safe_filename}`.

### 2. Multi-Layer Security & Ingestion Engine

- **Supported File Formats**: PDF (`.pdf`), Microsoft Word (`.doc`, `.docx`), Excel Spreadsheets (`.xlsx`), Images (`.jpg`, `.jpeg`, `.png`).
- **Magic Bytes & Signature Verification**: Validates file content headers against claimed extensions (PDF header `%PDF-`, JPEG `\xFF\xD8\xFF`, PNG `\x89PNG`, OLE DOC `\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1`, ZIP container `PK\x03\x04` with internal `[Content_Types].xml` manifest).
- **MIME & Executable Spoofing Defense**: Explicitly rejects executable binaries (`MZ`, `ELF`) and embedded script/HTML payloads spoofed as documents.
- **Archive Safety**: Raw `.zip` files are rejected. DOCX/XLSX zip containers are inspected for excessive file count (>5000) and dangerous expansion ratios to prevent zip bombs.
- **Path Traversal Prevention**: Strips and sanitizes client filenames. Storage keys are generated purely server-side with UUIDs.
- **SHA-256 Hashing**: Computed chunk-by-chunk during streaming upload.
- **Configurable Size Limits**: Enforced streaming chunk-by-chunk via `MAX_UPLOAD_SIZE_MB` (default 50 MB) without loading entire files into memory.
- **Compensatory Transaction Safety**: If PostgreSQL metadata recording fails after storage upload, the orphaned object is automatically deleted from storage and rolled back.
- **Strict Retention**: No public `DELETE` endpoint is exposed to maintain procurement auditability.

---

---

## Document Processing Pipeline Architecture (Phase 6)

### 1. Processing Flow

```text
Upload & Ingestion (Phase 5)
     ↓
Enqueue Job (`document_processing_jobs`, JobStatus.QUEUED)
     ↓
Worker Daemon (`app.workers.document_worker`)
     ├── Locks next available job (`SELECT FOR UPDATE SKIP LOCKED`)
     ├── Downloads binary from Object Storage (MinIO / S3)
     ├── Dispatches to Format-Specific Parser (PDF, DOCX, XLSX, Images)
     ├── Extracts Structured Representation (pages, blocks, tables, bounding boxes)
     ├── Stores Normalized JSON Artifact (`artifacts/normalized_content.json`)
     └── Records `processing_artifacts` metadata & transitions job to `COMPLETED`
```

### 2. Multi-Format Parsers

- **Digital & Scanned PDF**: Extracts text streams, structural blocks, tabular structures, and performs OCR fallback for image-only pages. Enforces strict `MAX_PARSER_PAGES` limits to prevent resource exhaustion.
- **Office Documents (DOCX)**: Iterates headings, paragraphs, and structured table grids into normalized page blocks.
- **Spreadsheets (XLSX)**: Parses individual sheets into 2D tabular cell matrixes with column metadata.
- **Images (JPEG, PNG)**: Verifies pixel dimensions (`MAX_IMAGE_PIXELS`) to prevent decompression bombs and extracts blocks via OCR preprocessing.

### 3. Normalized Content Schema

Processing outputs are serialized to JSON adhering to the `NormalizedDocument` schema:

- `document_id`: Source document UUID
- `filename`, `file_extension`, `document_type`: Inferred type
- `total_pages`: Extracted page count
- `pages`: List of `DocumentPage` items containing `DocumentBlock` items (`PARAGRAPH`, `HEADING`, `TABLE`, `LIST_ITEM`, `IMAGE_REGION`) with bounding boxes and table matrices.

### 4. Background Processing Worker Daemon

The worker runs as an independent daemon service in Docker Compose (`crpf_tender_document_worker`):

```bash
python -m app.workers.document_worker
```

- Fully decoupled from web request threads.
- Controlled exponential retry loop up to `MAX_JOB_ATTEMPTS` (default 3).
- Concurrency-safe job dispatching with row-level locking.

---

## Prerequisites

- **Python**: 3.11+
- **Docker**: Docker Engine 24+ & Docker Compose v2+

---

## Local Development Setup

### 1. Create and Activate Virtual Environment

**On Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**On Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the example environment configuration:

```bash
cp .env.example .env
```

Key configuration variables:

- `APP_NAME`: `CRPF Tender Evaluation API`
- `APP_VERSION`: `0.1.0`
- `ENVIRONMENT`: `development`
- `DEBUG`: `True`
- `API_V1_PREFIX`: `/api/v1`
- `LOG_LEVEL`: `INFO`
- `POSTGRES_SERVER`: `localhost`
- `POSTGRES_PORT`: `5432`
- `POSTGRES_USER`: `postgres`
- `POSTGRES_PASSWORD`: `postgres`
- `POSTGRES_DB`: `tender_evaluation`
- `DATABASE_URL`: `postgresql+psycopg://postgres:postgres@localhost:5432/tender_evaluation`
- `JWT_SECRET_KEY`: `change-me-in-development-secure-random-secret-key-32chars`
- `JWT_ALGORITHM`: `HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES`: `60`
- `S3_ENDPOINT`: `http://localhost:9000`
- `S3_ACCESS_KEY`: `minioadmin`
- `S3_SECRET_KEY`: `minioadmin`
- `S3_BUCKET`: `tender-documents`

### 4. Start Infrastructure via Docker Compose

```bash
docker compose up -d postgres minio
```

### 5. Apply Database Migrations

```bash
alembic upgrade head
```

To roll back the latest migration:

```bash
alembic downgrade -1
```

### 6. Run the Development Server and Worker Daemon

**Web API Server:**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Background Worker Daemon:**

```bash
python -m app.workers.document_worker
```

The application will be accessible at `http://localhost:8000`.

---

## API Endpoints & Documentation

### Authentication & Authorization Endpoints

- **`POST /api/v1/auth/login`**: Authenticate with email and password to receive a JWT bearer access token.
- **`GET /api/v1/auth/me`**: Retrieve the profile, assigned roles, and permissions of the currently authenticated user (`Authorization: Bearer <token>`).
- **`GET /api/v1/auth/admin-test`**: Protected endpoint requiring `USER_MANAGE` permission to verify RBAC enforcement.

### Tender Management & Versioning Endpoints

- **`POST /api/v1/tenders`**: Create a new procurement tender and initialize Version 1 (Requires `TENDER_CREATE`).
- **`GET /api/v1/tenders`**: List tenders with pagination and optional status filter (Requires `TENDER_READ`).
- **`GET /api/v1/tenders/{tender_id}`**: Get tender details along with its active version (Requires `TENDER_READ`).
- **`PATCH /api/v1/tenders/{tender_id}`**: Update tender metadata and lifecycle status (Requires `TENDER_UPDATE`).
- **`POST /api/v1/tenders/{tender_id}/versions`**: Create a new sequential version for a tender (Requires `TENDER_UPDATE`).
- **`GET /api/v1/tenders/{tender_id}/versions`**: List all historical and active versions for a tender (Requires `TENDER_READ`).
- **`GET /api/v1/tenders/{tender_id}/versions/{version_number}`**: Get a specific historical version snapshot (Requires `TENDER_READ`).

### Document Ingestion & Storage Endpoints (Phase 5)

- **`POST /api/v1/tenders/{tender_id}/versions/{version_id}/documents`**: Upload and ingest a procurement document for a tender version (Requires `DOCUMENT_UPLOAD`).
- **`GET /api/v1/documents/{document_id}`**: Retrieve document metadata and processing status (Requires `DOCUMENT_READ`).
- **`GET /api/v1/documents/{document_id}/download`**: Securely stream and download document binary from object storage (Requires `DOCUMENT_READ`).
- **`GET /api/v1/tenders/{tender_id}/versions/{version_id}/documents`**: List all documents ingested under a tender version (Requires `DOCUMENT_READ`).

### Document Processing Pipeline Endpoints (Phase 6)

- **`GET /api/v1/documents/{document_id}/processing-status`**: Get real-time job processing status, attempt count, and error diagnostics (Requires `DOCUMENT_READ`).
- **`GET /api/v1/documents/{document_id}/content`**: Retrieve normalized structured JSON content artifact (Requires `DOCUMENT_READ`).
- **`POST /api/v1/documents/{document_id}/process`**: Manually trigger document reprocessing / re-enqueue (Requires `DOCUMENT_UPLOAD`).

### Tender Understanding & Criterion Extraction Endpoints (Phase 7)

- **`POST /api/v1/tenders/{tender_id}/versions/{version_id}/criteria/extract`**: Trigger AI-assisted candidate eligibility criteria extraction (Requires `TENDER_UPDATE`).
- **`GET /api/v1/tenders/{tender_id}/versions/{version_id}/criteria/extraction-status`**: Check latest AI extraction run status and model/prompt metadata (Requires `TENDER_READ`).
- **`GET /api/v1/tenders/{tender_id}/versions/{version_id}/criteria`**: List candidate criteria with category/status filters and pagination (Requires `TENDER_READ`).
- **`GET /api/v1/tenders/{tender_id}/versions/{version_id}/criteria/{criterion_id}`**: Get detailed criterion with exact source clause and location attribution (Requires `TENDER_READ`).

### Health Check

- **`GET /api/v1/health`**: Returns application and live database connectivity status.

### Interactive Documentation

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## Automated Testing

Run the entire automated test suite using `pytest`:

```bash
pytest -v
```

### Test Suite Structure

- `tests/unit/`: Tests for parsers (PDF, DOCX, XLSX, Images), security, password hashing, JWTs, Pydantic schemas, and config loading.
- `tests/integration/`: Tests for processing queue lifecycle, async pipeline execution, pipeline API endpoints, login flows, RBAC enforcement, tender management, versioning, document ingestion, and partial failure handling.
- **Database Isolation**: Tests run in-memory against an isolated SQLite database, preventing interference with development or production data.

---

## Docker Deployment

Build and start the complete platform (Backend + Document Worker + PostgreSQL + MinIO):

```bash
docker compose up -d --build
```

Stop containers:

```bash
docker compose down
```
