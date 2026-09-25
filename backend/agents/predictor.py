"""
Predictor Agent
===============
Runs ahead of Watchtower's threshold trip: given the current trend in
a metric, extrapolates forward to estimate *time-to-breach* — how many
minutes until the metric would cross its critical threshold if the
trend continues unchecked. This is what turns ZENITH from purely
reactive into predictive: a slow_leak shape can be caught and patched
before it ever causes a user-facing incident.

Method: simple linear regression over the recent window (kept
dependency-light like watchtower's CNN); production version would use
a proper seasonal forecaster (Prophet / exponential smoothing) — see
docs/ARCHITECTURE.md.
"""

from __future__ import annotations
import numpy as np


class PredictorAgent:
    def forecast(self, series: list[float], critical_threshold: float, sample_interval_sec: int = 30) -> dict:
        arr = np.array(series[-20:]) if len(series) >= 3 else np.array(series)
        if len(arr) < 3:
            return {"time_to_breach_min": None, "trend": "insufficient_data", "reasoning": "Not enough history to forecast."}

        x = np.arange(len(arr))
        slope, intercept = np.polyfit(x, arr, 1)

        if slope <= 0:
            return {
                "time_to_breach_min": None,
                "trend": "stable_or_improving",
                "reasoning": "Trend is flat or improving — no breach predicted.",
            }

        current = arr[-1]
        steps_to_breach = (critical_threshold - current) / slope if slope > 0 else float("inf")
        minutes = max(0, steps_to_breach * sample_interval_sec / 60)

        urgency = "critical" if minutes < 15 else ("warning" if minutes < 60 else "watch")

        return {
            "time_to_breach_min": round(minutes, 1),
            "trend": "rising",
            "urgency": urgency,
            "reasoning": (
                f"Linear trend projects breach of critical threshold "
                f"({critical_threshold}) in ~{round(minutes,1)} min at current rate "
                f"(slope={round(float(slope),3)}/sample). Urgency: {urgency}."
            ),
        }
