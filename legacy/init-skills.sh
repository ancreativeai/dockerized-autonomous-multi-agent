#!/bin/bash
# OpenClaw binary is installed globally via NPM at /usr/local/bin
OC="/usr/local/bin/openclaw"

echo "=== Starting Full OpenClaw Skill Installation & Lock Configuration ==="

# 1. Core Safety Guardrails (Watchdog + Token Monitor)
$OC skill install toolifyai/openclaw-skills/openclaw-claw-guard-2989
$OC skill install davida-ps/openclaw-audit-watchdog
$OC skill install openclaw/token-monitor
$OC token monitor set alert-threshold 80 --lock
$OC audit watchdog enable --scope all --lock
$OC claw-guard sandbox strict-mode enable --lock

# 2. 5 Self-Evolution Core Skills
$OC skill install ivangdavila/self-evolving-agent
$OC skill install spclaudehome/skill-vetter
$OC skill install OthmanAdi/planning-with-files
$OC skill install chindden/skill-creator
$OC skill install JimLiuxinghai/find-skills

# 3. Token Cost Reduction Memory & Multi-Agent Context Layer
$OC skill install thedotmack/claude-mem
$OC skill install volcengine/OpenViking
$OC claude-mem config set compression-level high auto-save true --lock
$OC openviking config set layered-context true agent-sharing true --lock

# 4. Obsidian knowledge base mount
$OC skill install lobehub/openclaw-skills-obsidian-direct
$OC obsidian config set vault-path /app/obsidian-vault --lock

echo "=== All Skills Installed & Security/Low-Token Rules Locked ==="
echo "=== Launch Shared Peter Steinberg Persistent Agent Loop ==="
# Start background master agent loop
$OC loop start --persistent &
sleep 3

# Launch valid gateways with full global binary path
/usr/local/bin/claude-code gateway start --port 8081 --workspace /app/workspaces/claude &
/usr/local/bin/openai-agent gateway start --port 8082 --workspace /app/workspaces/chatgpt &

# Remove invalid notebook-lm line entirely
# notebook-lm start --port 8083 --workspace /app/workspaces/notebook-lm &

# Keep container running forever
tail -f /dev/null
