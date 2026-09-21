"""Benchmark sequential vs worker-based parallel document processing on real 20 documents."""

import io
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import get_settings
from app.pipeline.router import parse_document

DOCS_DIR = r"d:\tender\backend\generated-tender-documents"

TENDER_DOCS = [
    "A1_NIT_Tender_Notice.pdf",
    "A2_Eligibility_Criteria.pdf",
    "A3_Technical_Specification.pdf",
    "A4_Financial_Commercial_Conditions.pdf",
    "A5_Document_Checklist.pdf",
    "A6_Technical_Compliance_Form.pdf",
]

BIDDER_DOCS = [
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

ALL_20_DOCS = TENDER_DOCS + BIDDER_DOCS


def load_all_documents() -> List[Tuple[str, bytes]]:
    docs_data = []
    for fname in ALL_20_DOCS:
        fpath = os.path.join(DOCS_DIR, fname)
        with open(fpath, "rb") as f:
            docs_data.append((fname, f.read()))
    return docs_data


def run_sequential_benchmark(docs_data: List[Tuple[str, bytes]]) -> Tuple[float, List[dict]]:
    print("\n" + "=" * 70)
    print("RUNNING SEQUENTIAL PROCESSING BENCHMARK (1 worker / sequential)")
    print("=" * 70)
    metrics = []
    t_start = time.time()

    for fname, data in docs_data:
        t0 = time.time()
        norm = parse_document(
            document_id=uuid.uuid4(),
            content=data,
            filename=fname,
            file_extension=".pdf",
        )
        duration = time.time() - t0
        metrics.append({
            "filename": fname,
            "duration": duration,
            "pages": norm.page_count,
            "characters": norm.total_characters,
        })
        print(f"  [Sequential] {fname:38s}: {norm.page_count}p, {norm.total_characters:5d} chars, {duration:.2f}s")

    total_time = time.time() - t_start
    print(f"\nSequential Total Time: {total_time:.2f}s (Average: {total_time/len(docs_data):.2f}s/doc)")
    return total_time, metrics


def run_parallel_worker_benchmark(
    docs_data: List[Tuple[str, bytes]], concurrency: int = 3
) -> Tuple[float, List[dict]]:
    print("\n" + "=" * 70)
    print(f"RUNNING PARALLEL WORKER BENCHMARK (concurrency={concurrency} workers)")
    print("=" * 70)
    metrics = []
    t_start = time.time()

    def worker_process_task(item: Tuple[str, bytes, int]) -> dict:
        fname, data, worker_id = item
        t0 = time.time()
        norm = parse_document(
            document_id=uuid.uuid4(),
            content=data,
            filename=fname,
            file_extension=".pdf",
        )
        duration = time.time() - t0
        res = {
            "filename": fname,
            "worker_id": f"worker-{worker_id:02d}",
            "start_time": t0,
            "end_time": time.time(),
            "duration": duration,
            "pages": norm.page_count,
            "characters": norm.total_characters,
        }
        print(f"  [{res['worker_id']}] {fname:38s}: {norm.page_count}p, {norm.total_characters:5d} chars, {duration:.2f}s")
        return res

    tasks = [(fname, data, (i % concurrency) + 1) for i, (fname, data) in enumerate(docs_data)]

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        metrics = list(pool.map(worker_process_task, tasks))

    total_time = time.time() - t_start
    print(f"\nWorker Total Time: {total_time:.2f}s (Average: {total_time/len(docs_data):.2f}s/doc)")
    return total_time, metrics


def main():
    docs_data = load_all_documents()
    print(f"Loaded {len(docs_data)} real procurement documents from {DOCS_DIR}")

    # 1. Warm-up
    parse_document(uuid.uuid4(), docs_data[0][1], docs_data[0][0], ".pdf")

    # 2. Sequential Run
    seq_time, seq_metrics = run_sequential_benchmark(docs_data)

    # 3. Parallel Worker Run (Concurrency = 3)
    worker_time, worker_metrics = run_parallel_worker_benchmark(docs_data, concurrency=3)

    speedup = seq_time / worker_time if worker_time > 0 else 1.0

    print("\n" + "=" * 70)
    print("PERFORMANCE COMPARISON SUMMARY")
    print("=" * 70)
    print(f"Number of Documents:    {len(docs_data)}")
    print(f"Worker Concurrency:     3")
    print(f"Sequential Processing:  {seq_time:.2f} seconds ({seq_time/60:.2f} minutes)")
    print(f"Worker Processing:      {worker_time:.2f} seconds ({worker_time/60:.2f} minutes)")
    print(f"Speedup Ratio:          {speedup:.2f}x faster throughput")
    print(f"Throughput Improvement: {(1 - worker_time/seq_time)*100:.1f}% reduction in processing time")
    print("=" * 70)


if __name__ == "__main__":
    main()
