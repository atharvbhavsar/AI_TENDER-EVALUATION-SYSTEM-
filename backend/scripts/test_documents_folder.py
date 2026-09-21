"""Test and analyze all documents in d:\\tender\\backend\\documents."""

import os
import sys
import time
import uuid
import json
import pymupdf as fitz
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.pipeline.pdf import PDFDocumentParser
from app.pipeline.ocr.engine import OCREngine
from app.pipeline.ocr.preprocessing import ImagePreprocessor, ImageQualityProfile
from app.pipeline.ocr.quality import OCRQualityAssessment

DOCS_DIR = r"d:\tender\backend\documents"


def analyze_all_documents():
    print("=" * 90)
    print("DEEP ANALYSIS & BENCHMARK OF DOCUMENTS IN: " + DOCS_DIR)
    print("=" * 90)

    if not os.path.exists(DOCS_DIR):
        print(f"Error: Directory {DOCS_DIR} not found.")
        return

    files = sorted([f for f in os.listdir(DOCS_DIR) if f.lower().endswith(".pdf")])
    print(f"Found {len(files)} PDF documents to analyze.\n")

    parser = PDFDocumentParser()
    results = []
    
    total_start = time.time()

    for idx, fname in enumerate(files, 1):
        fpath = os.path.join(DOCS_DIR, fname)
        file_size_kb = os.path.getsize(fpath) / 1024.0

        print(f"\n[{idx:02d}/{len(files)}] Document: {fname} ({file_size_kb:.1f} KB)")
        print("-" * 75)

        with open(fpath, "rb") as f:
            content = f.read()

        # Step 1: Physical inspection with PyMuPDF
        doc_fitz = fitz.open(stream=content, filetype="pdf")
        page_count = len(doc_fitz)
        
        digital_pages = []
        scanned_pages = []

        for pno in range(page_count):
            p = doc_fitz[pno]
            raw_text = p.get_text()
            if parser._is_usable_digital_text(raw_text):
                digital_pages.append(pno + 1)
            else:
                scanned_pages.append(pno + 1)

        print(f"  Pages: {page_count} | Digital Native: {digital_pages} | Scanned/Raster: {scanned_pages}")

        # Step 2: Full pipeline parse
        doc_id = uuid.uuid4()
        t0 = time.time()
        try:
            norm_doc = parser.parse(doc_id, content, fname)
            duration = time.time() - t0
            
            total_chars = norm_doc.total_characters
            total_tables = norm_doc.total_tables
            engine_used = norm_doc.metadata.get("ocr_engine", "unknown")
            bypassed = norm_doc.metadata.get("pages_digital_bypassed", 0)
            ocr_pages = norm_doc.metadata.get("pages_ocr", 0)

            # Collect block details
            confidences = []
            all_text_snippets = []
            all_prep_transforms = set()
            engine_counts = {}
            blocks_for_quality = []

            for page in norm_doc.pages:
                for blk in page.blocks:
                    if blk.confidence is not None:
                        confidences.append(blk.confidence)
                    if blk.text:
                        all_text_snippets.append(blk.text)
                    eng = blk.ocr_engine or "unknown"
                    engine_counts[eng] = engine_counts.get(eng, 0) + 1
                    if blk.preprocessing:
                        for tr in blk.preprocessing:
                            all_prep_transforms.add(tr)
                    blocks_for_quality.append({
                        "text": blk.text or "",
                        "confidence": blk.confidence if blk.confidence is not None else 1.0,
                    })

            full_text = " ".join(all_text_snippets)
            mean_conf = (sum(confidences) / len(confidences)) if confidences else 1.0

            # Quality evaluation
            q_eval = OCRQualityAssessment.calculate_quality_score(blocks_for_quality)
            quality_status = q_eval.status
            critical_fields = q_eval.critical_fields_found

            print(f"  Duration:      {duration:.3f} s ({duration*1000/page_count:.1f} ms/page)")
            print(f"  Engine(s):     {engine_counts}")
            print(f"  Characters:    {total_chars}")
            print(f"  Tables:        {total_tables}")
            print(f"  Mean Conf:     {mean_conf:.3f} | Quality Status: {quality_status} (Score: {q_eval.overall_score:.2f})")
            if all_prep_transforms:
                print(f"  Preprocessing: {list(all_prep_transforms)}")
            if critical_fields:
                print(f"  Key Entities:  {critical_fields[:5]}")

            # Preview first 140 chars
            preview = full_text[:140].replace("\n", " ")
            print(f"  Snippet:       \"{preview}...\"")

            results.append({
                "filename": fname,
                "size_kb": file_size_kb,
                "pages": page_count,
                "digital_pages": len(digital_pages),
                "scanned_pages": len(scanned_pages),
                "duration_s": duration,
                "characters": total_chars,
                "tables": total_tables,
                "mean_conf": mean_conf,
                "quality_status": quality_status,
                "overall_score": q_eval.overall_score,
                "engines": engine_counts,
                "critical_fields": critical_fields,
                "preprocessing": list(all_prep_transforms),
                "status": "PASS",
            })

        except Exception as exc:
            duration = time.time() - t0
            print(f"  ERROR:         {exc}")
            import traceback
            traceback.print_exc()
            results.append({
                "filename": fname,
                "size_kb": file_size_kb,
                "pages": page_count,
                "duration_s": duration,
                "status": "FAIL",
                "error": str(exc),
            })

    total_duration = time.time() - total_start
    
    print("\n" + "=" * 90)
    print("ALL 20 DOCUMENTS PROCESSED")
    print("=" * 90)
    print(f"Total files:    {len(results)}")
    print(f"Total time:     {total_duration:.2f} s")
    print(f"Success count:  {sum(1 for r in results if r.get('status') == 'PASS')}")
    print(f"Failure count:  {sum(1 for r in results if r.get('status') == 'FAIL')}")

    out_json = os.path.join(os.path.dirname(__file__), "documents_test_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results JSON to: {out_json}")


if __name__ == "__main__":
    analyze_all_documents()
