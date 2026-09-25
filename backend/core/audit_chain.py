"""
Tamper-Evident Audit Chain
==========================
Every audit entry is hashed together with the hash of the entry before
it (classic blockchain-style hash chaining), so the recorded reasoning
trail for an incident cannot be silently edited after the fact without
breaking the chain — important for a system that autonomously takes
production actions: the "why did it do that" record has to be trusted
as much as the action itself.

`verify_chain` recomputes every hash and confirms the chain is intact;
the dashboard surfaces this as a verification badge per incident.
"""

from __future__ import annotations
import hashlib
import json


GENESIS_HASH = "0" * 64


def _hash_entry(prev_hash: str, entry: dict) -> str:
    payload = json.dumps({"prev": prev_hash, "entry": entry}, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def chain_entries(entries: list[dict]) -> list[dict]:
    """Given a list of audit entries (as produced by Incident.log),
    return them annotated with hash + prev_hash fields."""
    chained = []
    prev = GENESIS_HASH
    for entry in entries:
        # hash over the entry's original fields only, so re-chaining is deterministic
        core = {k: v for k, v in entry.items() if k not in ("hash", "prev_hash")}
        h = _hash_entry(prev, core)
        chained.append({**entry, "prev_hash": prev, "hash": h})
        prev = h
    return chained


def verify_chain(chained_entries: list[dict]) -> dict:
    prev = GENESIS_HASH
    for i, entry in enumerate(chained_entries):
        core = {k: v for k, v in entry.items() if k not in ("hash", "prev_hash")}
        expected = _hash_entry(prev, core)
        if entry.get("prev_hash") != prev or entry.get("hash") != expected:
            return {"valid": False, "broken_at_index": i}
        prev = entry["hash"]
    return {"valid": True, "broken_at_index": None, "final_hash": prev}
