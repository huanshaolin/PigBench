# Setup môi trường PigBench trên Ubuntu 24 Server

## Yêu cầu hệ thống

| Thành phần | Version |
|-----------|---------|
| Ubuntu | 24.04 |
| CUDA | 11.8 |
| GCC | 11.x |
| Python | 3.10 |
| PyTorch | 2.0.0 |
| torchvision | 0.15.1 |
| mmdet | 3.3.0 |
| mmcv | 2.0.0 |
| numpy | 1.26.4 |

---

## Bước 1 — Kiểm tra GPU

```bash
nvidia-smi
```

Nếu chưa có driver NVIDIA:

```bash
sudo apt update
sudo ubuntu-drivers autoinstall
sudo reboot
```

---

## Bước 2 — Cài CUDA 11.8

Ubuntu 24 không cài được `cuda-toolkit-11-8` trọn gói do thiếu `libtinfo5`.
Dùng **runfile** để tránh lỗi apt dependencies:

```bash
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run

# Cài toolkit (bỏ --driver vì driver đã có sẵn)
sudo sh cuda_11.8.0_520.61.05_linux.run \
    --toolkit \
    --silent \
    --override \
    --no-opengl-libs

# Thêm vào PATH
echo 'export PATH=/usr/local/cuda-11.8/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-11.8/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

# Kiểm tra
nvcc --version
```

---

## Bước 3 — Cài GCC 11

> GCC 11 bắt buộc để compile CUDA extensions (deformable attention của MOTRv2/MOTIP).

Nếu apt bị lock bởi `unattended-upgrades`:

```bash
sudo systemctl stop unattended-upgrades
sudo kill -9 $(pgrep unattended-upgr)
sudo rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/cache/apt/archives/lock
sudo dpkg --configure -a
```

Sau đó cài GCC:

```bash
sudo apt install -y gcc-11 g++-11

sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-11 100
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-11 100

gcc --version   # phải ra 11.x
```

---

## Bước 4 — Cài Miniconda

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3
echo 'export PATH=$HOME/miniconda3/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
conda init bash && source ~/.bashrc
```

---

## Bước 5 — Tạo môi trường conda

```bash
conda create -n pigbench python=3.10 -y
conda activate pigbench
```

---

## Bước 6 — Cài PyTorch 2.0.0

> Dùng **pip** thay vì conda để tránh lỗi MKL conflict (`iJIT_NotifyEvent`).

```bash
pip install torch==2.0.0 torchvision==0.15.1 torchaudio==2.0.0 \
    --index-url https://download.pytorch.org/whl/cu118

# Nếu vẫn lỗi iJIT_NotifyEvent, cài thêm:
pip install mkl==2024.0.0

# Kiểm tra
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
# Kết quả mong đợi: True  11.8
```

---

## Bước 7 — Clone repo và cài dependencies

```bash
git clone https://github.com/huanshaolin/PigBench
cd PigBench

# Pip packages
pip install -r _setup/requirements.txt

# MMDetection stack
conda install anaconda::lit -y
pip install cmake
pip install -U openmim
mim install mmengine
mim install "mmcv==2.0.0"
mim install mmdet==3.3.0
mim install mmyolo==0.6.0
```

---

## Bước 8 — Đặt model weights

```bash
mkdir -p detection/data/pretrained_weights

# Copy từ máy local
scp user@local-machine:/path/to/codino_swin.pth \
    detection/data/pretrained_weights/codino_swin.pth
```

Config mặc định trỏ đến:
```
detection/data/pretrained_weights/codino_swin.pth
```

---

## Bước 9 — Chạy inference (detection)

```bash
conda activate pigbench
cd PigBench/detection/tools/inference

python - <<'EOF'
import mmcv, sys
from mmdet.utils import register_all_modules
from mmdet.apis import init_detector, inference_detector
from visualization_utils import draw_bboxes
sys.path.append('../../')

config_path     = '../../configs/co_detr/co_dino_swin.py'
checkpoint_path = '../../data/pretrained_weights/codino_swin.pth'

register_all_modules(init_default_scope=False)
model = init_detector(config_path, checkpoint_path, device='cuda:0')

