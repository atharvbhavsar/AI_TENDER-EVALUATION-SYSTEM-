"""Document validation, file signature verification, and security sanitization."""

import hashlib
import io
import os
import re
import uuid
import zipfile
from typing import BinaryIO, Tuple
from fastapi import HTTPException, UploadFile, status

# Allowed file extensions and their corresponding standard MIME types
ALLOWED_EXTENSIONS_MAP = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

# Signatures / Magic bytes
SIGNATURE_PDF = b"%PDF-"
SIGNATURE_JPEG = b"\xff\xd8\xff"
SIGNATURE_PNG = b"\x89PNG\r\n\x1a\n"
SIGNATURE_OLE_DOC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
SIGNATURE_ZIP = b"PK\x03\x04"

# Dangerous executable / script signatures
DANGEROUS_SIGNATURES = [
    b"MZ",  # DOS / Windows PE executable
    b"\x7fELF",  # Linux ELF executable
]


def sanitize_filename(filename: str | None) -> Tuple[str, str]:
    """
    Sanitize an untrusted user-supplied filename.
    Returns (safe_filename, file_extension_lowercase).
    Rejects filenames containing path traversal characters ('..', '/', '\\'), absolute paths, or null bytes.
    """
    if not filename or not filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename must not be empty.",
        )

    trimmed = filename.strip()

    # Reject path traversal, absolute paths, or null bytes in input
    if (
        "\x00" in trimmed
        or ".." in trimmed
        or trimmed.startswith("/")
        or trimmed.startswith("\\")
        or (len(trimmed) >= 2 and trimmed[1] == ":")  # Windows absolute path C:\
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename containing illegal characters or path traversal sequences.",
        )

    # Normalize path separators and extract basename
    normalized = trimmed.replace("\\", "/")
    basename = os.path.basename(normalized).strip()

    if not basename or "\x00" in basename or ".." in basename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename containing illegal characters or path traversal sequences.",
        )

    # Clean characters: allow alphanumeric, dots, hyphens, underscores, spaces
    clean_name = re.sub(r"[^\w\.\-\s]", "_", basename).strip()
    if not clean_name:
        clean_name = "unnamed_document"

    name_part, ext_part = os.path.splitext(clean_name)
    ext_lower = ext_part.lower()

    return clean_name, ext_lower


def generate_storage_key(
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    document_id: uuid.UUID,
    safe_filename: str,
) -> str:
    """Generate a deterministic, server-controlled storage key."""
    return f"documents/tender/{tender_id}/version/{tender_version_id}/{document_id}/{safe_filename}"


def validate_file_signature(content: bytes, ext: str) -> None:
    """
    Validate file content magic bytes against the claimed extension.
    Rejects MIME spoofing, renamed executables, and zip bombs.
    """
    # 1. Reject obvious executable binaries
    for dangerous in DANGEROUS_SIGNATURES:
        if content.startswith(dangerous):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Executable binaries are strictly prohibited.",
            )

    # 2. Check for script/HTML injection in document/image files
    lowered_header = content[:512].lower()
    if b"<html" in lowered_header or b"<!doctype" in lowered_header or b"<script" in lowered_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security violation: HTML or script content detected in document file.",
        )

    # 3. Validate signature per extension
    if ext == ".pdf":
        if not content.startswith(SIGNATURE_PDF):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file signature: Content does not match PDF specification.",
            )
    elif ext in (".jpg", ".jpeg"):
        if not content.startswith(SIGNATURE_JPEG):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file signature: Content does not match JPEG specification.",
            )
    elif ext == ".png":
        if not content.startswith(SIGNATURE_PNG):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file signature: Content does not match PNG specification.",
            )
    elif ext == ".doc":
        if not content.startswith(SIGNATURE_OLE_DOC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file signature: Content does not match Microsoft Word DOC specification.",
            )
    elif ext in (".docx", ".xlsx"):
        if not content.startswith(SIGNATURE_ZIP):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file signature: Content does not match {ext.upper()} container specification.",
            )
        # Verify safe zip structure and Office Open XML manifest
        _validate_office_zip_container(content, ext)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension: '{ext}'.",
        )


def _validate_office_zip_container(content: bytes, ext: str) -> None:
    """Inspect internal structure of DOCX/XLSX zip container to prevent zip bombs, path traversal, and macros."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            namelist = zf.namelist()

            # Verify standard Open Packaging Convention manifest
            if "[Content_Types].xml" not in namelist:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid {ext.upper()} structure: Missing Open Packaging Convention manifest.",
                )

            # Prevent zip bombs: check decompressed size ratio and total count
            total_uncompressed_size = 0
            file_count = len(namelist)
            if file_count > 5000:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Archive safety violation: Excessive file count in document container.",
                )

            for info in zf.infolist():
                entry_name = info.filename
                # Path traversal check inside archive entries
                if ".." in entry_name or entry_name.startswith("/") or entry_name.startswith("\\"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Archive safety violation: Dangerous path traversal detected in archive entry.",
                    )

                # Macro detection: block VBA macros or script components inside Office documents
                entry_lower = entry_name.lower()
                if (
                    "vbaproject.bin" in entry_lower
                    or entry_lower.endswith(".vba")
                    or entry_lower.endswith(".bas")
                    or entry_lower.endswith(".cls")
                    or entry_lower.endswith(".vbe")
                    or "vba" in entry_lower.split("/")
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Security violation: Macro-bearing office documents are strictly prohibited.",
                    )

                total_uncompressed_size += info.file_size

            # Ratio check against compressed container size
            compressed_size = len(content)
            if compressed_size > 0:
                ratio = total_uncompressed_size / compressed_size
                if ratio > 50 and total_uncompressed_size > 100 * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Archive safety violation: Potential zip bomb detected (unreasonable expansion ratio).",
                    )
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrupted or invalid {ext.upper()} archive container.",
        )


async def validate_and_process_upload_stream(
    file: UploadFile,
    max_size_mb: int,
) -> Tuple[bytes, str, str, str, int, str]:
    """
    Stream and validate an uploaded file.
    Returns:
        (file_bytes, safe_filename, ext, verified_content_type, file_size, sha256_hash)
    """
    safe_filename, ext = sanitize_filename(file.filename)

    if ext not in ALLOWED_EXTENSIONS_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed types: {', '.join(ALLOWED_EXTENSIONS_MAP.keys())}",
        )

    verified_content_type = ALLOWED_EXTENSIONS_MAP[ext]

    # Stream chunks, compute SHA-256, enforce size limit
    max_bytes = max_size_mb * 1024 * 1024
    hasher = hashlib.sha256()
    buffer = io.BytesIO()
    total_size = 0
    chunk_size = 64 * 1024  # 64 KB chunks

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds the maximum permitted limit of {max_size_mb} MB.",
            )
        hasher.update(chunk)
        buffer.write(chunk)

    if total_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    file_bytes = buffer.getvalue()
    sha256_hash = hasher.hexdigest()

    # Validate file magic bytes / signature
    validate_file_signature(file_bytes, ext)

    return file_bytes, safe_filename, ext, verified_content_type, total_size, sha256_hash
