# ZENITH — Autonomous Self-Healing SRE Agent

**Live demo (GitHub Pages):** `https://nikhil-creat.github.io/zenith/`

ZENITH is a multi-agent system that watches a production service, detects an incident, diagnoses the root cause, writes a code/config fix, tests it in a sandbox, and deploys it — **with no human in the loop**. When it can't fix something safely after retries, it escalates instead of guessing forever.

Most "agentic AI" portfolio projects generate content (chat, RAG answers, images). ZENITH takes autonomous *action* on live infrastructure — perceive, diagnose, patch, verify, deploy — which is the operational-autonomy skillset behind real AIOps/SRE-copilot systems (e.g. what teams at Datadog, PagerDuty, and internal platform teams at big tech are actively building toward).

## The loop

```
metrics ──▶ Predictor ──▶ Watchtower ──▶ Diagnosis ──▶ Patch ──▶ SecurityAuditor ──▶ Verifier ──▶ Deploy
            (forecasts     (anomaly       (RAG over     (fix        (scans diff        (sandbox      (canary +
             time-to-       CNN +          runbooks)     templates)  for risky           replay)       rollback)
             breach)        z-score)                                 patterns)
                                              ▲_______________________|_________________|
                                        retry w/ escalated fix tier if security OR verification rejects it
```

Every stage writes a structured, human-readable reasoning entry to an audit log, and the entire log is **hash-chained** (SHA-256, each entry references the previous entry's hash — same idea as a blockchain) so the trail is tamper-evident: the dashboard shows a live chain-integrity check per incident. Each resolved incident also computes an estimated **cost impact** (minutes of downtime avoided vs. a human MTTR baseline, revenue protected).

## What's real vs. simulated in this repo

This is built to run **fully offline with zero API keys and zero cloud infra**, so it's gradable/demoable anywhere:

| Component | This repo | Production version |
|---|---|---|
| Prediction | Linear-trend time-to-breach forecaster (NumPy) | Seasonal forecaster (Prophet/ETS) over real historical incident data |
| Anomaly detection | NumPy-only 1D-CNN + z-score, deterministic | Trained PyTorch model on real Prometheus streams |
| Diagnosis | Groq (Llama 3.3 70B) when `GROQ_API_KEY` is set, else a deterministic heuristic classifier — both grounded in local RAG over `docs/runbooks/` | Same Groq/LLM pipeline, hardened with retries and response validation |
| Patch generation | Parameterized fix-template library, escalates tier on retry | LLM-generated diffs against the real repo, opened as a PR |
| Security review | Regex-based static scan for hardcoded secrets, disabled auth/TLS, SQLi patterns | Real SAST integration (Semgrep/CodeQL) gating every generated diff |
| Sandbox verification | Deterministic simulated pass/fail by fix tier | Docker container replaying recorded traffic against the patched service |
| Deploy | Simulated canary → rollout sequence | Real kubectl/ArgoCD canary rollout with automatic rollback |
| Audit trail | SHA-256 hash-chained log, verified per incident | Same, anchored periodically to an external timestamping service |

The **control flow, agent boundaries, and audit trail are exactly what would ship in production** — only the I/O at the edges (real metrics, real LLM calls, real Kubernetes) is swapped for deterministic stand-ins, per `docs/ARCHITECTURE.md`.

## Run it yourself

```bash
git clone https://github.com/Nikhil-creat/zenith.git
cd zenith
pip install -r requirements.txt

# Optional: enable real LLM diagnosis via Groq's free tier (Llama 3.3 70B,
# sub-second inference on Groq's LPU hardware). Get a free key at
# https://console.groq.com/keys — without it, ZENITH runs fully offline
# using its deterministic rule-based fallback (see backend/agents/diagnosis.py).
cp .env.example .env && echo "GROQ_API_KEY=gsk_..." >> .env
export $(cat .env | xargs)

python backend/sandbox/traffic_simulator.py       # runs 4 real incidents through the full agent pipeline
python backend/core/orchestrator.py               # run a single incident end-to-end, see raw JSON output
```

Each incident's diagnosis records which reasoning engine produced it (`"engine": "groq/llama-3.3-70b-versatile"` or `"engine": "heuristic"`) — the dashboard shows this as a badge per incident, so it's always transparent whether a given diagnosis came from real LLM reasoning or the offline fallback.

Regenerating `frontend/src/data/demo_run.json` and rebuilding `docs/index.html` reruns the *actual* agents — the dashboard is not hand-authored content, it's a replay of a real pipeline execution.

## Repo layout

```
backend/
  agents/         watchtower.py, predictor.py, diagnosis.py, patch.py,
                  security_auditor.py, verifier.py, deploy.py
  core/           orchestrator.py — state machine wiring the agents together
                  audit_chain.py — SHA-256 hash-chained, tamper-evident audit log
  sandbox/        traffic_simulator.py — synthetic incident generator
docs/
  runbooks/       knowledge base retrieved by the diagnosis agent
  ARCHITECTURE.md
  index.html      GitHub Pages dashboard (self-contained, embeds real run data)
frontend/
  src/data/       demo_run.json — output of an actual pipeline run
```

## Why this project (for reviewers)

- **Multi-agent orchestration** with real retry/escalation logic across two independent safety gates (security + verification), not a single LLM call wrapped in a UI
- **Predictive, not just reactive** — the Predictor agent forecasts time-to-breach from trend data, the kind of "catch it before it pages anyone" capability real SRE platforms are built around
- **RAG grounded in a real knowledge base** (runbooks) rather than the model's parametric memory
- **Security-aware autonomy** — a dedicated agent scans every self-generated patch for risky patterns before it's allowed near a sandbox, treating "the agent's own output" as an attack surface
- **Tamper-evident audit trail** — hash-chained logs mean the reasoning record for an autonomous action can be cryptographically verified, not just trusted
- **Quantified impact** — every incident reports downtime-minutes and revenue protected vs. a human-MTTR baseline, the language SRE leadership actually reports in
- **Fully reproducible** — every number on the dashboard came from an actual run of the code in this repo, checked in as data, not written by hand

## Roadmap

- [x] Real LLM diagnosis via Groq (Llama 3.3 70B) with graceful offline fallback
- [ ] Real Docker sandbox in `verifier.py` instead of simulated pass/fail
- [ ] Live Prometheus/OpenTelemetry ingestion in `watchtower.py`
- [ ] GitHub PR integration for the patch agent (open real PRs against a target repo)

---

**Designed & Developed by NIKHIL CHARY SRIRAMOJU**
[GitHub](https://github.com/Nikhil-creat) · [LinkedIn](https://in.linkedin.com/in/nikhil-chary-sriramoju-95041b38a)
