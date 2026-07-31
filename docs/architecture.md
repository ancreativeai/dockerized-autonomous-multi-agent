# Architecture — System Design

High-level overview of how the OpenClaw stack is designed and structured.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Your Devices (Laptop, Phone, etc.)                             │
│  - Tailscale installed & logged in                              │
│  - Private Tailscale IPs (e.g., 100.104.71.39)                  │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Encrypted Tailscale Tunnels
                 │ (over public internet, but encrypted)
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│  Tailscale Coordination Server (Tailscale, Inc.)                │
│  - Maintains device identity mappings                           │
│  - Routes connections through encrypted tunnels               │
│  - Tailnet: tail2bffa6.ts.net                                   │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Routes traffic to server
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│  Hetzner Cloud Server (ubuntu-16gb-hel1-2)                      │
│  Tailscale IP: 100.107.239.95                                   │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Docker Compose Stack                                     │  │
│  │                                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐ │  │
│  │  │  OpenClaw Gateway (Port :18789, HTTPS via TS Serve)│ │  │
│  │  │  - Control UI for agents                           │ │  │
│  │  │  - Device pairing & authentication                 │ │  │
│  │  └─────────────────────────────────────────────────────┘ │  │
│  │                                                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │  │
│  │  │ Hermes LLM   │  │ Mission      │  │ ClawLibrary  │    │  │
│  │  │ (Port :8081) │  │ Control      │  │ (Port :5173) │    │  │
│  │  │              │  │ (Port :4000) │  │              │    │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │  │
│  │                                                           │  │
│  │  ┌──────────────┐  ┌──────────────────────────────────┐  │  │
│  │  │ Knowledge    │  │ Monitoring Stack                 │  │  │
│  │  │ Graph        │  │ - Grafana (Port :3000)          │  │  │
│  │  │ (Port :8090) │  │ - Prometheus (Port :9090)       │  │  │
│  │  └──────────────┘  └──────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  │
│  │  │  Storage & Configuration                            │ │  │
│  │  │  - Docker volumes (agent data, metrics, logs)       │ │  │
│  │  │  - .env file (API keys, tokens)                     │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Tailscale Network Layer

**Purpose:** Provide secure, stable connectivity across the internet without exposing services publicly.

**How it works:**
- Each device has a cryptographic identity (key pair)
- Tailscale assigns stable virtual IPs (100.x.x.x)
- Traffic flows through encrypted tunnels, even over public WiFi
- Coordination server manages device registration & routing
- ACL (Access Control List) defines who can reach what

**Why we use it:**
- No public IP addresses exposed
- Works from anywhere (office, home, coffee shop)
- Automatic encryption (zero-trust security)
- Stable addresses (never need to update IPs)
- No VPN setup complexity

### 2. OpenClaw Gateway

**Purpose:** Autonomous multi-agent framework with control UI.

