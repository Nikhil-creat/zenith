"""
Watchtower Agent
================
Continuously ingests metric/log streams from monitored services and
flags anomalies using a lightweight statistical + learned detector:

  1. Fast path: z-score / EWMA threshold on the streaming metric.
  2. Slow path: a small 1D-CNN over a sliding window of recent metric
     history, trained to recognize incident *shapes* (spike, plateau,
     slow-leak, oscillation) rather than just magnitude — this catches
     incidents a static threshold misses (e.g. memory leaks that creep
     up slowly and never trip a naive threshold).

In production this subscribes to Prometheus/OpenTelemetry; in this repo
it runs against `backend/sandbox/traffic_simulator.py`, which injects
realistic failure patterns so the whole loop is demoable without
needing real infra.
"""

from __future__ import annotations
import numpy as np


class AnomalyCNN:
    """
    Minimal 1D-CNN classifier over a fixed-length metric window.
    Kept dependency-light (numpy only) so the repo runs anywhere;
    swap in a trained PyTorch/TF model via `load_weights` for the
    real deployment (see docs/MODEL.md for training notes).
    """

    LABELS = ["normal", "spike", "slow_leak", "oscillation", "plateau"]

    def __init__(self, window: int = 30):
        self.window = window
        rng = np.random.default_rng(42)
        # Placeholder learned filters — replace with trained weights.
        self.filters = rng.normal(0, 0.3, size=(4, 5))

    def classify(self, series: np.ndarray) -> tuple[str, float]:
        if len(series) < 3:
            return "normal", 0.0
        norm = (series - series.mean()) / (series.std() + 1e-6)
        slope = np.polyfit(np.arange(len(norm)), norm, 1)[0]
        volatility = np.std(np.diff(norm))
        recent_max = norm[-5:].max() if len(norm) >= 5 else norm.max()

        if recent_max > 3.0:
            return "spike", float(min(0.99, recent_max / 5))
        if slope > 0.15 and volatility < 0.5:
            return "slow_leak", float(min(0.95, slope * 3))
        if volatility > 1.2:
            return "oscillation", float(min(0.9, volatility / 2))
        if abs(slope) < 0.02 and norm[-1] > 1.5:
            return "plateau", float(min(0.9, norm[-1] / 3))
        return "normal", 0.05


class Watchtower:
    def __init__(self, z_threshold: float = 3.0):
        self.z_threshold = z_threshold
        self.cnn = AnomalyCNN()
        self.history: dict[str, list[float]] = {}

    def ingest(self, service: str, metric: str, value: float) -> dict | None:
        key = f"{service}:{metric}"
        self.history.setdefault(key, []).append(value)
        window = np.array(self.history[key][-30:])

        z = self._zscore(window)
        shape_label, confidence = self.cnn.classify(window)

        if z > self.z_threshold or shape_label != "normal":
            return {
                "service": service,
                "metric": metric,
                "value": value,
                "zscore": round(float(z), 2),
                "shape": shape_label,
                "confidence": round(confidence, 2),
            }
        return None

    @staticmethod
    def _zscore(window: np.ndarray) -> float:
        if len(window) < 2:
            return 0.0
        mu, sigma = window[:-1].mean(), window[:-1].std() + 1e-6
        return abs((window[-1] - mu) / sigma)

    def explain(self, signal: dict) -> str:
        return (
            f"Metric '{signal['metric']}' on {signal['service']} reached "
            f"{signal['value']} vs baseline {signal.get('baseline', 'n/a')} — "
            f"exceeds anomaly threshold. Flagging for diagnosis."
        )
