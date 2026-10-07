"""Bonus B5: run the same yaw-alignment experiment on KITTI and nuScenes.

nuScenes is loaded with ego-motion correction enabled by the default loader.
Only common object classes (Car and Pedestrian) are compared to avoid a class
mix difference between datasets.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.exp_yaw_sweep import run_one
from starter.datasets import load_frame

COMMON_CLASSES = ("Car", "Pedestrian")
FIELDNAMES = (
    "dataset", "frame", "yaw_deg", "ego_motion", "group_by", "group", "n_points", "inside_image",
    "object_points", "visible_object_points", "hits", "hit_ratio", "visible_hit_ratio", "visibility_ratio",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare yaw-drift sensitivity on KITTI and nuScenes")
    parser.add_argument("--kitti-root", default="data/kitti_mini", help="KITTI data directory")
    parser.add_argument("--kitti-frames", nargs="+", default=["000008", "000011", "000049"], help="KITTI frame IDs")
    parser.add_argument("--nuscenes-root", default="data/nuscenes_mini_subset", help="nuScenes data directory")
    parser.add_argument("--nuscenes-frames", nargs="+",
                        default=["scene-0103_010", "scene-0103_020", "scene-1094_010"],
                        help="nuScenes frame IDs; defaults cover day and night")
    parser.add_argument("--yaw-levels", nargs="+", type=float, default=[0, 0.5, 1, 2, 3],
                        help="yaw drift levels in degrees")
    parser.add_argument("--out", default="results/yaw_dataset_compare.csv", help="output CSV path")
    parser.add_argument("--figure", default="results/figures/yaw_dataset_compare.png", help="output plot path")
    args = parser.parse_args()

    rows = []
    for data_root, frames, is_nuscenes in (
        (args.kitti_root, args.kitti_frames, False),
        (args.nuscenes_root, args.nuscenes_frames, True),
    ):
        for frame_id in frames:
            frame_data = load_frame(data_root, frame_id)  # nuScenes ego-motion compensation stays enabled.
            for yaw_deg in args.yaw_levels:
                measurements = run_one(frame_data, frame_id, data_root, yaw_deg)
                common_rows = [
                    row for row in measurements
                    if row["group_by"] == "class" and row["group"] in COMMON_CLASSES
                ]
                for row in common_rows:
                    output_row = {**row, "ego_motion": "on" if is_nuscenes else "not_applicable"}
                    rows.append(output_row)
                    print(
                        f"{row['dataset']} frame={frame_id} class={row['group']} yaw={yaw_deg:g}deg "
                        f"visible_hit_ratio={row['visible_hit_ratio']}"
                    )

    if not rows:
        raise RuntimeError("No common Car/Pedestrian object points found in the selected frames")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    data = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for ax, class_name in zip(axes, COMMON_CLASSES):
        subset = data[data["group"] == class_name]
        grouped = subset.groupby(["dataset", "yaw_deg"], as_index=False).agg(
            hits=("hits", "sum"), visible_object_points=("visible_object_points", "sum")
        )
        grouped["ratio"] = grouped["hits"] / grouped["visible_object_points"].replace(0, np.nan)
        for dataset, curve in grouped.groupby("dataset", sort=True):
            curve = curve.sort_values("yaw_deg")
            ax.plot(curve["yaw_deg"], 100 * curve["ratio"], marker="o", label=dataset)
        ax.set_title(class_name)
        ax.set_xlabel("Yaw calibration drift (degrees)")
        ax.set_ylim(0, 105)
        ax.grid(alpha=0.3)
        ax.legend(title="Dataset")
    axes[0].set_ylabel("Visible object points inside 2D box (%)")
    fig.suptitle("Yaw sensitivity: KITTI vs nuScenes (ego-motion corrected)")
    fig.tight_layout()
    figure = Path(args.figure)
    figure.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure, dpi=160)
    plt.close(fig)
    print(f"-> {output} ({len(rows)} rows)")
    print(f"-> {figure}")


if __name__ == "__main__":
    main()
