"""Bonus B3: measure repeatable CPU latency for the Topic A projection QA pipeline.

The first run per frame is recorded as warm-up and excluded from p50/p95.
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import time
from pathlib import Path

import numpy as np

from src.exp_yaw_sweep import run_one
from starter.datasets import load_frame

FIELDNAMES = ("dataset", "frame", "run_index", "warmup", "latency_ms", "n_points", "cpu_name", "logical_cpus")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the LiDAR-camera projection QA pipeline")
    parser.add_argument("--data-root", default="data/kitti_mini", help="KITTI dataset directory")
    parser.add_argument("--frames", nargs="+", default=["000008", "000011", "000049"], help="KITTI frame IDs")
    parser.add_argument("--repeats", type=int, default=20, help="measured runs per frame, minimum 20")
    parser.add_argument("--hardware", default="", help="CPU model override for the CSV")
    parser.add_argument("--out", default="results/projection_latency.csv", help="output CSV path")
    args = parser.parse_args()
    if args.repeats < 20:
        parser.error("--repeats must be at least 20 per GUIDE.md")

    cpu_name = args.hardware.strip() or platform.processor() or platform.machine() or "unknown"
    logical_cpus = os.cpu_count() or 0
    rows = []
    for frame_id in args.frames:
        frame_data = load_frame(args.data_root, frame_id)  # File I/O is outside the timed section.
        timings = []
        for run_index in range(args.repeats + 1):
            start = time.perf_counter()
            measured = run_one(frame_data, frame_id, args.data_root, yaw_deg=0.0)
            elapsed_ms = (time.perf_counter() - start) * 1000
            overall = next((row for row in measured if row["group_by"] == "all"), None)
            if overall is None:
                raise RuntimeError(f"No labeled object points found in frame {frame_id}")
            is_warmup = run_index == 0
            rows.append({
                "dataset": overall["dataset"],
                "frame": frame_id,
                "run_index": run_index,
                "warmup": is_warmup,
                "latency_ms": round(elapsed_ms, 4),
                "n_points": overall["n_points"],
                "cpu_name": cpu_name,
                "logical_cpus": logical_cpus,
            })
            if not is_warmup:
                timings.append(elapsed_ms)
        p50, p95 = np.percentile(timings, [50, 95])
        print(f"frame={frame_id} p50={p50:.2f} ms p95={p95:.2f} ms ({args.repeats} measured runs)")

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"-> {output} ({len(rows)} rows; warm-up rows are marked in the CSV)")


if __name__ == "__main__":
    main()
