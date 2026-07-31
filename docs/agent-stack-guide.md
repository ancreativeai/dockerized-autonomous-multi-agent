# Agent Stack Guide — OpenClaw Operations

Complete reference for running, monitoring, and troubleshooting the OpenClaw multi-agent stack.

## Server Details

**Hardware:**
- Provider: Hetzner Cloud
- Server: CX43 `ubuntu-16gb-hel1-2`
- Region: Helsinki (hel1)
- RAM: 16 GB
- OS: Ubuntu 26.04

**Network Access:**
- Tailscale IP: `100.107.239.95`
- MagicDNS: `ubuntu-16gb-hel1-2.tail2bffa6.ts.net`
- Access: Via Tailscale only (private tailnet, not public internet)

**Deployment:**
- Location on server: `/root/dockerized-autonomous-multi-agent`
- Restart policy: `restart: unless-stopped` (automatically comes back after reboot)

## Service URLs & Access

### Overview Table

| Service | URL | Purpose | Notes |
|---|---|---|---|
| **OpenClaw Control** | https://ubuntu-16gb-hel1-2.tail2bffa6.ts.net | Web UI for agents | Must use HTTPS; requires device pairing |
| Grafana | http://100.107.239.95:3000 | Dashboards & alerts | No auth (internal tailnet) |
| Prometheus | http://100.107.239.95:9090 | Metrics storage | Query tool for time-series data |
| Knowledge Graph | http://100.107.239.95:8090 | Interactive reports | Visualization of agent knowledge |
| Hermes Chat | http://100.107.239.95:8081 | Chat interface | Real-time communication |
| Mission Control | http://100.107.239.95:4000 | Agent orchestration | Manage runs & jobs |
| ClawLibrary (Pixel) | http://100.107.239.95:5173 | Pixel UI | Password-protected |

### Credentials & Tokens

**No secrets are committed to this repo.** They live only on the server and are fetched
over Tailscale when needed.

**ClawLibrary (Pixel UI) password:**
```bash
ssh root@100.107.239.95 'cat /root/dockerized-autonomous-multi-agent/clawlibrary/.access-password'
```

**OpenClaw Gateway token** (if login screen asks):
```bash
ssh root@100.107.239.95 'grep OPENCLAW_GATEWAY_TOKEN /root/dockerized-autonomous-multi-agent/.env'
```

**Environment variables** on server (stored in `.env`):
- `OPENROUTER_API_KEY` — API key for OpenRouter
- `ANTHROPIC_API_KEY` — Anthropic API credentials
- `LANGSMITH_API_KEY` — LangSmith tracing
- `OPENCLAW_GATEWAY_TOKEN` — Gateway authentication

## SSH Access

### Prerequisites
- Tailscale installed and logged in
- Device on the tailnet (`tail2bffa6.ts.net`)

### Connect to Server

No password or SSH key needed — Tailscale authentication is automatic:

```bash
ssh root@100.107.239.95
```

Or using MagicDNS:
```bash
ssh root@ubuntu-16gb-hel1-2.tail2bffa6.ts.net
```

**First-time only:** You may see a browser approval prompt. Click approve in the browser.

## Docker Commands

### Check Service Status

```bash
ssh root@100.107.239.95
cd /root/dockerized-autonomous-multi-agent
docker compose ps
```

Output example:
```
NAME                    STATUS
openclaw-stack          Up 2 days (healthy)
hermes-llm              Up 2 days (healthy)
grafana                 Up 2 days
prometheus-monitor      Up 2 days
graph-viewer            Up 2 days
```

All should show `Up` with status healthy.

### Start / Stop Services

**Start everything:**
```bash
docker compose up -d
```

**Stop everything:**
```bash
docker compose down
```

**Restart a specific service:**
```bash
docker compose restart openclaw-stack
# or: hermes-llm, grafana, prometheus-monitor, graph-viewer
```

### View Logs

**Last 50 lines of a service:**
```bash
docker logs --tail 50 openclaw-stack
```

**Follow logs in real-time:**
```bash
docker logs -f openclaw-stack
```

**Available services for logs:**
- `openclaw-stack` — Main agent framework
- `hermes-llm` — LLM interface
- `grafana` — Dashboards
- `prometheus-monitor` — Metrics collection
- `graph-viewer` — Knowledge graph

### Restart Everything (If Something Breaks)

```bash
cd /root/dockerized-autonomous-multi-agent
docker compose down
docker compose up -d
docker compose ps    # Confirm all are "Up"
```

## Health Checks

### Quick Health Check (from any tailnet device)

```bash
# Check each service by port
for p in 3000 9090 8090 8081 4000; do 
  echo -n "$p -> "; 
  curl -s -o /dev/null -w "%{http_code}\n" http://100.107.239.95:$p
done

# Check OpenClaw HTTPS endpoint
curl -s https://ubuntu-16gb-hel1-2.tail2bffa6.ts.net/healthz
```

