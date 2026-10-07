"""Bonus B2: stress-test projection alignment under point-cloud degradation.

Run from the repository root with:
    python -m src.exp_degradation --data-root data/kitti_mini --frames 000008 000011 000049

Uses fixed, per-frame seeds for random dropout and Gaussian XYZ noise. The
CSV records both alignment ratios and the number of labeled object points.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt

from src.exp_yaw_sweep import run_one
from starter.datasets import load_frame
from starter.perturb import gaussian_noise, random_dropout

FIELDNAMES = (
    "dataset", "frame", "perturbation", "level", "seed", "n_points", "inside_image",
    "object_points", "visible_object_points", "hits", "hit_ratio", "visible_hit_ratio",
    "visibility_ratio",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stress-test LiDAR-camera QA under point-cloud degradation")
    parser.add_argument("--data-root", default="data/kitti_mini", help="KITTI dataset directory")
    parser.add_argument("--frames", nargs="+", default=["000008", "000011", "000049"], help="KITTI frame IDs")
    parser.add_argument("--dropout-levels", nargs="+", type=float, default=[1.0, 0.9, 0.7, 0.5],
                        help="random point keep ratios; include 1.0 as the baseline")
    parser.add_argument("--noise-levels", nargs="+", type=float, default=[0.0, 0.02, 0.05, 0.1],
                        help="Gaussian XYZ noise sigma in meters; include 0.0 as the baseline")
    parser.add_argument("--seed", type=int, default=0, help="base seed, fixed across levels within each frame/type")
    parser.add_argument("--out", default="results/degradation_sweep.csv", help="output CSV path")
    parser.add_argument("--figure", default="results/figures/degradation_sweep.png", help="output plot path")
    args = parser.parse_args()

    rows = []
    for frame_index, frame_id in enumerate(args.frames):
        frame_data = load_frame(args.data_root, frame_id)
        for perturbation_index, (name, levels) in enumerate(
            (("random_dropout", args.dropout_levels), ("gaussian_noise", args.noise_levels))
        ):
            seed = args.seed + frame_index * 100 + perturbation_index
            for level in levels:
                changed = dict(frame_data)
                if name == "random_dropout":
                    changed["points"] = random_dropout(frame_data["points"], keep_ratio=level, seed=seed)
                else:
                    changed["points"] = gaussian_noise(frame_data["points"], sigma_xyz_m=level, seed=seed)
                overall = next(
                    (row for row in run_one(changed, frame_id, args.data_root, yaw_deg=0.0)
                     if row["group_by"] == "all"),
                    None,
                )
                if overall is None:
                    continue
                rows.append({
                    **{key: overall[key] for key in FIELDNAMES if key in overall},
                    "frame": frame_id,
                    "perturbation": name,
                    "level": level,
                    "seed": seed,
                })
                print(
                    f"frame={frame_id} {name}={level:g} points={overall['object_points']} "
                    f"hit_ratio={overall['hit_ratio']}"
                )

    if not rows:
        raise RuntimeError("No labeled object points found; check the dataset and selected frames")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    figure_path = Path(args.figure)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex="col")
    specifications = (
        ("random_dropout", "Random dropout", "Keep ratio", args.dropout_levels),
        ("gaussian_noise", "Gaussian XYZ noise", "Sigma (m)", args.noise_levels),
    )
    for column, (name, title, x_label, levels) in enumerate(specifications):
        subset = [row for row in rows if row["perturbation"] == name]
        for frame_id in args.frames:
            group = sorted((row for row in subset if row["frame"] == frame_id), key=lambda row: row["level"])
            x = [row["level"] for row in group]
            axes[0, column].plot(x, [100 * row["hit_ratio"] for row in group], marker="o", label=frame_id)
            axes[1, column].plot(x, [row["object_points"] for row in group], marker="o", label=frame_id)
        axes[0, column].set_title(title)
        axes[0, column].set_ylabel("Object points inside 2D box (%)")
        axes[1, column].set_ylabel("LiDAR points inside 3D boxes")
        axes[1, column].set_xlabel(x_label)
        for row_index in range(2):
            axes[row_index, column].set_xticks(levels)
            axes[row_index, column].grid(alpha=0.3)
            axes[row_index, column].legend(title="Frame")
    fig.suptitle("Projection QA under point-cloud degradation")
    fig.tight_layout()
    fig.savefig(figure_path, dpi=160)
    plt.close(fig)
    print(f"-> {output} ({len(rows)} rows)")
    print(f"-> {figure_path}")


if __name__ == "__main__":
    main()
