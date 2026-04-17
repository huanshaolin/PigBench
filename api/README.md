# PigBench API

REST API phát hiện và đếm heo qua ảnh/video, xây dựng trên **Co-DINO Swin + BoT-SORT**, phục vụ qua **FastAPI**.

> **Yêu cầu:** Hoàn thành toàn bộ [SETUP_UBUNTU.md](../SETUP_UBUNTU.md) trước khi tiếp tục.

---

## Mục lục

1. [Cấu trúc thư mục](#cấu-trúc-thư-mục)
2. [Cài đặt dependencies API](#1-cài-đặt-dependencies-api)
3. [Cấu hình .env](#2-cấu-hình-env)
4. [Cài đặt PostgreSQL](#3-cài-đặt-postgresql)
5. [Chạy migration database](#4-chạy-migration-database)
6. [Tạo API key cho user](#5-tạo-api-key-cho-user)
7. [Tạo bảng giá](#6-tạo-bảng-giá)
8. [Chạy server](#7-chạy-server)
9. [Sử dụng API](#8-sử-dụng-api)
10. [Quản lý migration](#9-quản-lý-migration)
11. [Troubleshooting](#troubleshooting)

---

## Cấu trúc thư mục

```
api/
├── main.py                      # FastAPI app + lifespan
├── run.py                       # Entry point
├── alembic.ini                  # Cấu hình Alembic
├── .env                         # Biến môi trường (không commit)
├── requirements.txt
│
├── controllers/
│   ├── detect_controller.py     # POST /detect
│   └── track_controller.py      # POST /track
│
├── services/
│   ├── detection_service.py     # Load model, detect, annotate ảnh
│   ├── tracking_service.py      # Load model, track, annotate video
│   ├── upload_service.py        # Upload Cloudinary
│   ├── log_service.py           # Ghi log vào DB
│   ├── billing_service.py       # Tính chi phí request
│   ├── queue_service.py         # Giới hạn request đồng thời
│   └── resource_monitor.py      # Đo CPU/RAM/GPU/VRAM
│
├── db/
│   ├── database.py              # Engine, session
│   ├── models.py                # ORM: ApiKey, RequestLog, PricingPlan
│   └── auth.py                  # Xác thực X-API-Key header
│
├── validation/
│   └── file_validation.py       # Validate size, duration
│
└── migrations/                  # Alembic migration files
    ├── env.py
    ├── script.py.mako
    └── versions/
```

---

## 1. Cài đặt dependencies API

```bash
conda activate pigbench
cd /root/PigBench
pip install -r api/requirements.txt
```

---

## 2. Cấu hình .env

Sửa file `api/.env`:

```env
# Device
PIGBENCH_DEVICE=cuda:0          # hoặc cpu

# Cloudinary — lấy tại cloudinary.com → Dashboard → API Keys
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# PostgreSQL
DATABASE_URL=postgresql://pigbench:yourpassword@localhost:5432/pigbench

# Uvicorn
HOST=0.0.0.0
PORT=8000
WORKERS=1
```

---

## 3. Cài đặt PostgreSQL

```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Tạo user và database
sudo -u postgres psql <<EOF
CREATE USER pigbench WITH PASSWORD 'yourpassword';
CREATE DATABASE pigbench OWNER pigbench;
EOF
```

---

## 4. Chạy migration database

```bash
conda activate pigbench
cd /root/PigBench/api

# Lần đầu — tạo migration từ models hiện tại
alembic revision --autogenerate -m "init"
alembic upgrade head

# Kiểm tra
alembic current
```

> Mỗi khi thêm/sửa column trong `db/models.py`, chạy lại:
> ```bash
> alembic revision --autogenerate -m "mo_ta_thay_doi"
> alembic upgrade head
> ```

---

## 5. Tạo API key cho user

```bash
# Tạo key ngẫu nhiên
python -c "import secrets; print(secrets.token_hex(32))"
# → ví dụ: a3f8c2d1e4b5...

# Thêm vào database
sudo -u postgres psql -d pigbench <<EOF
INSERT INTO api_keys (key, user_name, is_active, created_at)
VALUES ('a3f8c2d1e4b5...', 'user1', true, NOW());
EOF
```

---

## 6. Tạo bảng giá

```bash
sudo -u postgres psql -d pigbench <<EOF
INSERT INTO pricing_plans (
    name,
    price_per_request,
    price_per_upload_mb,
    price_per_cpu_ms,
    price_per_ram_mb,
    price_per_gpu_pct,
    price_per_vram_mb,
    valid_from,
    valid_until,
    is_active,
    created_at
) VALUES (
    'Standard',
    0.01,       -- $0.01 mỗi request
    0.005,      -- $0.005 mỗi MB upload
    0.000001,   -- $0.000001 mỗi ms CPU
    0.0001,     -- $0.0001 mỗi MB RAM peak
    0.0002,     -- $0.0002 mỗi % GPU trung bình
    0.0001,     -- $0.0001 mỗi MB VRAM peak
    '2025-01-01',
    NULL,       -- NULL = vô thời hạn
    true,
    NOW()
);
EOF
```

**Công thức tính tiền:**
```
cost = price_per_request
     + price_per_upload_mb  × uploaded_file_mb
     + price_per_cpu_ms     × cpu_ms
     + price_per_ram_mb     × ram_mb
     + price_per_gpu_pct    × gpu_percent
     + price_per_vram_mb    × vram_mb
```

> Request thất bại → `cost = 0.0`

---

## 7. Chạy server

```bash
conda activate pigbench
cd /root/PigBench
python api/run.py
```

**Chạy nền với nohup:**

```bash
nohup python api/run.py > api/server.log 2>&1 &
echo $! > api/server.pid

# Xem log
tail -f api/server.log

# Stop
kill $(cat api/server.pid)
```

**Kiểm tra server:**

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "device": "cuda:0",
  "queues": {
    "image": {"max_concurrent": 3, "active": 0, "waiting": 0},
    "video": {"max_concurrent": 2, "active": 0, "waiting": 0}
  }
}
```

**Swagger UI:** `http://<server-ip>:8000/docs`

---

## 8. Sử dụng API

Tất cả request phải kèm header `X-API-Key`.

### POST /detect — Phát hiện heo trong ảnh

```bash
curl -X POST http://localhost:8000/detect \
  -H "X-API-Key: your-api-key" \
  -F "file=@pig.jpg" \
  -F "score_thresh=0.4" \
  -F "export_file=true"
```

**Response:**
```json
{
  "total_pigs": 12,
  "score_thresh": 0.4,
  "filename": "pig.jpg",
  "image_url": "https://res.cloudinary.com/.../detect_pig.jpg",
  "processing_seconds": 2.31,
  "resources": {
    "cpu_ms": 1234.5,
    "ram_mb": 3812.5,
    "gpu_percent": 87.0,
    "vram_mb": 6144.3
  },
  "cost": 0.0234
}
```

| Query param | Default | Mô tả |
|-------------|---------|-------|
| `score_thresh` | `0.4` | Ngưỡng confidence (0–1) |
| `export_file` | `true` | Upload ảnh annotated lên Cloudinary |

**Giới hạn file:** tối đa **10 MB**

---

### POST /track — Tracking heo trong video

```bash
curl -X POST http://localhost:8000/track \
  -H "X-API-Key: your-api-key" \
  -F "file=@pigtrack.mp4" \
  -F "min_conf=0.1" \
  -F "export_file=true"
```

**Response:**
```json
{
  "max_pigs_in_frame": 18,
  "frame_counts": [15, 17, 18, 16, 14],
  "total_frames": 140,
  "min_conf": 0.1,
  "filename": "pigtrack.mp4",
  "video_url": "https://res.cloudinary.com/.../track_pigtrack.mp4",
  "processing_seconds": 87.4,
  "resources": {
    "cpu_ms": 45230.1,
    "ram_mb": 4102.0,
    "gpu_percent": 91.2,
    "vram_mb": 7680.0
  },
  "cost": 1.2341
}
```

| Query param | Default | Mô tả |
|-------------|---------|-------|
| `min_conf` | `0.1` | Ngưỡng confidence cho tracker (0–1) |
| `export_file` | `true` | Upload video annotated lên Cloudinary |

**Giới hạn file:** tối đa **20 MB**, **10 giây**

---

### Lỗi thường gặp

| HTTP | Nguyên nhân |
|------|-------------|
| `400` | File sai định dạng / vượt giới hạn kích thước / video quá dài |
| `401` | `X-API-Key` không hợp lệ hoặc bị vô hiệu hoá |
| `503` | Hàng chờ đầy, request chờ quá 5 phút |

---

## 9. Quản lý migration

```bash
cd /root/PigBench/api

# Xem lịch sử
alembic history

# Version hiện tại
alembic current

# Tạo migration mới sau khi sửa db/models.py
alembic revision --autogenerate -m "ten_thay_doi"
alembic upgrade head

# Rollback 1 version
alembic downgrade -1

# Rollback toàn bộ
alembic downgrade base
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'configs.co_detr'`
```bash
# Đảm bảo chạy từ root repo, không phải từ api/
cd /root/PigBench
python api/run.py
```

### `KeyError: CoATSSHead is already registered`
Xảy ra khi cả detection và tracking load config riêng biệt. Cả hai đều dùng `detection/configs/co_detr/co_dino_swin.py` — không đổi đường dẫn config.

### `No module named 'torch'`
```bash
conda activate pigbench
```

### `Invalid or inactive API key` (401)
Kiểm tra key trong DB:
```sql
SELECT * FROM api_keys WHERE key = 'your-key';
```

### Queue timeout (503)
Server đang xử lý nhiều request. Thử lại sau hoặc tăng `MAX_CONCURRENT_IMAGE` / `MAX_CONCURRENT_VIDEO` trong `services/queue_service.py`.
