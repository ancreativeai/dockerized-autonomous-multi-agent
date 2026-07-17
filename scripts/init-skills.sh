#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# OpenClaw stack bootstrap (container entrypoint).
#  1. Installs + hard-locks the guardrail/routing config (read-only + SHA pin)
#  2. Best-effort OpenClaw skill installation (non-fatal if a skill is missing)
#  3. Launches the OpenClaw gateway
#  4. Starts the persistent autonomous multi-agent loop
#     (LangGraph state engine + GraphRAG vault indexer + guardrails + metrics)
# Deliberately NOT `set -e`: optional steps degrade gracefully, the agent
# service is the mandatory core and runs via exec at the end.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
log() { echo "[init-skills] $*"; }

AUDIT_DIR=/app/audit-logs
mkdir -p "$AUDIT_DIR" /data/memory /data/state /data/graph \
         /app/workspaces/inbox /app/workspaces/done \
         /app/workspaces/openclaw/reports /app/workspaces/openclaw/skills \
         /root/.openclaw

# ── 1. Guardrail + hybrid-routing config: install and hard-lock ──
if [ -f /app/config/openclaw.json ] && [ ! -f /root/.openclaw/openclaw.json ]; then
  cp /app/config/openclaw.json /root/.openclaw/openclaw.json
  log "installed locked OpenClaw config (Claude=planner, Hermes=workers)"
fi
chmod 444 /root/.openclaw/openclaw.json 2>/dev/null || true

# Pin the guardrail ruleset: SHA recorded at bootstrap; the agent service
# re-verifies it on every loop cycle and refuses to run if it was tampered with.
sha256sum /app/config/guardrails.lock.json | awk '{print $1}' > /data/state/guardrails.sha256
log "guardrails locked: threshold=${TOKEN_ALERT_THRESHOLD:-80}% retention=${AUDIT_LOG_RETENTION_DAYS:-30}d strict-sandbox=on"

# ── 2. OpenClaw skills (best-effort; the CLI surface varies by release) ──
OC="$(command -v openclaw || true)"
if [ -n "$OC" ]; then
  log "openclaw CLI: $($OC --version 2>/dev/null | head -1 || echo 'version unknown')"
  for skill in obsidian coding-agent skill-creator; do
    if "$OC" skills install "$skill" >>"$AUDIT_DIR/skills-install.log" 2>&1; then
      log "skill installed: $skill"
    else
      log "skill '$skill' unavailable in this release — skipped (see skills-install.log)"
    fi
  done

  # ── 3. OpenClaw gateway (background) ──
  ( "$OC" gateway --port 18789 >>"$AUDIT_DIR/openclaw-gateway.log" 2>&1 & ) \
    && log "openclaw gateway starting on :18789 (log: audit-logs/openclaw-gateway.log)"
else
  log "WARNING: openclaw CLI not found — continuing with agent-service only"
fi

# ── 4. Persistent autonomous multi-agent loop ──
log "starting agent-service: planner=Claude (${CLAUDE_MODEL:-claude-opus-4-8}), workers=Hermes x${WORKER_AGENT_COUNT:-2}"
exec python /app/agents/main.py
