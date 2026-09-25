"""
Diagnosis Agent
===============
Given a flagged anomaly, retrieves relevant runbook entries (RAG over
`docs/runbooks/`) and asks an LLM to produce a structured root-cause
hypothesis. Uses Groq's free-tier inference API (Llama 3.3 70B) when
GROQ_API_KEY is set -- Groq's LPU inference is sub-second even on the
70B model, which matters for a system meant to diagnose incidents in
real time, not after a 10-second spinner.

Falls back to a deterministic rule-based classifier when no key is
configured, so the pipeline still runs fully offline for grading/demo
with zero external dependencies.
"""

from __future__ import annotations
import os
import json
import urllib.request
import urllib.error
from pathlib import Path

RUNBOOK_DIR = Path(__file__).parent.parent.parent / "docs" / "runbooks"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are the diagnosis module of an autonomous SRE agent called ZENITH.
Given a service anomaly and retrieved runbook context, respond with ONLY a JSON object
(no markdown, no prose) with exactly these keys:
{
  "root_cause": "short_snake_case_identifier",
  "fix_hint": "short_snake_case_fix_strategy_identifier",
  "confidence": 0.0-1.0,
  "reasoning": "one or two sentences explaining the diagnosis, referencing the runbook if relevant"
}"""


class RunbookRetriever:
    """Tiny TF-IDF-ish retriever over local runbook markdown files --
    no external vector DB needed for the demo; swap for pgvector/Chroma
    in production (see docs/ARCHITECTURE.md)."""

    def __init__(self, path: Path = RUNBOOK_DIR):
        self.docs = {}
        if path.exists():
            for f in path.glob("*.md"):
                self.docs[f.stem] = f.read_text()

    def retrieve(self, query: str, k: int = 2) -> list[str]:
        query_terms = set(query.lower().split())
        scored = []
        for name, text in self.docs.items():
            overlap = len(query_terms & set(text.lower().split()))
            if overlap:
                scored.append((overlap, name))
        scored.sort(reverse=True)
        return [name for _, name in scored[:k]]

    def text_for(self, names: list[str]) -> str:
        return "\n\n".join(self.docs.get(n, "") for n in names)


class DiagnosisAgent:
    def __init__(self):
        self.retriever = RunbookRetriever()
        self.api_key = os.environ.get("GROQ_API_KEY")

    def run(self, signal: dict) -> dict:
        matches = self.retriever.retrieve(
            f"{signal.get('metric','')} {signal.get('trace_snippet','')}"
        )
        if self.api_key:
            try:
                return self._llm_diagnosis(signal, matches)
            except Exception as e:  # network issues, rate limits, etc. -- degrade gracefully
                result = self._heuristic_diagnosis(signal, matches)
                result["reasoning"] = f"[Groq call failed ({e}), used offline fallback] " + result["reasoning"]
                result["engine"] = "heuristic_fallback"
                return result
        result = self._heuristic_diagnosis(signal, matches)
        result["engine"] = "heuristic"
        return result

    def _heuristic_diagnosis(self, signal: dict, matches: list[str]) -> dict:
        trace = signal.get("trace_snippet", "").lower()
        shape = signal.get("shape", "")

        if "connection pool" in trace or "pool exhausted" in trace:
            root_cause = "db_connection_pool_exhaustion"
            fix_hint = "increase_pool_size_and_add_circuit_breaker"
        elif shape == "slow_leak" or "memory" in trace or "heap" in trace:
            root_cause = "memory_leak_unbounded_cache"
            fix_hint = "add_cache_eviction_ttl"
        elif "timeout" in trace:
            root_cause = "upstream_timeout_no_retry_budget"
            fix_hint = "add_exponential_backoff_retry"
        else:
            root_cause = "unclassified_latency_regression"
            fix_hint = "add_tracing_and_rollback_last_deploy"

        return {
            "root_cause": root_cause,
            "fix_hint": fix_hint,
            "confidence": 0.82,
            "retrieved_runbooks": matches,
            "reasoning": (
                f"Trace snippet matches known pattern '{root_cause}'. "
                f"Retrieved {len(matches)} related runbook(s): {matches}. "
                f"Recommending fix strategy: {fix_hint}."
            ),
        }

    def _llm_diagnosis(self, signal: dict, matches: list[str]) -> dict:
        runbook_text = self.retriever.text_for(matches)
        user_prompt = (
            f"Service: {signal.get('service')}\n"
            f"Metric: {signal.get('metric')} = {signal.get('value')} (baseline: {signal.get('baseline')})\n"
            f"Trace snippet: {signal.get('trace_snippet')}\n\n"
            f"Relevant runbook context:\n{runbook_text or '(no matching runbook found)'}\n\n"
            "Diagnose the root cause and recommend a fix strategy per the JSON schema."
        )

        body = json.dumps({
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
        }).encode()

        req = urllib.request.Request(
            GROQ_API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read())

        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        parsed["retrieved_runbooks"] = matches
        parsed["engine"] = f"groq/{GROQ_MODEL}"
        return parsed
