# Báo cáo Day 6 Lab: Độ nhạy phép chiếu LiDAR-camera với lệch yaw

> CP2–CP4 đã chạy. Bảng dưới lấy từ CSV và ảnh đã tạo. Bonus B2–B5 đã có script; bổ sung kết quả bonus sau khi chạy mục 5.

- **Họ tên:** Vũ Hải Minh
- **MSSV:** 2A202602452
- **Lớp:** AI20K-T4
- **Link repo:** https://github.com/dtc-z/VuHaiMinh-2A202602452-Track4-Day21
- **Topic:** A — Kiểm tra calibration LiDAR-camera
- **Dataset:** `data/kitti_mini` (thử phép chiếu số với `data/synthetic`)
- **Các frame đã dùng:** 000004, 000008, 000011, 000019, 000049

> Hãy viết ngắn: mỗi mục từ 3 đến 8 dòng, ưu tiên số liệu và hình ảnh.

## 1. Claim

Giả thuyết: trên KITTI, lệch yaw 1° làm `visible_hit_ratio` giảm hơn 20 điểm phần trăm ở frame 000011, trong khi mức giảm ở frame đông xe 000008 dưới 5 điểm phần trăm. `visible_hit_ratio` là tỷ lệ điểm thuộc 3D box, còn chiếu được vào ảnh sau perturb, nằm trong 2D box; `visibility_ratio` bổ sung tỷ lệ điểm còn trong ảnh.

## 2. Evidence

Kết quả trong `results/yaw_perturb_sweep.csv` (metric `visible_hit_ratio`: tỷ lệ điểm thuộc 3D box còn chiếu trong ảnh và rơi trong 2D box):

| Frame | yaw 0° | yaw 1° | yaw 2° |
|---|---:|---:|---:|
| 000008, đông xe | 99.63% | 98.75% | 94.88% |
| 000011, nhiều người đi bộ | 99.45% | 77.44% | 45.44% |
| 000049, nhiều vật bị che | 99.25% | 93.54% | 84.73% |

Ở frame 000011, yaw 1° làm tỷ lệ giảm 22.01 điểm phần trăm; frame 000008 giảm 0.88 điểm. CSV ghi 122,555 điểm đầu vào mỗi frame, khác số mốc trong GUIDE; dùng số đo thực tế này khi giải thích kết quả. `yaw_sweep.png` cho xu hướng theo frame, còn `yaw_breakdown.png` tách theo class và khoảng cách.

![overlay frame 000011](../results/figures/overlay_000011_r0.0_p0.0_y0.0_t0.0_0.0_0.0.png)
![yaw sweep](../results/figures/yaw_sweep.png)
![class and distance breakdown](../results/figures/yaw_breakdown.png)

### Bonus [B2] — Suy giảm point cloud

`src.exp_degradation` thử random dropout ở keep ratio 1.0/0.9/0.7/0.5 và Gaussian XYZ noise ở σ=0/0.02/0.05/0.1 m với seed cố định. Đọc `hit_ratio` cùng số điểm trong 3D box để so sánh độ khớp và mật độ. Bổ sung số liệu, biểu đồ và nhận xét sau khi chạy.

![degradation sweep](../results/figures/degradation_sweep.png)

### Bonus [B3] — Latency

`src.bench_projection_latency` đo cùng pipeline QA trên ba frame; mỗi frame bỏ lượt warm-up, đo 20 lượt và lưu từng lần vào CSV. Bổ sung p50/p95 cùng CPU, RAM và GPU (nếu có) sau khi chạy.

Kết quả từng lượt: `results/projection_latency.csv`.

### Bonus [B5] — KITTI và nuScenes

`src.exp_yaw_dataset_compare` chạy cùng yaw sweep cho Car/Pedestrian ở cả hai dataset; nuScenes giữ bật bù ego-motion. Bổ sung bảng/biểu đồ và giải thích khác biệt về số beam, tiêu cự, kích thước ảnh và timestamp sau khi chạy.