Expected output: All `200` (and OpenClaw shows `{"ok":true,"status":"live"}`).

### From Server

```bash
docker compose ps    # See all service states
```

## OpenClaw-Specific Gotchas

### Issue: "HTTPS Certificate Error" or "Connection Refused"

**Cause:** The Tailscale HTTPS Serve endpoint (which exposes OpenClaw) may have stopped after a reboot.

**Fix:** Re-enable it on the server

```bash
ssh root@100.107.239.95
tailscale serve --bg --https=443 http://127.0.0.1:18789
tailscale serve status    # Confirm it's running
```

### Issue: "Device Pairing Required"

**Cause:** First time accessing OpenClaw from a new browser or device.

**How it works:** Each device needs one-time pairing for device identity verification.

**Fix:**

1. OpenClaw shows: `Device pairing required — Request ID: abc123...`

2. SSH to server and approve:
```bash
ssh root@100.107.239.95
docker exec openclaw-stack openclaw devices list        # See pending requests
docker exec openclaw-stack openclaw devices approve abc123def456
```

3. Go back to browser and click **Connect** again

4. You're in! (Won't need to pair this device again)

### Issue: Can't Access OpenClaw Over HTTP

**Cause:** OpenClaw requires HTTPS for security (device identity verification).

**Wrong:** `http://ubuntu-16gb-hel1-2.tail2bffa6.ts.net` ❌  
**Correct:** `https://ubuntu-16gb-hel1-2.tail2bffa6.ts.net` ✅

**Error code if you try HTTP:** `1008 "control ui requires device identity"`

## Monitoring & Alerts

### Grafana Dashboards

Open: http://100.107.239.95:3000

Pre-built dashboards for:
- Agent execution history
- Resource usage (CPU, memory)
- Request latency
- Error rates

### Prometheus Queries

Open: http://100.107.239.95:9090

Query examples:
```
# OpenClaw uptime
up{job="openclaw"}

# Request rate (req/sec)
rate(requests_total[5m])

# Memory usage
process_resident_memory_bytes
```

## Troubleshooting

### "Services won't start" or "docker compose ps shows Exit"

1. Check logs:
```bash
docker logs openclaw-stack
```

2. Look for error messages (usually API key issues, port conflicts, or disk space)

3. Common fixes:
   - Verify `.env` has correct API keys
   - Ensure no other services are using required ports
   - Check disk space: `df -h`

### "Cannot connect to Docker daemon"

Make sure you're on the server:
```bash
ssh root@100.107.239.95
# Then run docker commands
```

Docker only works when you SSH in.

### "Tailscale IP doesn't reach server"

1. Check Tailscale is running:
```bash
tailscale status
```

2. Confirm you're on the right tailnet:
```
tailnet: tail2bffa6.ts.net
```

3. Ping the server:
```bash
ping 100.107.239.95
```

If ping fails, the server's Tailscale daemon may have stopped:
```bash
ssh root@100.107.239.95
sudo systemctl restart tailscaled
```

### "Services are up but pages show error"

1. Check service logs:
```bash
docker logs --tail 100 openclaw-stack
```

2. Check if services can reach each other:
```bash
# From server:
docker exec openclaw-stack curl http://hermes-llm:8081/health
```

3. Check API keys in `.env`:
```bash
cat /root/dockerized-autonomous-multi-agent/.env | grep -i key
```

If keys are missing or wrong, update `.env` and restart:
```bash
docker compose restart openclaw-stack
```

## Maintenance

### Regular Tasks

**Weekly:** Check logs for errors
```bash
docker logs --tail 200 openclaw-stack | grep -i error
```

**Monthly:** Prune unused Docker images/volumes
```bash
docker system prune -a    # Warning: removes ALL unused images
```

**After reboot:** Verify services came back up
```bash
docker compose ps    # All should show "Up"
```

### Backups

Database/state files are in:
- `/root/dockerized-autonomous-multi-agent/openclaw-data` (agent data)
- Docker volumes (managed by compose)

Backup strategy (recommend weekly):
```bash
ssh root@100.107.239.95
tar -czf openclaw-data-backup-$(date +%Y%m%d).tar.gz /root/dockerized-autonomous-multi-agent/openclaw-data
```

## If Something Really Breaks

**Full stack reset** (CAUTION: loses all agent state/history):

```bash
ssh root@100.107.239.95
cd /root/dockerized-autonomous-multi-agent

# Stop everything
docker compose down -v    # -v removes ALL volumes

# Start fresh
docker compose up -d

# Confirm
docker compose ps
```

## Updating the Stack

To pull latest code and restart:

```bash
ssh root@100.107.239.95
cd /root/dockerized-autonomous-multi-agent

git pull origin main      # Get latest code
docker compose build      # Rebuild images
docker compose up -d      # Start with new images

docker compose ps         # Confirm
```

---

**Questions?** See [Troubleshooting](troubleshooting.md) or check service logs with `docker logs`.
