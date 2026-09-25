"""
Traffic Simulator
=================
Generates a realistic multi-service metric history with injected
failures (latency spikes, memory leaks, upstream timeouts, CPU
oscillation) so the full ZENITH loop -- including the Predictor's
trend forecasting -- can run and be demoed with zero real
infrastructure. Also produces the static `demo_run.json` bundled with
the GitHub Pages dashboard.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from core.orchestrator import Orchestrator  # noqa: E402

SCENARIOS = [
    {
        "signal": {
            "service": "checkout-api",
            "metric": "p99_latency_ms",
            "value": 4200,
            "baseline": 180,
            "trace_snippet": "TimeoutError: connection pool exhausted (db_pool size=10)",
        },
        "history": [180, 190, 210, 260, 340, 520, 900, 1800, 4200],
    },
    {
        "signal": {
            "service": "recommendation-engine",
            "metric": "heap_used_mb",
            "value": 1850,
            "baseline": 400,
            "trace_snippet": "gradual heap growth, suspected unbounded in-memory cache",
        },
        "history": [400, 460, 540, 640, 760, 910, 1100, 1400, 1850],
    },
    {
        "signal": {
            "service": "payments-gateway",
            "metric": "p99_latency_ms",
            "value": 3100,
            "baseline": 220,
            "trace_snippet": "upstream bank API timeout, no retry configured",
        },
        "history": [220, 230, 260, 290, 800, 1400, 2100, 2600, 3100],
    },
    {
        "signal": {
            "service": "search-indexer",
            "metric": "cpu_pct",
            "value": 97,
            "baseline": 35,
            "trace_snippet": "unexplained oscillating CPU, no clear trace match",
        },
        "history": [35, 60, 40, 75, 45, 88, 50, 92, 97],
    },
]


def generate_demo_run(out_path: str = "frontend/src/data/demo_run.json"):
    orch = Orchestrator()
    incidents = [orch.handle_signal(s["signal"], history=s["history"]).to_json() for s in SCENARIOS]
    for inc, s in zip(incidents, SCENARIOS):
        inc["metric_history"] = s["history"]
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"incidents": incidents}, indent=2))
    print(f"Wrote {len(incidents)} incidents to {out}")


if __name__ == "__main__":
    generate_demo_run()
