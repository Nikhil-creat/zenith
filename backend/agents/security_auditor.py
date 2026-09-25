"""
Security Auditor Agent
======================
Gatekeeper between Patch and Verifier: scans every generated diff for
known-risky patterns before it's allowed anywhere near a sandbox or
deploy. This matters because an autonomous patch-writing agent is a
real attack surface — an LLM-generated fix could accidentally
introduce a vulnerability while "fixing" the original incident (e.g.
disabling a timeout by disabling auth, or fixing a leak by logging
secrets). No production self-healing system should skip this step.

Checks performed (static, regex-based — see docs/ARCHITECTURE.md for
how this upgrades to a real SAST tool like Semgrep in production):
  - hardcoded credentials / API keys
  - disabled authentication or TLS verification
  - raw SQL string concatenation (injection risk)
  - overly permissive file/network settings
"""

from __future__ import annotations
import re

RISK_PATTERNS = [
    (r"(?i)(api[_-]?key|secret|password)\s*=\s*['\"][^'\"]+['\"]", "hardcoded_credential"),
    (r"(?i)verify\s*=\s*False", "disabled_tls_verification"),
    (r"(?i)auth(entication)?\s*=\s*(None|False|Disabled)", "disabled_authentication"),
    (r"(?i)f?[\"'].*\{.*\}.*(select|insert|update|delete)\s", "possible_sql_injection"),
    (r"(?i)chmod\s+777|0\.0\.0\.0/0", "overly_permissive_access"),
]


class SecurityAuditor:
    def audit(self, patch: dict) -> dict:
        diff = patch.get("diff", "")
        findings = []
        for pattern, label in RISK_PATTERNS:
            if re.search(pattern, diff):
                findings.append(label)

        passed = len(findings) == 0
        return {
            "passed": passed,
            "findings": findings,
            "reasoning": (
                "No risky patterns detected in generated diff — cleared for sandbox testing."
                if passed else
                f"Blocked: patch contains risky pattern(s) {findings}. Returning to Patch agent for revision."
            ),
        }
