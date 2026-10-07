"""Create a side-by-side baseline/drifted overlay for a CP4 geometry failure."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from src.exp_yaw_sweep import CLASSES, points_in_box
from starter.datasets import load_frame
from starter.projection import (
    draw_box2d,
    overlay_points,
    perturb_extrinsic,
    project_velo_to_image,
    velo_to_cam,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reproducible yaw-drift failure comparison")
    parser.add_argument("--data-root", default="data/kitti_mini", help="KITTI dataset directory")
    parser.add_argument("--frame", default="000011", help="frame with narrow pedestrian objects")
    parser.add_argument("--yaw-deg", type=float, default=2.0, help="yaw drift to demonstrate, in degrees")
    parser.add_argument("--class-name", choices=CLASSES, default="Pedestrian", help="object class to highlight")
    parser.add_argument(
        "--out", default="results/figures/fail_01_yaw2_frame000011.png", help="output comparison image path"
    )
    args = parser.parse_args()

    frame_data = load_frame(args.data_root, args.frame)
    original_points = frame_data["points"]
    finite = np.isfinite(original_points).all(axis=1)
    points = original_points[finite]
    points_cam = velo_to_cam(points[:, :3], frame_data["calib"])
    base_uv, base_depth, base_mask = project_velo_to_image(points, frame_data["calib"], frame_data["image"].shape)

    drifted_calib = perturb_extrinsic(frame_data["calib"], yaw_deg=args.yaw_deg)
    drift_uv, drift_depth, drift_mask = project_velo_to_image(points, drifted_calib, frame_data["image"].shape)
    drift_uv_all = np.full((len(points), 2), np.nan, dtype=np.float64)
    drift_uv_all[drift_mask] = drift_uv
    base_uv_all = np.full((len(points), 2), np.nan, dtype=np.float64)
    base_uv_all[base_mask] = base_uv

    candidates = []
    for object_index, obj in enumerate(frame_data["labels"]):
        if obj.type != args.class_name:
            continue
        object_mask = points_in_box(points_cam, obj) & base_mask
        indices = np.flatnonzero(object_mask)
        if indices.size < 3:
            continue
        x1, y1, x2, y2 = obj.bbox

        def hit_count(uv: np.ndarray, visible: np.ndarray) -> int:
            u, v = uv[:, 0], uv[:, 1]
            return int((visible & (u >= x1) & (u <= x2) & (v >= y1) & (v <= y2)).sum())

        base_hits = hit_count(base_uv_all[indices], base_mask[indices])
        drift_hits = hit_count(drift_uv_all[indices], drift_mask[indices])
        candidates.append((drift_hits / len(indices), object_index, obj, len(indices), base_hits, drift_hits))

    if not candidates:
        raise RuntimeError(f"No visible {args.class_name} points found in frame {args.frame}")
    _, object_index, target, n_object_points, base_hits, drift_hits = min(candidates, key=lambda item: item[0])
    base_ratio = base_hits / n_object_points
    drift_ratio = drift_hits / n_object_points

    base_image = overlay_points(frame_data["image"], base_uv, base_depth)
    drift_image = overlay_points(frame_data["image"], drift_uv, drift_depth)
    for obj in frame_data["labels"]:
        base_image = draw_box2d(base_image, obj.bbox, label=obj.type)
        drift_image = draw_box2d(drift_image, obj.bbox, label=obj.type)
    base_image = draw_box2d(base_image, target.bbox, color=(0, 0, 255), label=f"worst {target.type} #{object_index}")
    drift_image = draw_box2d(drift_image, target.bbox, color=(0, 0, 255), label=f"worst {target.type} #{object_index}")

    comparison = np.hstack((base_image, drift_image))
    cv2.putText(comparison, "Yaw 0 deg", (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    right_x = frame_data["image"].shape[1] + 15
    cv2.putText(
        comparison,
        f"Yaw {args.yaw_deg:g} deg | target hit ratio {drift_ratio:.1%}",
        (right_x, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
    )

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), comparison):
        raise OSError(f"Could not write failure image to {output}")
    print(
        f"target={target.type} object_index={object_index} points={n_object_points} "
        f"baseline={base_hits}/{n_object_points} ({base_ratio:.1%}) "
        f"yaw_{args.yaw_deg:g}={drift_hits}/{n_object_points} ({drift_ratio:.1%}) "
        f"-> {output}"
    )


if __name__ == "__main__":
    main()