![KITTI vs nuScenes](../results/figures/yaw_dataset_compare.png)

## 3. Failure case

Frame 000011, yaw extrinsic bị perturb 2°: ảnh `fail_01_yaw2_frame000011.png` cho thấy pedestrian được khoanh mất toàn bộ điểm trong 2D box (tỷ lệ của vật thể là 0.0%); `visible_hit_ratio` gộp các vật thể trong CSV giảm từ 99.45% ở 0° xuống 45.44% ở 2°.

Lớp debug: **Geometry** — extrinsic LiDAR-camera bị lệch yaw. Điểm của vật thể hẹp dịch khỏi label 2D dù frame và point cloud không đổi; failure tái lập bằng script CP4.

![failure: yaw drift](../results/figures/fail_01_yaw2_frame000011.png)

## 4. Khuyến nghị nếu triển khai thật

Với xe giao hàng tự hành trong đô thị, tính chỉ số căn chỉnh riêng cho pedestrian và car khi xe dừng hoặc ở tốc độ thấp để không tăng tải xử lý mỗi frame. Dùng 90% làm ngưỡng cảnh báo ban đầu nếu `visible_hit_ratio` pedestrian thấp liên tục 5 phút; hiệu chỉnh ngưỡng bằng dữ liệu ngày/đêm và tình huống che khuất trước khi đưa vào vận hành. Ghi log thêm yaw ước lượng, thời gian, class, khoảng cách và nhiệt độ/ngày bảo dưỡng giá đỡ cảm biến để khoanh vùng nguyên nhân.

## 5. Cách chạy lại

Chạy từ gốc repo sau khi kích hoạt môi trường đã cài ở CP0:

```bash
python -m src.test_projection
python -m starter.projection --data-root data/kitti_mini --frame 000019
python -m starter.projection --data-root data/kitti_mini --frame 000011
python -m starter.projection --data-root data/kitti_mini --frame 000004
python -m src.exp_yaw_sweep --data-root data/kitti_mini --frames 000008 000011 000049
python -m src.plot_yaw_sweep
python -m src.exp_yaw_sweep --data-root data/kitti_mini --frames 000008 000011 000049 --out results/check_rerun.csv
python -c "import filecmp; print('GIỐNG HỆT' if filecmp.cmp('results/yaw_perturb_sweep.csv', 'results/check_rerun.csv', shallow=False) else 'KHÁC NHAU')"
python -m src.failure_yaw_demo --data-root data/kitti_mini --frame 000011 --yaw-deg 2 --out results/figures/fail_01_yaw2_frame000011.png
python -m src.exp_degradation --data-root data/kitti_mini --frames 000008 000011 000049
python -m src.bench_projection_latency --data-root data/kitti_mini --frames 000008 000011 000049 --repeats 20
python -m src.exp_yaw_dataset_compare --kitti-frames 000008 000011 000049 --nuscenes-frames scene-0103_010 scene-0103_020 scene-1094_010
python -m src.exp_yaw_sweep --help
python -m src.exp_yaw_sweep
python tools/check_submission.py
```

### Bonus [B4] — CLI có thể dùng lại

`src.exp_yaw_sweep` có `argparse`, trợ giúp cho mọi tham số và mặc định hợp lý. Xem `--help`, rồi chạy không tham số để tái tạo sweep KITTI mặc định ở mục 2.

## 6. Khai báo sử dụng AI

| Công cụ | Dùng cho việc gì | Cách kiểm chứng |
|---|---|---|
| ChatGPT | Cài đặt phép chiếu CP2, viết sweep/plot CP3, script failure CP4, script bonus B2–B5 và biên tập report | CP3 đã đối chiếu với CSV/ảnh hiện có. Trước khi nộp, chạy self-check CP2, xác nhận sweep tái lập, chạy bonus và đối chiếu CSV/biểu đồ mới. |
