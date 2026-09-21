"""Benchmark execution for the 20-document real dataset (A1-A6 and B1-B14)."""

import io
import os
import sys
import time
import uuid
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.pipeline.pdf import PDFDocumentParser
from app.pipeline.ocr.engine import OCREngine
from app.pipeline.schemas import NormalizedDocument

DOCS_DIR = r"d:\tender\backend\generated-tender-documents"

DOCUMENT_FILENAMES = [
    # Tender Notice & Requirements (A1 - A6)
    "A1_NIT_Tender_Notice.pdf",
    "A2_Eligibility_Criteria.pdf",
    "A3_Technical_Specification.pdf",
    "A4_Financial_Commercial_Conditions.pdf",
    "A5_Document_Checklist.pdf",
    "A6_Technical_Compliance_Form.pdf",
    # Bidder Evidence & Certificates (B1 - B14)
    "B1_Company_Registration.pdf",
    "B2_GST_Certificate.pdf",
    "B3_PAN_Document.pdf",
    "B4_CA_Turnover_Certificate.pdf",
    "B5_Work_Order_1.pdf",
    "B6_Completion_Certificate_1.pdf",
    "B7_Work_Order_2.pdf",
    "B8_Completion_Certificate_2.pdf",
    "B9_Work_Order_3.pdf",
    "B10_Completion_Certificate_3.pdf",
    "B11_ISO_9001_Certificate.pdf",
    "B12_Non_Blacklisting_Declaration.pdf",
    "B13_Technical_Compliance_Statement.pdf",
    "B14_Signed_Tender_Declaration.pdf",
]


def run_benchmark():
    print("=" * 80)
    print("STARTING 20-DOCUMENT REAL OCR & PIPELINE BENCHMARK")
    print("=" * 80)

    parser = PDFDocumentParser()
    total_pages = 0
    total_ocr_pages = 0
    total_bypassed_pages = 0
    total_characters = 0
    total_tables = 0
    doc_times: List[float] = []
    secondary_invocations = 0
    vision_fallback_invocations = 0
    ocr_failures = 0

    benchmark_start = time.time()

    for idx, fname in enumerate(DOCUMENT_FILENAMES):
        fpath = os.path.join(DOCS_DIR, fname)
        if not os.path.exists(fpath):
            print(f" [SKIP] {fname} not found at {fpath}")
            continue

        with open(fpath, "rb") as f:
            content = f.read()

        doc_id = uuid.uuid4()
        t0 = time.time()
        try:
            norm_doc = parser.parse(doc_id, content, fname)
            duration = time.time() - t0
            doc_times.append(duration)

            pages_count = norm_doc.page_count
            total_pages += pages_count
            bypassed = norm_doc.metadata.get("pages_digital_bypassed", 0)
            ocr_pgs = norm_doc.metadata.get("pages_ocr", 0)
            total_bypassed_pages += bypassed
            total_ocr_pages += ocr_pgs
            total_characters += norm_doc.total_characters
            total_tables += norm_doc.total_tables

            # Inspect block provenance
            for p in norm_doc.pages:
                for b in p.blocks:
                    if b.ocr_engine == "vision_fallback":
                        vision_fallback_invocations += 1
                    elif b.ocr_engine == "secondary_ocr":
                        secondary_invocations += 1
                    elif b.ocr_engine == "error":
                        ocr_failures += 1

            engine_used = norm_doc.metadata.get("ocr_engine", "unknown")
            print(
                f" [{idx+1:02d}/20] {fname[:35]:<35} | {duration*1000:6.1f}ms | "
                f"Pages: {pages_count} (Bypassed: {bypassed}, OCR: {ocr_pgs}) | "
                f"Engine: {engine_used} | Chars: {norm_doc.total_characters}"
            )
        except Exception as exc:
            ocr_failures += 1
            print(f" [{idx+1:02d}/20] {fname}: FAILED: {exc}")

    total_time = time.time() - benchmark_start
    avg_doc_time = (sum(doc_times) / len(doc_times)) if doc_times else 0.0
    avg_page_time = (total_time / total_pages * 1000) if total_pages else 0.0

    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total Documents Processed:      {len(doc_times)} / {len(DOCUMENT_FILENAMES)}")
    print(f"Total Pages Processed:          {total_pages}")
    print(f"Pages Bypassing OCR (FastPath): {total_bypassed_pages}")
    print(f"Pages Using OCR:                {total_ocr_pages}")
    print(f"Secondary OCR Invocations:      {secondary_invocations}")
    print(f"Vision Fallback Invocations:    {vision_fallback_invocations}")
    print(f"OCR Failures:                   {ocr_failures}")
    print(f"Total Tables Extracted:         {total_tables}")
    print(f"Total Characters Extracted:     {total_characters}")
    print(f"Average Page Processing Time:   {avg_page_time:.1f} ms")
    print(f"Average Document Time:          {avg_doc_time:.2f} s")
    print(f"Total 20-Doc Benchmark Time:    {total_time:.2f} s")
    print("=" * 80)

    return {
        "total_documents": len(doc_times),
        "total_pages": total_pages,
        "pages_bypassed": total_bypassed_pages,
        "pages_ocr": total_ocr_pages,
        "secondary_invocations": secondary_invocations,
        "vision_fallback_invocations": vision_fallback_invocations,
        "ocr_failures": ocr_failures,
        "total_characters": total_characters,
        "total_tables": total_tables,
        "avg_page_time_ms": avg_page_time,
        "avg_doc_time_s": avg_doc_time,
        "total_time_s": total_time,
    }


if __name__ == "__main__":
    run_benchmark()
