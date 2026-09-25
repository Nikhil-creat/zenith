# Runbook: Memory Leak / Unbounded Cache
Symptoms: slow, monotonic heap growth over hours, eventual OOM kill.
Root cause: in-memory cache with no eviction policy or TTL.
Fix: switch to TTLCache/LRUCache with bounded maxsize.
