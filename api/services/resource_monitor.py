import threading
import time
import psutil
import torch

try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_AVAILABLE = True
except Exception:
    _NVML_AVAILABLE = False


def _gpu_index_from_device(device: str) -> int:
    if not device.startswith("cuda"):
        return -1
    parts = device.split(":")
    return int(parts[1]) if len(parts) > 1 else 0


class ResourceMonitor:
    """
    Đo tài nguyên trong khi một block code chạy:
      - cpu_ms      : tổng thời gian CPU thực sự xử lý (user + system), đơn vị ms
      - ram_mb      : RAM peak của process (MB)
      - gpu_percent : % GPU trung bình (pynvml)
      - vram_mb     : VRAM peak (MB)

    Usage:
        monitor = ResourceMonitor(device="cuda:0")
        monitor.start()
        # ... heavy work ...
        stats = monitor.stop()
        # {"cpu_ms": 1234.5, "ram_mb": 3200.1, "gpu_percent": 87.0, "vram_mb": 6400.5}
    """

    def __init__(self, device: str = "cuda:0", sample_interval: float = 0.5):
        self._gpu_idx         = _gpu_index_from_device(device)
        self._sample_interval = sample_interval
        self._process         = psutil.Process()

        # CPU time snapshot
        self._cpu_times_start: psutil._common.ppcputimes | None = None

        # Sampled metrics
        self._ram_samples:  list[float] = []
        self._gpu_samples:  list[float] = []
        self._vram_samples: list[float] = []

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._ram_samples  = []
        self._gpu_samples  = []
        self._vram_samples = []
        self._stop_event.clear()
        self._cpu_times_start = self._process.cpu_times()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> dict:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)

        # CPU time = delta(user + system) in ms
        cpu_ms = 0.0
        if self._cpu_times_start is not None:
            t_end  = self._process.cpu_times()
            delta  = (t_end.user - self._cpu_times_start.user) + \
                     (t_end.system - self._cpu_times_start.system)
            cpu_ms = round(delta * 1000, 1)

        return {
            "cpu_ms":      cpu_ms,
            "ram_mb":      round(max(self._ram_samples,  default=0.0), 1),
            "gpu_percent": round(sum(self._gpu_samples)  / len(self._gpu_samples)  if self._gpu_samples  else 0.0, 1),
            "vram_mb":     round(max(self._vram_samples, default=0.0), 1),
        }

    # ------------------------------------------------------------------
    def _loop(self) -> None:
        handle = None
        if _NVML_AVAILABLE and self._gpu_idx >= 0:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(self._gpu_idx)
            except Exception:
                pass

        while not self._stop_event.is_set():
            self._ram_samples.append(self._process.memory_info().rss / (1024 * 1024))

            if handle is not None:
                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    mem  = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    self._gpu_samples.append(float(util.gpu))
                    self._vram_samples.append(mem.used / (1024 * 1024))
                except Exception:
                    pass
            elif torch.cuda.is_available() and self._gpu_idx >= 0:
                self._vram_samples.append(
                    torch.cuda.memory_allocated(self._gpu_idx) / (1024 * 1024)
                )

            self._stop_event.wait(timeout=self._sample_interval)
