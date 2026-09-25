# Runbook: DB Connection Pool Exhaustion
Symptoms: p99 latency spike, "connection pool exhausted" in traces.
Root cause: pool size too small for concurrent load, or connections not released.
Fix: raise pool_size, add acquire_timeout, add circuit breaker on repeated failures.
