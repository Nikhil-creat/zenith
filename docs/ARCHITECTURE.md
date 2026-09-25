# Architecture

## Design goals
1. **Agent boundaries mirror a real production system** so swapping any simulated component for a real one (Docker, Kubernetes, Anthropic API) is a localized change, not a rewrite.
2. **Every decision is auditable.** No agent silently mutates state — each writes a structured `AuditEntry` with its reasoning, so the dashboard replay is a faithful trace, not a summary.
3. **Runs anywhere with zero setup.** No API keys, no Docker daemon, no cloud account required to see the full loop execute and produce real output.

## Why a retry loop instead of a single-shot pipeline
Early incident-response demos generate one fix and call it done. Real incidents often need an *escalating* response: a cheap fix first (bump a config value), and only if that fails, a more invasive one (add a circuit breaker, roll back a deploy). `Orchestrator.handle_signal` encodes this directly: the patch/verify pair runs in a bounded loop (`MAX_PATCH_ATTEMPTS = 3`), and `PatchAgent` picks a fix **tier** based on the attempt number, not just the fix type. This is what makes the system agentic — it revises its own hypothesis based on verification feedback — rather than a fixed DAG.

## Why RAG over runbooks instead of raw LLM diagnosis
Grounding the diagnosis in `docs/runbooks/*.md` means the agent's root-cause hypothesis is traceable to a specific document, which is both more auditable and closer to how real SRE teams actually diagnose incidents (via runbooks and postmortems, not vibes). The retriever here is intentionally simple (term-overlap scoring) to stay dependency-light; swapping in a real embedding-based retriever (Chroma/pgvector) only touches `RunbookRetriever`.

## Why the sandbox is simulated, not a real Docker container
A real verifier would spin up the patched service in an isolated container and replay recorded production traffic against it — that's the production design, and `verifier.py`'s docstring specifies exactly how. For this repo, `_simulate_sandbox`-style pass rates per fix tier let the *system's behavior* (attempt 1 sometimes insufficient, escalated attempts reliable) be demonstrated deterministically without requiring a Docker daemon in CI or on a grader's machine.

## Data flow for the dashboard
`traffic_simulator.py` is not a mock — it runs real `Signal` objects through the actual `Orchestrator`, and the resulting `Incident` objects (with their real audit logs) are serialized to `frontend/src/data/demo_run.json`. `docs/index.html` embeds that JSON directly at build time. **The dashboard shows the output of code actually executing, not hand-written example content.**

## Extension points
| File | Swap simulated → real by |
|---|---|
| `agents/watchtower.py` | Replace `AnomalyCNN` weights with a trained model; subscribe to a real Prometheus remote-write stream instead of `traffic_simulator.py` |
| `agents/diagnosis.py` | Set `ANTHROPIC_API_KEY`; implement `_llm_diagnosis` to call `/v1/messages` with retrieved runbook text |
| `agents/verifier.py` | Replace `_simulate_sandbox` with a Docker Compose spin-up + traffic replay + real metric scrape |
| `agents/deploy.py` | Replace simulated steps with real `gh pr create` + `kubectl`/ArgoCD calls |
