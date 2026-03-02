"""Optional native (C++) kernel for S02 weather probability calculations."""
from __future__ import annotations

import math
import os
import subprocess
import threading
from pathlib import Path
from typing import Iterable, Optional, Tuple


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _python_temperature(temps: list[float], threshold_f: float, above: bool) -> Tuple[float, float]:
    if not temps:
        return 0.5, 0.20
    hits = 0
    margin_sum = 0.0
    for temp in temps:
        if above:
            if temp > threshold_f:
                hits += 1
            margin_sum += temp - threshold_f
        else:
            if temp < threshold_f:
                hits += 1
            margin_sum += threshold_f - temp
    n = float(len(temps))
    prob = hits / n
    avg_margin = margin_sum / n
    margin_score = math.tanh(abs(avg_margin) / 6.0)
    sample_score = min(1.0, math.sqrt(n / 24.0))
    conf = _clamp(0.40 + 0.35 * margin_score + 0.20 * sample_score, 0.35, 0.95)
    return _clamp(prob), conf


def _python_precip(pops_pct: list[float]) -> Tuple[float, float]:
    if not pops_pct:
        return 0.0, 0.20
    probs = [_clamp(float(p) / 100.0) for p in pops_pct]
    mean = sum(probs) / len(probs)
    variance = (sum(p * p for p in probs) / len(probs)) - (mean * mean)
    variance = max(0.0, variance)
    norm_var = _clamp(variance / 0.25)
    sample_score = min(1.0, math.sqrt(len(probs) / 24.0))
    conf = _clamp(0.45 + 0.30 * (1.0 - norm_var) + 0.20 * sample_score, 0.35, 0.95)
    return _clamp(mean), conf


class NativeS02WeatherKernel:
    """Stream forecast arrays into a native process for low-latency scoring.

    Falls back to Python math if the native executable is unavailable.
    """

    def __init__(self, binary_path: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen[str]] = None
        self._require_native = os.getenv("S02_WEATHER_NATIVE_ONLY", "0") == "1"
        self._binary = Path(
            binary_path
            or os.getenv("S02_WEATHER_KERNEL_BIN")
            or Path(__file__).resolve().parents[1] / "native" / "s02_weather_signal_engine"
        )
        self._enabled = self._spawn()
        if self._require_native and not self._enabled:
            raise RuntimeError(f"S02 native kernel required but unavailable: {self._binary}")

    def _spawn(self) -> bool:
        if not self._binary.exists() or not os.access(self._binary, os.X_OK):
            return False
        try:
            self._proc = subprocess.Popen(
                [str(self._binary)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            return self._proc.stdin is not None and self._proc.stdout is not None
        except Exception:
            self._proc = None
            return False

    @property
    def native_enabled(self) -> bool:
        return bool(self._enabled)

    @staticmethod
    def _csv(values: Iterable[float]) -> str:
        return ",".join(f"{float(v):.4f}" for v in values)

    def _query(self, payload: str) -> Optional[Tuple[float, float]]:
        if not self._enabled or self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            return None
        with self._lock:
            try:
                self._proc.stdin.write(payload + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline().strip()
                if not line:
                    return None
                parts = line.split()
                if len(parts) < 2:
                    return None
                prob = float(parts[0])
                conf = float(parts[1])
                return _clamp(prob), _clamp(conf)
            except Exception:
                self._enabled = False
                return None

    def temperature_probability(self, temps: list[float], threshold_f: float, above: bool = True) -> Tuple[float, float]:
        temps_clean = [float(t) for t in temps if isinstance(t, (float, int))]
        if not temps_clean:
            return 0.5, 0.20

        payload = f"TEMP|{float(threshold_f):.4f}|{1 if above else 0}|{self._csv(temps_clean)}"
        native = self._query(payload)
        if native is not None:
            return native
        return _python_temperature(temps_clean, float(threshold_f), bool(above))

    def precipitation_probability(self, pops_pct: list[float]) -> Tuple[float, float]:
        pops_clean = [float(p) for p in pops_pct if isinstance(p, (float, int))]
        if not pops_clean:
            return 0.0, 0.20

        payload = f"PRECIP|{self._csv(pops_clean)}"
        native = self._query(payload)
        if native is not None:
            return native
        return _python_precip(pops_clean)

    def close(self) -> None:
        with self._lock:
            if self._proc is None:
                return
            try:
                if self._proc.stdin is not None:
                    self._proc.stdin.write("QUIT\n")
                    self._proc.stdin.flush()
            except Exception:
                pass
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
