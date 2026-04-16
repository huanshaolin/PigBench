import os
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

load_dotenv(Path(__file__).parent / ".env")

host    = os.getenv("HOST", "0.0.0.0")
port    = int(os.getenv("PORT", 8000))
workers = int(os.getenv("WORKERS", 1))

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        workers=workers,
    )
