# Runbook: Upstream Timeout, No Retry Budget
Symptoms: latency spike correlated with third-party API degradation.
Root cause: no retry/backoff strategy, single slow call blocks the request.
Fix: add exponential backoff retry with capped attempts and jitter.
