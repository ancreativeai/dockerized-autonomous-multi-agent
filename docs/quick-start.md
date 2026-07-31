# Quick Start — Get Running in 5 Minutes

## 1. Install Tailscale (if you haven't already)

Go to [tailscale.com/download](https://tailscale.com/download) and install for your OS.

## 2. Log In to the Tailnet

Open Tailscale and log in with your account. Make sure you see the tailnet name **`tail2bffa6.ts.net`** — that's the shared network.

## 3. Access the Services

All of these work once Tailscale is running:

| Service | URL |
|---|---|
| **OpenClaw Control** | https://ubuntu-16gb-hel1-2.tail2bffa6.ts.net |
| Grafana (dashboards) | http://100.107.239.95:3000 |
| Prometheus (metrics) | http://100.107.239.95:9090 |
| Knowledge Graph | http://100.107.239.95:8090 |
| Hermes Chat | http://100.107.239.95:8081 |
| Mission Control | http://100.107.239.95:4000 |
| ClawLibrary (Pixel UI) | http://100.107.239.95:5173 |

## 4. Device Pairing (First Time Only)

When you open **OpenClaw** for the first time, it will ask:
> "Device pairing required — Request ID: abc123def456"

**Approve it on the server:**

```bash
ssh root@100.107.239.95
docker exec openclaw-stack openclaw devices list    # Find your request ID
docker exec openclaw-stack openclaw devices approve abc123def456
```

Then click **Connect** in your browser.

That's it! Your device is now paired and you won't need to do this again.

## 5. SSH into the Server (Optional)

Once Tailscale is logged in, SSH works without a password:

```bash
ssh root@100.107.239.95
# or:
ssh root@ubuntu-16gb-hel1-2.tail2bffa6.ts.net
```

You may see a browser check the first time — approve it.

## Common Credentials

Secrets are not stored in this repo. Retrieve them from the server over Tailscale:

**ClawLibrary (Pixel UI) login:**
```bash
ssh root@100.107.239.95 'cat /root/dockerized-autonomous-multi-agent/clawlibrary/.access-password'
```

**OpenClaw Gateway token** (if prompted):
```bash
ssh root@100.107.239.95 'grep OPENCLAW_GATEWAY_TOKEN /root/dockerized-autonomous-multi-agent/.env'
```

## Troubleshooting

**"Can't reach the URL"**
- Make sure Tailscale is running (`tailscale status` in terminal)
- Make sure you're logged into the tailnet
- Check internet connection

**"Connection refused"**
- A service might be down
- SSH in and run: `cd /root/dockerized-autonomous-multi-agent && docker compose ps`
- If any show "Exit" or "Down", restart: `docker compose up -d`

**"HTTPS certificate error"**
- This is normal on first visit to a Tailscale HTTPS domain
- Accept/ignore the warning (it's using Tailscale's cert)

---

**Next:** See [Agent Stack Guide](agent-stack-guide.md) for full operations, or [Networking Guide](networking-guide.md) to understand how it all works.
