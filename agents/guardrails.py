"""Hard-locked safety guardrail suite.

- Token spend budget with alert threshold and hard cutoff
- Immutable config verification (SHA pinned at bootstrap by init-skills.sh)
- Audit watchdog: JSONL logs with retention sweep
- Forbidden-action filter
- Prompt compression / context pruning helper
"""
import hashlib
import json
import os
import pathlib
import threading
import time

LOCK_FILE = "/app/config/guardrails.lock.json"
LOCK_SHA_FILE = "/data/state/guardrails.sha256"
AUDIT_DIR = pathlib.Path("/app/audit-logs")
USAGE_FILE = pathlib.Path("/data/state/token_usage.json")


class TokenBudgetExceeded(RuntimeError):
    pass


class GuardrailTampered(RuntimeError):
    pass


class Guardrails:
    def __init__(self):
        with open(LOCK_FILE) as f:
            self.cfg = json.load(f)
        self.cap = int(os.getenv("MONTHLY_TOKEN_CAP", "1000000"))
        self.alert_pct = int(os.getenv("TOKEN_ALERT_THRESHOLD",
                                       str(self.cfg.get("token_alert_threshold_pct", 80))))
        self.retention_days = int(os.getenv("AUDIT_LOG_RETENTION_DAYS",
                                            str(self.cfg.get("audit_log_retention_days", 30))))
        self.max_context_tokens = int(os.getenv("MAX_CONTEXT_TOKENS", "16384"))
        self._lock = threading.Lock()
        self._alerted = False
        self.usage = self._load_usage()
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # ── immutable config ──
    def verify_lock(self):
        with open(LOCK_FILE, "rb") as f:
            current = hashlib.sha256(f.read()).hexdigest()
        pinned = pathlib.Path(LOCK_SHA_FILE).read_text().strip()
        if current != pinned:
            self.audit("guardrail_tamper_detected", expected=pinned, got=current)
            raise GuardrailTampered("guardrails.lock.json changed since bootstrap — refusing to run")

    # ── audit watchdog ──
    def audit(self, event, **fields):
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **fields}
        path = AUDIT_DIR / f"audit-{time.strftime('%Y-%m-%d')}.jsonl"
        with self._lock:
            with open(path, "a") as f:
                f.write(json.dumps(rec, default=str) + "\n")

    def retention_sweep(self):
        cutoff = time.time() - self.retention_days * 86400
        removed = 0
        for p in AUDIT_DIR.glob("audit-*.jsonl"):
            if p.stat().st_mtime < cutoff:
                p.unlink(missing_ok=True)
                removed += 1
        if removed:
            self.audit("audit_retention_sweep", removed_files=removed)

    # ── forbidden-action filter (strict sandbox) ──
    def check_forbidden(self, text):
        low = (text or "").lower()
        for pattern in self.cfg.get("forbidden_actions", []):
            if pattern.lower() in low:
                self.audit("forbidden_action_blocked", pattern=pattern)
                raise PermissionError(f"forbidden action blocked by sandbox filter: {pattern!r}")

    # ── token budget ──
    def _load_usage(self):
        month = time.strftime("%Y-%m")
        if USAGE_FILE.exists():
            try:
                u = json.loads(USAGE_FILE.read_text())
                if u.get("month") == month:
                    return u
            except (ValueError, OSError):
                pass
        return {"month": month, "tokens": 0}

    def add_tokens(self, n, model="unknown"):
        with self._lock:
            month = time.strftime("%Y-%m")
            if self.usage.get("month") != month:
                self.usage = {"month": month, "tokens": 0}
                self._alerted = False
            self.usage["tokens"] += int(n)
            USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            USAGE_FILE.write_text(json.dumps(self.usage))
            pct = 100.0 * self.usage["tokens"] / max(self.cap, 1)
        if pct >= self.alert_pct and not self._alerted:
            self._alerted = True
            self.audit("token_alert_threshold", pct=round(pct, 1), model=model,
                       tokens=self.usage["tokens"], cap=self.cap)
        if self.usage["tokens"] >= self.cap:
            self.audit("token_cap_exceeded", tokens=self.usage["tokens"], cap=self.cap)
            raise TokenBudgetExceeded(
                f"monthly token cap reached ({self.usage['tokens']}/{self.cap})")

    def spend_pct(self):
        return 100.0 * self.usage["tokens"] / max(self.cap, 1)

    # ── prompt compression / context pruning ──
    def compress(self, text, max_chars=None):
        """Head+tail truncation. ~4 chars/token heuristic against MAX_CONTEXT_TOKENS."""
        limit = max_chars or self.max_context_tokens * 4
        if len(text) <= limit:
            return text
        head, tail = limit * 2 // 3, limit // 3
        self.audit("prompt_compressed", original_chars=len(text), kept_chars=limit)
        return text[:head] + "\n...[pruned by guardrails]...\n" + text[-tail:]