image_path = '../../data/example_images/demo_image1.jpg'
image  = mmcv.imread(image_path, channel_order='rgb')
result = inference_detector(model, image)

scores0 = result.pred_instances.scores.cpu().numpy()
bboxes0 = result.pred_instances.bboxes.cpu().numpy()

draw_bboxes(image_path=image_path, bboxes=bboxes0, scores=scores0,
            score_thresh=0.4, save_path='/tmp/result.jpg',
            linewidth=2, show_scores=True, figsize=(15, 15), score_fontsize=6)
print("Done! Saved to /tmp/result.jpg")
EOF
```

> Server không có display nên dùng `save_path='/tmp/result.jpg'` thay vì `None`.

---

## Bước 10 — Chuẩn bị video và chạy tracking

### 10.1 — Đặt model weights cho tracker

Tracking dùng lại `codino_swin.pth` làm detector và thêm ReID model (tự download khi chạy lần đầu):

```bash
# Tạo thư mục chứa weights cho tracking
mkdir -p tracking/data/pretrained

# Symlink hoặc copy checkpoint đã có
cp detection/data/pretrained_weights/codino_swin.pth \
   tracking/data/pretrained/codino_swin.pth
```

### 10.2 — Đặt video đầu vào

```bash
mkdir -p tracking/data/videos

# Copy video từ máy local (mp4)
scp user@local-machine:/path/to/pigtrack0001.mp4 \
    tracking/data/videos/pigtrack0001.mp4
```

Hoặc download video mẫu từ repo:
```
https://data.goettingen-research-online.de/dataset.xhtml?persistentId=doi:10.25625/P7VQTP
```
Giải nén lấy file `pigtrack0001.mp4`.

### 10.3 — Chạy tracking (BoT-SORT)

```bash
conda activate pigbench
cd PigBench/tracking/boxmot

python main.py \
    --config configs/botsort.yaml \
    --inference_detector_checkpoint ../../detection/data/pretrained_weights/codino_swin.pth \
    --seq_dir ../../tracking/data/videos \
    --outputs_base outputs/botsort
```

**Các tracker khác** (thay `botsort.yaml`):

| Config | Tracker |
|--------|---------|
| `configs/botsort.yaml` | BoT-SORT (khuyến nghị) |
| `configs/bytetrack.yaml` | ByteTrack |
| `configs/deepocsort.yaml` | DeepOC-SORT |
| `configs/strongsort.yaml` | StrongSORT |

### 10.4 — Kết quả output

Kết quả lưu tại:
```
tracking/boxmot/outputs/botsort/inference/<tên_video>/results/
├── tracker/          # file .txt kết quả tracking (MOT format)
└── visualization/    # video mp4 đã vẽ bounding box + ID
```

Xem video kết quả trực tiếp trên server (không cần display):
```bash
# Kiểm tra file đã tạo
ls tracking/boxmot/outputs/botsort/inference/*/results/visualization/

# Tải về máy local để xem
scp user@server:/path/to/PigBench/tracking/boxmot/outputs/botsort/inference/videos/results/visualization/pigtrack0001.mp4 \
    ~/Downloads/pigtrack_result.mp4
```

---

## Troubleshooting

### `libtinfo5` không cài được
Không cài `cuda-toolkit-11-8` qua apt trên Ubuntu 24. Dùng runfile ở Bước 2.

### `unattended-upgrades` lock apt
```bash
sudo systemctl stop unattended-upgrades
sudo rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock
sudo dpkg --configure -a
```

### `ChecksumMismatchError` khi cài conda package
```bash
conda clean --all -y
# Thử lại lệnh conda
```

### `iJIT_NotifyEvent` khi import torch
Xung đột MKL. Gỡ và cài lại PyTorch qua pip:
```bash
pip uninstall torch torchvision torchaudio -y
pip install torch==2.0.0 torchvision==0.15.1 torchaudio==2.0.0 \
    --index-url https://download.pytorch.org/whl/cu118
pip install mkl==2024.0.0
```

### `ModuleNotFoundError: No module named 'torch'`
Chưa activate conda env:
```bash
conda activate pigbench
```
