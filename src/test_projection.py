"""Numeric self-check for the two CP2 projection functions.

Run from the repository root with ``python -m src.test_projection``.
"""
import numpy as np

from starter.datasets import load_frame
from starter.projection import cam_to_image, velo_to_cam


def main() -> None:
    np.set_printoptions(suppress=True, precision=2)
    frame = load_frame("data/synthetic", "000000")
    calib, image_shape = frame["calib"], frame["image"].shape
    points = np.array(
        [
            [10.0, 0.0, 0.0],
            [np.nan, 0.0, 0.0],
            [-10.0, 0.0, 0.0],
            [10.0, 50.0, 0.0],
        ]
    )

    points_cam = velo_to_cam(points, calib)
    uv, depth, mask = cam_to_image(points_cam, calib.P2, image_shape)
    print("camera frame:\n", np.round(points_cam, 2))
    print("uv:", np.round(uv, 1), " depth:", np.round(depth, 2), " mask:", mask)

    assert points_cam.shape == (4, 3), f"velo_to_cam returned {points_cam.shape}, expected (4, 3)"
    assert abs(points_cam[0, 2] - 9.73) < 0.01, f"unexpected z_cam: {points_cam[0, 2]}"
    assert mask.tolist() == [True, False, False, False], f"unexpected mask: {mask}"
    assert uv.shape == (1, 2) and depth.shape == (1,), "unexpected uv/depth shape"
    assert np.allclose(uv[0], [614, 175], atol=1), f"unexpected pixel: {uv[0]}"
    print("✅ CP2 self-test passed")


if __name__ == "__main__":
    main()
