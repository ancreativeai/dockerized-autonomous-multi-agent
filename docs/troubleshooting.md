# Troubleshooting Guide

## "I can't reach the services"

### Checklist

1. **Is Tailscale running?**
   ```bash
   tailscale status
   ```
   Should show your device and the tailnet (`tail2bffa6.ts.net`).

2. **Are you logged into the right tailnet?**
   ```bash
   tailscale status | grep -i tailnet
   ```
   Should show: `tail2bffa6.ts.net`

3. **Can you ping the server?**
   ```bash
   ping 100.107.239.95
   ```
   If ping fails → the server's Tailscale daemon may be down.

4. **Is the URL correct?**
   - OpenClaw: `https://ubuntu-16gb-hel1-2.tail2bffa6.ts.net` (HTTPS, not HTTP)
   - Others: `http://100.107.239.95:PORT`

### Fixes

**Restart Tailscale on your device:**
```bash
# macOS:
sudo launchctl stop com.tailscale.ipn.macos
sudo launchctl start com.tailscale.ipn.macos

# Linux:
sudo systemctl restart tailscaled

# Windows:
# Restart Tailscale from system tray
```

**If server is unreachable, restart Tailscale on the server:**
```bash
ssh root@100.107.239.95  # might not work if Tailscale is down
# Or use a different device on the tailnet:
ssh -J your-other-device@100.x.x.x root@100.107.239.95

# On the server:
sudo systemctl restart tailscaled
```

---

## "OpenClaw returns HTTPS certificate error"

### Why
This is expected on first visit. Tailscale Serve is using a self-signed certificate for HTTPS.

### Fix
Click through the warning:
- Chrome/Firefox: Click "Advanced" → "Proceed anyway"
- Safari: Click "Show Details" → "Visit this website"
- The certificate is valid; it's just not from a public CA

(This only happens once per browser — it then trusts the cert.)

---

## "Device pairing required" (OpenClaw)

### What This Means
New browser/device accessing OpenClaw for the first time needs to be approved.

### Fix

1. OpenClaw shows:
   ```
   Device pairing required
   Request ID: abc123def456...
   ```

2. SSH to server:
   ```bash
   ssh root@100.107.239.95
   ```

3. Approve the device:
   ```bash
   docker exec openclaw-stack openclaw devices list      # See requests
   docker exec openclaw-stack openclaw devices approve abc123def456
   ```

4. Go back to browser, click **Connect**

That device is now permanently paired — you won't need to do this again.

---

## "Services are running but pages show errors"

### Step 1: Check service status

```bash
ssh root@100.107.239.95
cd /root/dockerized-autonomous-multi-agent
docker compose ps
```

All should show `Up` with green status.

### Step 2: Check logs

```bash
docker logs --tail 100 openclaw-stack | grep -i error
```

Look for:
- `API key` errors → Check `.env` has correct keys
- `Connection refused` → Services can't reach each other
- `Port already in use` → Another service using the port

### Step 3: Restart one service

```bash
docker compose restart openclaw-stack
```

Wait 10 seconds and try the URL again.

### Step 4: Full restart

```bash
docker compose down
docker compose up -d
docker compose ps
```

Wait 30 seconds for services to become healthy.

---

## "Service is up but won't respond"

### Check if service is healthy

```bash
docker compose ps openclaw-stack    # See "Up (healthy)" or "Up (unhealthy)"
```

### Check service logs for startup errors

```bash
docker logs openclaw-stack    # First 50 lines
docker logs --tail 200 openclaw-stack | tail -50  # Last 50 lines
```

### Common Issues

**API Keys Missing:**
```bash
cat .env | grep -i key
# If empty or missing, add them:
# OPENROUTER_API_KEY=...
# ANTHROPIC_API_KEY=...
```

Then restart:
```bash
docker compose restart openclaw-stack
```

**Database/Volume Corrupted:**
```bash
docker compose down -v    # Remove volumes
docker compose up -d      # Restart (fresh database)
```

