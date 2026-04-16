import os
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

# Đổi CWD sang thư mục api/ để các import nội bộ (detector, tracker, ...) hoạt động
API_DIR = Path(__file__).parent
os.chdir(API_DIR)

load_dotenv(API_DIR / ".env")

host    = os.getenv("HOST", "0.0.0.0")
port    = int(os.getenv("PORT", 8000))
workers = int(os.getenv("WORKERS", 1))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
    )