**Components:**
- **Control UI** — Web interface to monitor and manage agents
- **Device Pairing** — Security layer (proves it's really you accessing the UI)
- **HTTPS via Tailscale Serve** — Terminates TLS on the gateway, allows HTTPS-only access

**Why HTTPS only:** The control UI requires "device identity" verification — HTTP is not secure enough for this.

### 3. Agent Runtime (Hermes + Mission Control)

**Purpose:** Execute multi-agent workflows.

**Components:**
- **Hermes LLM** (Port :8081) — LLM interface for agents
- **Mission Control** (Port :4000) — Orchestrate agent runs and jobs

### 4. User Interfaces

**ClawLibrary (Pixel UI)** (Port :5173)
- Alternative UI for managing OpenClaw missions
- Password-protected

**Knowledge Graph** (Port :8090)
- Visual exploration of agent knowledge
- Generated from agent interactions

**Hermes Chat** (Port :8081)
- Real-time chat with agents

### 5. Monitoring & Observability

**Grafana** (Port :3000)
- Dashboards showing agent performance, resource usage, alerts
- Queries data from Prometheus

**Prometheus** (Port :9090)
- Time-series metrics database
- Collects metrics from all services
- Retention: configurable (default ~15 days)

## Data Flow

### User accesses OpenClaw UI

```
1. User's browser → Tailscale network
2. Tailscale routes to server (100.107.239.95)
3. Tailscale Serve terminates HTTPS on gateway
4. Gateway checks device pairing
5. If paired, serves control UI
6. UI can trigger agent runs → Mission Control
7. Agents execute → Hermes LLM
8. Results stored in volumes
9. Metrics sent to Prometheus
10. Grafana visualizes metrics
```

### Agent Execution

```
User clicks "Run Agent"
    ↓
Mission Control receives request
    ↓
Creates agent task with parameters
    ↓
Agents fetch LLM calls through Hermes
    ↓
Hermes queries external APIs (OpenRouter, Anthropic)
    ↓
Agent stores results in volume
    ↓
Metrics logged to Prometheus
    ↓
Knowledge Graph viewer indexes results
```

## Deployment & Scaling

### Current Setup (Single Server)

- One Hetzner CX43 (16GB RAM, 4 CPU cores)
- All services in one Docker Compose stack
- Suitable for: Development, testing, small workloads

### Future Scaling (If Needed)

- Separate Prometheus/Grafana onto dedicated monitoring server
- Move database to managed PostgreSQL
- Use container orchestration (Kubernetes) for horizontal scaling
- Load balancer for multiple OpenClaw instances

## Security Model

### Tailscale Security

**No public internet exposure:**
- Services are NOT open to the public internet
- Only accessible via Tailscale private network
- Device identity is cryptographically verified

**ACL (Access Control List):**
```
{
  "ACLs": [
    {"Action": "accept", "Principal": "group:developers", "Resources": ["*"]}
  ]
}
```
Controls which devices can reach which services.

### OpenClaw Security

**Device Pairing:**
- Each browser/device must be approved once
- Proves the user requesting access is authorized
- Uses Tailscale device identity as proof

**HTTPS Requirement:**
- `tailscale serve --https=443` terminates TLS
- Prevents man-in-the-middle attacks
- Uses Tailscale's certificate authority

### API Keys

- Stored in `.env` on the server (not in git)
- Injected into container at runtime
- Used for:
  - OpenRouter LLM API
  - Anthropic Claude API
  - LangSmith tracing

## Service Communication

All services run on the same server, so they communicate via localhost:

```
OpenClaw Gateway → http://hermes-llm:8081 (Docker DNS)
Mission Control  → http://openclaw-stack:18789 (internal API)
Prometheus       ← metrics from all services
```

No external network calls except to external LLM APIs.

## Restart & High Availability

### Current Model

`restart: unless-stopped` in docker-compose.yml means:
- Services automatically restart if they crash
- Services come back up after server reboot
- Manual intervention required for configuration changes

### Data Persistence

- Agent state stored in Docker volumes
- Volumes survive container restarts
- Backup volumes regularly

### Downtime

Single points of failure:
- Server hardware failure (rare on Hetzner)
- Internet connection to Hetzner data center
- Disk full (causes all services to stop)

Mitigation:
- Regular backups to external storage
- Monitor disk usage
- Set up alerts in Grafana

## Performance Characteristics

### Expected Throughput

- Single server can handle: ~10-50 concurrent agents (depends on LLM API rate limits)
- Request latency: 50-200ms (within private network)
- Bottleneck: External LLM API calls (OpenRouter, Anthropic)

### Resource Usage

- Idle (no agents running): ~2-3 GB RAM, <5% CPU
- Peak (multiple agents): ~12-14 GB RAM, 80-100% CPU
- Restart recovery: ~30 seconds for all services

---

**Next:** [Agent Stack Guide](agent-stack-guide.md) for operational details, or [Quick Start](quick-start.md) to get using it.
