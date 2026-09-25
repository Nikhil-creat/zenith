"""
Patch Agent
===========
Translates a root-cause hypothesis into an actual code/config diff.
Maintains a library of parameterized fix templates keyed by
`fix_hint` (from DiagnosisAgent) and adapts them to the failing
service. On retry (attempt > 1), escalates to a more aggressive fix
tier rather than repeating the same patch — this is what makes the
patch/verify loop genuinely agentic instead of a single fixed attempt.
"""

from __future__ import annotations

FIX_TEMPLATES = {
    "increase_pool_size_and_add_circuit_breaker": [
        # attempt 1: minimal fix
        {
            "file": "config/db.yaml",
            "diff": "- pool_size: 10\n+ pool_size: 40\n+ acquire_timeout_ms: 2000",
        },
        # attempt 2: escalate — add circuit breaker
        {
            "file": "services/checkout/db_client.py",
            "diff": (
                "+ from resilience import CircuitBreaker\n"
                "+ breaker = CircuitBreaker(fail_max=5, reset_timeout=30)\n"
                "+ @breaker\n"
                "  def get_connection(self):\n"
                "      return self.pool.acquire()"
            ),
        },
    ],
    "add_cache_eviction_ttl": [
        {
            "file": "services/cache/lru.py",
            "diff": "- cache = {}\n+ cache = TTLCache(maxsize=5000, ttl=300)",
        },
    ],
    "add_exponential_backoff_retry": [
        {
            "file": "services/http_client.py",
            "diff": (
                "+ @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(4))\n"
                "  def call_upstream(self, req):\n"
                "      return self.session.post(req)"
            ),
        },
    ],
    "add_tracing_and_rollback_last_deploy": [
        {
            "file": "deploy/rollback.sh",
            "diff": "+ kubectl rollout undo deployment/${SERVICE} --to-revision=$(($CURRENT-1))",
        },
    ],
}


class PatchAgent:
    def run(self, diagnosis: dict, attempt: int = 1) -> dict:
        hint = diagnosis["fix_hint"]
        templates = FIX_TEMPLATES.get(hint, FIX_TEMPLATES["add_tracing_and_rollback_last_deploy"])
        tier = min(attempt - 1, len(templates) - 1)
        chosen = templates[tier]

        return {
            "fix_hint": hint,
            "attempt": attempt,
            "file": chosen["file"],
            "diff": chosen["diff"],
            "reasoning": (
                f"Applying tier-{tier+1} fix for '{hint}' "
                f"({'initial attempt' if attempt == 1 else 'escalated after prior failure'}) "
                f"targeting {chosen['file']}."
            ),
        }
