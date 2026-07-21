# Dockerized-autonomous-multi-agent

A fully Dockerized, self-contained **autonomous multi-agent AI stack** that runs on modest CPU-only hardware. Built and validated on an HP EliteBook 830 G6 (Intel i5-8365U, 16 GB RAM, no GPU) running Ubuntu/Linux Mint.

One `docker compose up -d` gives you an orchestrated agent system with a paid frontier-model planner, free local worker LLMs, a knowledge graph built from your Obsidian vault, persistent memory, hard-locked safety guardrails, and full metrics — with **zero host dependencies beyond Docker**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ agent-net (private Docker bridge network)                       │
│                                                                 │
│  ┌────────────────────────┐      ┌──────────────────────────┐   │
│  │ openclaw-stack         │      │ hermes-llm               │   │
│  │                        │      │                          │   │
│  │ OpenClaw gateway :18789│      │ llama.cpp server :8080   │   │
│  │ LangGraph agent engine │─────▶│ Hermes 3 Llama 3.1 8B    │   │
│  │ GraphRAG vault indexer │      │ (GGUF, auto-quantized    │   │
│  │ Guardrails + audit     │      │  by host RAM)            │   │
│  │ Metrics :9091          │      │                          │   │
│  └───────────┬────────────┘      └────────────┬─────────────┘   │
│              │         ┌──────────────────┐   │                 │
│              └────────▶│ prometheus :9090 │◀──┘                 │
│                        └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
         │                        │
   Anthropic API           ./obsidian-vault  ./workspaces
  (planner: Claude)        (shared knowledge base, agent I/O)
```

**Hybrid LLM routing, locked at bootstrap:** the gateway defaults to a **zero-cost model chain** — Nemotron 3 Super 120B (`:free` via OpenRouter) → Llama 3.3 70B (`:free`) → local Hermes 8B — so nothing spends API credit automatically. Paid frontier models (Claude via `ANTHROPIC_API_KEY`, or any OpenRouter model) stay available as an explicit per-session choice. The Python agent service uses Claude for planning when a key is present and free/local models otherwise; workers always run local Hermes.

**The agent loop:** drop a goal file into `workspaces/inbox/` → the LangGraph pipeline (`plan → work → report`) decomposes it, executes tasks on a parallel worker pool with GraphRAG-retrieved context, and writes a markdown report to `workspaces/openclaw/reports/` and back into the vault, where it gets re-ingested. When idle, the loop runs Hermes-only vault-maintenance tasks on a timer.

## Quick start

```bash
git clone git@github.com:ancreativeai/dockerized-autonomous-multi-agent.git
cd dockerized-autonomous-multi-agent
cp .env.example .env
# edit .env:
#   OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 24)   (required)
#   OPENROUTER_API_KEY=sk-or-...              (recommended: unlocks free 120B/70B models)
#   ANTHROPIC_API_KEY=sk-ant-...              (optional: Claude planning)
#   LANGSMITH_API_KEY=lsv2_...                (optional: LangGraph run tracing)
docker compose up -d
```

First boot downloads the Hermes GGUF model (~4.9 GB, resumable, cached in `hermes/` thereafter). Then:

| Interface | URL (local) | Port |
|---|---|---|
| OpenClaw gateway UI | http://localhost:18789 (token from `.env`) | 18789 |
| Hermes chat (llama.cpp) | http://localhost:8081 | 8081 |
| Grafana — "Agent Stack Mission Metrics" | http://localhost:3000 (anonymous viewer) | 3000 |
| Knowledge graph (interactive) + reports + vault | http://localhost:8090 | 8090 |
| Prometheus | http://localhost:9090 | 9090 |

> **⚠️ These `localhost` URLs only apply when the stack runs on the same machine as your browser.**
> On a **VPS reached over Tailscale (the recommended production setup)** the host is **not** `localhost` — it is the server's tailnet address, which is **different for every server and changes if you replace it.** Replace `localhost` with your VPS's Tailscale IP or MagicDNS name, e.g. `http://100.x.y.z:3000` or `http://my-vps:3000`. See **[Cloud deployment (VPS over Tailscale)](#cloud-deployment-vps-over-tailscale)** below for how to find it.

