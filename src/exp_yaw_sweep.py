"""Topic A: measure how yaw calibration drift changes LiDAR-to-box alignment.

Run from the repository root, for example:
    python -m src.exp_yaw_sweep --data-root data/kitti_mini --frames 000008 000011 000049

The fixed-denominator ``hit_ratio`` counts every object point visible with the
original calibration, so points pushed outside the image by the drift count as
misses. ``visible_hit_ratio`` matches the GUIDE sample metric and is included
for direct comparison. Class and distance groups extend the sample experiment.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

from starter.datasets import load_frame
from starter.projection import perturb_extrinsic, project_velo_to_image, velo_to_cam

CLASSES = ("Car", "Van", "Pedestrian", "Cyclist")
DISTANCE_BINS = (("0-15m", 0.0, 15.0), ("15-30m", 15.0, 30.0), ("30m+", 30.0, float("inf")))
FIELDNAMES = (
    "dataset", "frame", "yaw_deg", "group_by", "group", "n_points", "inside_image",
    "object_points", "visible_object_points", "hits", "hit_ratio", "visible_hit_ratio",
    "visibility_ratio",
)


def points_in_box(points_cam: np.ndarray, obj) -> np.ndarray:
    """Return a mask for points inside one KITTI 3D box in camera coordinates."""
    h, w, length = obj.dimensions
    c, s = np.cos(obj.rotation_y), np.sin(obj.rotation_y)
    rotation = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    local = (points_cam - obj.location) @ rotation
    return (
        (np.abs(local[:, 0]) <= length / 2)
        & (local[:, 1] <= 0)
        & (local[:, 1] >= -h)
        & (np.abs(local[:, 2]) <= w / 2)
    )


def _distance_bin(distance_m: float) -> str:
    for name, lower, upper in DISTANCE_BINS:
        if lower <= distance_m < upper:
            return name
    return DISTANCE_BINS[-1][0]


def run_one(frame_data: dict, frame_id: str, data_root: str, yaw_deg: float) -> list[dict]:
    """Measure total, per-class, and per-distance alignment for one frame/yaw."""
    points = frame_data["points"]
    finite = np.isfinite(points).all(axis=1)
    points = points[finite]
    cam_true = velo_to_cam(points[:, :3], frame_data["calib"])
    base_uv, _, base_mask = project_velo_to_image(points, frame_data["calib"], frame_data["image"].shape)

    shifted_calib = perturb_extrinsic(frame_data["calib"], yaw_deg=yaw_deg)
    shifted_uv, _, shifted_mask = project_velo_to_image(points, shifted_calib, frame_data["image"].shape)
    shifted_uv_all = np.full((len(points), 2), np.nan, dtype=np.float64)
    shifted_uv_all[shifted_mask] = shifted_uv

    # Each group stores counts, not ratios, so aggregated ratios are point-weighted.
    groups: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"object_points": 0, "visible_object_points": 0, "hits": 0}
    )
    for obj in frame_data["labels"]:
        if obj.type not in CLASSES:
            continue
        object_mask = points_in_box(cam_true, obj) & base_mask
        object_indices = np.flatnonzero(object_mask)
        if object_indices.size == 0:
            continue

        object_visible = shifted_mask[object_indices]
        u, v = shifted_uv_all[object_indices, 0], shifted_uv_all[object_indices, 1]
        x1, y1, x2, y2 = obj.bbox
        hits = object_visible & (u >= x1) & (u <= x2) & (v >= y1) & (v <= y2)
        distance_m = float(np.hypot(obj.location[0], obj.location[2]))
        keys = (("class", obj.type), ("distance", _distance_bin(distance_m)))
        for key in (("all", "all"), *keys):
            counts = groups[key]
            counts["object_points"] += int(object_indices.size)
            counts["visible_object_points"] += int(object_visible.sum())
            counts["hits"] += int(hits.sum())

    rows = []
    n_points = len(points)
    inside_image = int(shifted_mask.sum())
    for (group_by, group), counts in groups.items():
        object_points = counts["object_points"]
        visible_points = counts["visible_object_points"]
        hits = counts["hits"]
        rows.append(
            {
                "dataset": Path(data_root).name,
                "frame": frame_id,
                "yaw_deg": yaw_deg,
                "group_by": group_by,
                "group": group,
                "n_points": n_points,
                "inside_image": inside_image,
                "object_points": object_points,
                "visible_object_points": visible_points,
                "hits": hits,
                "hit_ratio": round(hits / object_points, 4) if object_points else "",
                "visible_hit_ratio": round(hits / visible_points, 4) if visible_points else "",
                "visibility_ratio": round(visible_points / object_points, 4) if object_points else "",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep LiDAR-camera yaw drift and measure 2D-box alignment")
    parser.add_argument("--data-root", default="data/kitti_mini", help="KITTI dataset directory")
    parser.add_argument("--frames", nargs="+", default=["000008", "000011", "000049"], help="KITTI frame IDs")
    parser.add_argument("--yaw-levels", nargs="+", type=float, default=[0, 0.5, 1, 2, 3], help="yaw drift levels in degrees")
    parser.add_argument("--out", default="results/yaw_perturb_sweep.csv", help="output CSV path")
    args = parser.parse_args()

    rows = []
    for frame_id in args.frames:
        frame_data = load_frame(args.data_root, frame_id)
        for yaw_deg in args.yaw_levels:
            frame_rows = run_one(frame_data, frame_id, args.data_root, yaw_deg)
            rows.extend(frame_rows)
            overall = next((row for row in frame_rows if row["group_by"] == "all"), None)
            print(
                f"frame={frame_id} yaw={yaw_deg:g}deg "
                f"hit_ratio={overall['hit_ratio'] if overall else 'n/a'} "
                f"visible_hit_ratio={overall['visible_hit_ratio'] if overall else 'n/a'}"
            )

    if not rows:
        raise RuntimeError("No labeled object points were found; check the dataset and selected frames")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"-> {output} ({len(rows)} measurement rows)")


if __name__ == "__main__":
    main()
