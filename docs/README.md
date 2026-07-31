# OpenClaw Multi-Agent Stack Documentation

Complete guide to understanding and operating the OpenClaw autonomous multi-agent AI stack deployed on Hetzner Cloud with Tailscale networking.

## Quick Links

- **[Quick Start Guide](quick-start.md)** — Get running in 5 minutes
- **[Networking Guide](networking-guide.md)** — How Tailscale works & why it's stable
- **[Agent Stack Guide](agent-stack-guide.md)** — Services, URLs, operations, troubleshooting
- **[Architecture Guide](architecture.md)** — System design and components
- **[Troubleshooting](troubleshooting.md)** — Common problems and fixes

## What Is This?

This documentation covers:

1. **OpenClaw** — Dockerized autonomous multi-agent AI framework running on Hetzner CX43 (100.107.239.95)
2. **Tailscale** — Zero-trust private network connecting your devices to the stack
3. **Services** — Grafana, Prometheus, Knowledge Graph, Hermes Chat, Mission Control, ClawLibrary
4. **Operations** — How to SSH, restart services, monitor health, debug issues

## Key Concepts

### Public IP vs. Tailscale IP

| Property | Public IP | Tailscale IP |
|---|---|---|
| **Changes when** | You join different WiFi | Never (device identity) |
| **Example** | 1.2.3.4, 5.6.7.8 | 100.107.239.95 (always) |
| **Who assigns it** | ISP / WiFi provider | Your Tailscale account |
| **Used for** | Internet browsing | Accessing your private stack |

**Bottom line:** Tailscale gives you a stable, encrypted way to reach your services from anywhere — coffee shop, home, travel. Your Tailscale IP never changes, so you can always do `ssh root@100.107.239.95` or visit `https://ubuntu-16gb-hel1-2.tail2bffa6.ts.net`.

### Why Tailscale Works Without Public IPs

Tailscale recognizes devices by **cryptographic identity** (keys), not by IP address. When you move to McDonald's WiFi:
- Your public IP changes (ISP assigns a new one)
- Your Tailscale IP stays the same (tied to your device key, not the network)
- A central coordination server maps your device key → current public IP
- Peers connect directly using encrypted tunnels

See [Networking Guide](networking-guide.md) for the full explanation.

## Prerequisites

To use any part of this stack:

1. **Tailscale installed** on your device (laptop, phone, etc.)
2. **Tailscale logged in** to the shared tailnet (`tail2bffa6.ts.net`)
3. **Device pairing approved** (one-time, then you're in)

Everything here is on the private tailnet — nothing is exposed to the public internet.

## Common Tasks

### Access the OpenClaw Control UI
```
https://ubuntu-16gb-hel1-2.tail2bffa6.ts.net
```
First browser/device needs pairing approval (see [Quick Start](quick-start.md#device-pairing)).

### SSH into the Server
```bash
ssh root@100.107.239.95
# or:
ssh root@ubuntu-16gb-hel1-2.tail2bffa6.ts.net
```

### Check Service Status
```bash
# From server:
cd /root/dockerized-autonomous-multi-agent
docker compose ps
```

### View Service URLs
See [Agent Stack Guide](agent-stack-guide.md#service-urls).

## GitHub Readme
This README + `/docs` folder is ready to commit to GitHub. Markdown renders directly.

### GitHub Pages
1. Enable in repo settings: **Settings → Pages → Build from main branch → /docs folder**
2. Adds automatic hosting at `your-username.github.io/repo-name`

### GitHub Wiki
Create pages in the Wiki tab for:
- Deployment runbook (who, when, where)
- Architecture decisions (why we chose Tailscale, Docker, etc.)
- Team access process (how new people get added)


## Index of All Docs

| Doc | Purpose |
|---|---|
| [Quick Start](quick-start.md) | Get running ASAP |
| [Networking Guide](networking-guide.md) | Understand Tailscale & IP addresses |
| [Agent Stack Guide](agent-stack-guide.md) | Services, operations, troubleshooting |
| [Architecture](architecture.md) | System design & components |
| [Troubleshooting](troubleshooting.md) | Common issues & fixes |

## Current Stack Status

**Server:** Hetzner CX43 `ubuntu-16gb-hel1-2`
- **Tailscale IP:** 100.107.239.95
- **MagicDNS:** ubuntu-16gb-hel1-2.tail2bffa6.ts.net
- **Status:** Running with `restart: unless-stopped` (comes back on reboot)

**Services Running:**
- OpenClaw Gateway (HTTPS only)
- Hermes Chat & LLM
- Grafana (monitoring)
- Prometheus (metrics)
- Knowledge Graph Viewer
- Mission Control

See [Agent Stack Guide](agent-stack-guide.md) for full URLs and access details.

---

**Last updated:** 2026-07-31  
**Questions or problems?** Check [Troubleshooting](troubleshooting.md) or the [Agent Stack Guide](agent-stack-guide.md#if-something-breaks).