With `LANGSMITH_API_KEY` set, every LangGraph run (plan → work → report, per-node I/O and timings) is traced to [LangSmith](https://smith.langchain.com) under the `openclaw-full-stack` project.

## Components

| Piece | Implementation |
|---|---|
| Orchestration control plane | [OpenClaw](https://openclaw.ai) CLI + gateway (Node), config hard-locked at boot |
| Planner LLM | Claude Opus 4.8 via official Anthropic SDK (streaming, adaptive thinking, JSON schema outputs) |
| Worker LLM | Hermes 3 Llama 3.1 8B GGUF on llama.cpp server (OpenAI-compatible API + Prometheus metrics) |
| Workflow engine | LangGraph `StateGraph` with SQLite checkpointer on a persistent volume |
| Knowledge / RAG | GraphRAG-style indexer: Obsidian wikilinks + tags → networkx graph; chunks → sentence-transformers embeddings → Chroma. Hybrid retrieval = vector top-k + 1-hop graph expansion |
| Memory | Named Docker volumes: `chroma-memory`, `langgraph-state`, `graphrag-graph`, `prom-data` — everything survives restarts |
| Monitoring | Prometheus scraping agent service and llama.cpp: token spend, GraphRAG query latency, LangGraph transitions, request throughput |

## Safety guardrails (locked)

Defined in [`config/guardrails.lock.json`](config/guardrails.lock.json), SHA-pinned at bootstrap and re-verified every loop cycle — the agent service refuses to run if the file is tampered with.

- **Token budget:** monthly cap with alert at 80% and hard cutoff at 100%
- **Audit watchdog:** JSONL audit trail in `audit-logs/`, 30-day retention sweep
- **Sandbox filter:** forbidden-action list (destructive shell patterns, `curl | bash`, etc.) checked on every LLM input
- **Prompt compression & context pruning** against a configurable token ceiling
- **Constrained JSON output** via schema for all planner responses

## RAM-aware model selection

`scripts/detect-ram.sh` reads host RAM at container start and picks the quantization (corrected from the usual inverted folklore — bigger quant needs more RAM):

| Host RAM | Model |
|---|---|
| < 5.8 GB | 8B Q3_K_M (~4.0 GB) |
| < 20 GB | 8B Q4_K_M (~4.9 GB) |
| < 48 GB | 8B Q6_K (~6.6 GB) |
| ≥ 48 GB | 70B Q4_K_M (~42 GB) |

Override with `HERMES_FORCE_FILE` in `.env`.

## Obsidian integration

Point the Obsidian app (or any editor) at `obsidian-vault/`. Every `[[wikilink]]` becomes a graph edge, every `#tag` a node; contents are embedded into vector memory. Re-indexed every 5 minutes (configurable). Agents ground their answers in the vault, and their reports flow back into it under `agent-reports/`.

## Repository layout

```
├── docker-compose.yml        # three services, private network, volumes
├── Dockerfile.openclaw       # Node (OpenClaw, Claude Code CLI) + Python agent stack
├── Dockerfile.hermes         # llama.cpp server + RAM-detect entrypoint
├── agents/                   # the agent service
│   ├── main.py               #   threads: indexer / agent loop / housekeeping
│   ├── graph.py              #   LangGraph plan→work→report pipeline
│   ├── indexer.py            #   GraphRAG vault indexer + graph HTML export
│   ├── llm.py                #   Claude + Hermes clients, hybrid routing
│   └── guardrails.py         #   budget, audit, sandbox, config lock
├── scripts/
│   ├── detect-ram.sh         # RAM → GGUF quantization selection
│   └── init-skills.sh        # container bootstrap: lock config, skills, gateway, loop
├── config/                   # locked guardrail + OpenClaw config
├── prompts/  schemas/        # editable prompt templates, JSON output schemas
├── obsidian-vault/           # your knowledge base (gitignored)
└── workspaces/               # agent inbox / outputs / evolved skills
```

## Operations

```bash
docker compose ps                          # health of all three services
docker logs -f openclaw-stack              # agent loop + guardrails live log
docker compose restart openclaw-stack      # apply .env / config changes
docker compose down                        # stop (state persists)
curl -s localhost:9091/metrics | grep llm_tokens_total   # spend check
```

## Notes

- The `./openclaw` bind mount in `docker-compose.yml` is **disabled by default** — mounting an empty folder over the image breaks it. See the comment in the compose file for live-source development.
- vLLM was deliberately replaced with llama.cpp: vLLM targets GPUs; llama.cpp is the correct engine for CPU-only machines.
- `.env`, the model cache, audit logs, and your vault are gitignored — nothing sensitive or bulky leaves your machine.

## Cloud deployment (VPS over Tailscale)

**This is the recommended production setup.** The stack runs 24/7 on any 16 GB VPS, reachable only over your private [Tailscale](https://tailscale.com) network — nothing is exposed to the public internet. The design goal is **disposable servers**: this Git repo is the single source of truth, so any server is a throwaway runtime you can delete and recreate in ~20 minutes.

### Why Tailscale (and why the URLs are dynamic)

The provider firewall allows **only SSH (port 22)** inbound. All service ports (18789, 8081, 3000, 8090, 9090) are therefore **unreachable from the public internet** — you reach them across your tailnet instead. Tailscale connects *outbound* from the server, so no inbound ports are opened for it.

Consequence: **your service URLs are dynamic.** They are `http://<this server's tailnet address>:<port>` — and that address is unique to each machine and **changes whenever you replace the server.** There is no fixed URL to hard-code; always derive it from the current server (below).

### First-time setup

1. **Create a VPS** — any provider, 16 GB RAM, Ubuntu 24.04, x86 or ARM. Add your SSH public key at creation. Attach a firewall allowing **only inbound SSH**.
2. **On the server**, install Docker + Compose and join your tailnet:
   ```bash
   curl -fsSL https://get.docker.com | sh
   curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up
   ```
3. **Deploy the stack:**
   ```bash
   git clone https://github.com/ancreativeai/dockerized-autonomous-multi-agent.git
   cd dockerized-autonomous-multi-agent
   cp .env.example .env   # set OPENCLAW_GATEWAY_TOKEN (required) + any API keys
   docker compose up -d
   ```
4. **Find your service URLs** — run this on the server:
   ```bash
   tailscale ip -4        # e.g. 100.107.239.95  → gateway at http://100.107.239.95:18789
   ```
   Or enable [MagicDNS](https://tailscale.com/kb/1081/magicdns) in the Tailscale admin console and use the server's name instead of the IP (e.g. `http://my-vps:3000`) — this is nicer because the name is stable even if the IP changes. Any device on **your** tailnet (laptop, phone) can open these; nobody else can.

### Replacing a server (delete + recreate)

Because the repo holds everything and only runtime state lives on the server, swapping servers is routine — do this to change provider/region, resize, or recover:

1. **(Optional) preserve agent state** from the old server — the knowledge graph, LangGraph checkpoints, and vector memory live in Docker named volumes:
   ```bash
   docker run --rm -v dockerized-autonomous-multi-agent_graphrag-graph:/v -v $PWD:/out alpine tar czf /out/state.tgz -C /v .
   # repeat for _langgraph-state and _chroma-memory, then scp the tarballs off
   ```
   (Skip this to start fresh — the vault re-indexes itself from `obsidian-vault/` on first boot anyway.)
2. **Delete the old server** in the provider console (most providers, incl. Hetzner, **bill stopped servers — only deletion stops charges**), and remove its now-offline node from the Tailscale admin console.
3. **Run First-time setup** on the new server. Restore any tarballs from step 1 into the matching volumes before `docker compose up -d`.
4. **Update your bookmarks / GitHub deploy secrets** with the new server's tailnet address (see below) — this is the only place the old URL lived.

### Auto-deploy on every push (optional)

`.github/workflows/deploy.yml` ships every push to the default branch to the VPS over Tailscale SSH (pull, rebuild, `compose up`). It stays dormant until these repo secrets exist:

| Secret | Value |
|---|---|
| `TS_OAUTH_CLIENT_ID` / `TS_OAUTH_SECRET` | Tailscale OAuth client (`auth_keys` scope, tag `tag:ci`) — from the Tailscale admin OAuth page |
| `VPS_HOST` | the server's **tailnet IP or MagicDNS name** (update this when you replace the server) |
| `VPS_USER` | SSH user (e.g. `root`) |
| `VPS_SSH_KEY` | a private deploy key whose public half is in the server's `authorized_keys` |

## License

Private project. All third-party components retain their own licenses (OpenClaw, llama.cpp, LangGraph, Chroma, Hermes 3 weights per NousResearch's license).
