"""Plot frame, class, and range trends from the CP3 yaw-sweep CSV."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot CP3 yaw-sweep results")
    parser.add_argument("--csv", default="results/yaw_perturb_sweep.csv", help="input sweep CSV")
    parser.add_argument("--out-dir", default="results/figures", help="directory for plots")
    parser.add_argument(
        "--metric", choices=("hit_ratio", "visible_hit_ratio"), default="hit_ratio",
        help="metric to plot; hit_ratio counts points outside the shifted image as misses",
    )
    args = parser.parse_args()

    data = pd.read_csv(args.csv, dtype={"frame": str, "group": str})
    if args.metric not in data.columns:
        raise ValueError(f"CSV is missing metric column {args.metric!r}")
    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    overall = data[data["group_by"] == "all"].dropna(subset=[args.metric])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for frame_id, group in overall.groupby("frame", sort=True):
        group = group.sort_values("yaw_deg")
        ax.plot(group["yaw_deg"], 100 * group[args.metric], marker="o", label=f"frame {frame_id}")
    ax.set_xlabel("Yaw calibration drift (degrees)")
    ax.set_ylabel("Object points inside labeled 2D box (%)")
    ax.set_ylim(0, 105)
    ax.set_title("LiDAR-camera alignment by frame")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    frame_plot = output_dir / "yaw_sweep.png"
    fig.savefig(frame_plot, dpi=160)
    plt.close(fig)
    print(f"-> {frame_plot}")

    breakdown = data[data["group_by"].isin(["class", "distance"])].dropna(subset=[args.metric])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, group_by, title in zip(axes, ("class", "distance"), ("By object class", "By distance")):
        subset = breakdown[breakdown["group_by"] == group_by]
        # Aggregate point counts across frames before taking the ratio.
        grouped = subset.groupby(["group", "yaw_deg"], as_index=False).agg(
            hits=("hits", "sum"),
            object_points=("object_points", "sum"),
            visible_object_points=("visible_object_points", "sum"),
        )
        denominator = "object_points" if args.metric == "hit_ratio" else "visible_object_points"
        grouped["ratio"] = grouped["hits"] / grouped[denominator].replace(0, float("nan"))
        for label, series in grouped.groupby("group", sort=True):
            series = series.sort_values("yaw_deg")
            ax.plot(series["yaw_deg"], 100 * series["ratio"], marker="o", label=label)
        ax.set_title(title)
        ax.set_xlabel("Yaw calibration drift (degrees)")
        ax.set_ylim(0, 105)
        ax.grid(alpha=0.3)
        ax.legend(title=group_by.replace("_", " "))
    axes[0].set_ylabel("Object points inside labeled 2D box (%)")
    fig.suptitle("Yaw sensitivity by class and range")
    fig.tight_layout()
    breakdown_plot = output_dir / "yaw_breakdown.png"
    fig.savefig(breakdown_plot, dpi=160)
    plt.close(fig)
    print(f"-> {breakdown_plot}")


if __name__ == "__main__":
    main()