**Port Conflict:**
```bash
# Check if another process is using port 18789 (OpenClaw):
netstat -tlnp | grep 18789
# Kill if needed:
kill -9 <PID>
```

---

## "I can SSH in but docker commands don't work"

### Check Docker Daemon

```bash
docker ps    # Should list running containers
```

If this fails:
```bash
sudo systemctl restart docker
```

### Check Docker Compose Version

```bash
docker compose version    # Should show version >= 2.0
```

If missing:
```bash
sudo apt-get install docker-compose
```

---

## "Disk is full or out of space"

### Check disk usage

```bash
df -h    # Show all disks
```

### Clean up Docker

```bash
docker system prune -a    # Remove unused images/containers
```

Be careful: this removes ALL unused images.

### Check specific volumes

```bash
docker volume ls
du -sh /var/lib/docker/volumes/*    # See which volumes are biggest
```

### Clean old logs

```bash
cd /root/dockerized-autonomous-multi-agent
docker compose logs --tail 0 openclaw-stack > /dev/null  # Clear log buffer
```

---

## "Tailscale Serve (HTTPS) is broken"

### Symptoms
- OpenClaw returns connection refused on HTTPS
- `https://ubuntu-16gb-hel1-2.tail2bffa6.ts.net` doesn't work

### Check status

```bash
tailscale serve status
```

### Re-enable it

```bash
tailscale serve --bg --https=443 http://127.0.0.1:18789
tailscale serve status    # Confirm
```

### Verify it's working

```bash
curl -k https://ubuntu-16gb-hel1-2.tail2bffa6.ts.net/healthz
# Should return: {"ok":true,"status":"live"}
```

---

## "Server won't come back up after reboot"

### SSH in

```bash
ssh root@100.107.239.95
```

### Check if Tailscale is running

```bash
tailscale status
```

If not:
```bash
sudo systemctl start tailscaled
```

### Check if Docker is running

```bash
docker ps    # Should list containers
```

If not:
```bash
sudo systemctl start docker
```

### Restart the stack

```bash
cd /root/dockerized-autonomous-multi-agent
docker compose up -d
docker compose ps    # Verify
```

Services should auto-start due to `restart: unless-stopped`.

---

## "Something is broken but I'm not sure what"

### Full diagnostic

```bash
ssh root@100.107.239.95

# Check system health
df -h                           # Disk space
free -h                         # Memory
top -bn1 | head -20             # CPU usage

# Check Tailscale
tailscale status

# Check Docker
docker ps
docker stats --no-stream        # Resource usage per container

# Check services
cd /root/dockerized-autonomous-multi-agent
docker compose ps
docker compose logs --tail 50

# Check network
curl -v http://127.0.0.1:3000/api/health    # Grafana
curl -v http://127.0.0.1:18789/healthz      # OpenClaw

# Check ports listening
netstat -tlnp | grep LISTEN
```

### Capture full logs for debugging

```bash
docker compose logs > /tmp/full-logs.txt
# Send to someone for analysis
```

---

## "I made a mistake and want to reset everything"

### Full reset (WARNING: loses all agent data/history)

```bash
cd /root/dockerized-autonomous-multi-agent

# Stop and remove everything
docker compose down -v

# (optional) Remove old images
docker image prune -a

# Start fresh
docker compose up -d

# Verify
docker compose ps
```

---

## Still stuck?

### Collect debugging info

```bash
# From your device:
tailscale status > /tmp/device-debug.txt

# From the server:
ssh root@100.107.239.95
cd /root/dockerized-autonomous-multi-agent
docker compose logs > /tmp/server-debug.txt
docker compose ps > /tmp/server-status.txt
df -h > /tmp/disk-usage.txt
```

### Share diagnostics

Include:
- Device Tailscale status
- Server logs (last 100 lines)
- Service status (`docker compose ps`)
- Error messages from browser console (F12)

---

**Still need help?** Check [Agent Stack Guide](agent-stack-guide.md#troubleshooting) or [Architecture](architecture.md) to understand how things connect.
