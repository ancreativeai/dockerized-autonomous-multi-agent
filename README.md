# OpenClaw Full Stack

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

**Hybrid LLM routing, locked at bootstrap:** Claude (Opus 4.8, adaptive thinking, constrained JSON output) is used *exclusively* for planning and orchestration; all worker tasks run on the free local Hermes model to minimize paid API calls. Without an API key the planner gracefully falls back to Hermes.

**The agent loop:** drop a goal file into `workspaces/inbox/` → the LangGraph pipeline (`plan → work → report`) decomposes it, executes tasks on a parallel worker pool with GraphRAG-retrieved context, and writes a markdown report to `workspaces/openclaw/reports/` and back into the vault, where it gets re-ingested. When idle, the loop runs Hermes-only vault-maintenance tasks on a timer.

## Quick start

```bash
git clone git@github.com:ancreativeai/openclaw-full-stack.git
cd openclaw-full-stack
cp .env.example .env
# edit .env:
#   ANTHROPIC_API_KEY=sk-ant-...              (optional but recommended)
#   OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 24)   (required)
docker compose up -d
```

First boot downloads the Hermes GGUF model (~4.9 GB, resumable, cached in `hermes/` thereafter). Then:

| Interface | URL |
|---|---|
| OpenClaw gateway UI | http://localhost:18789 (token from `.env`) |
| Hermes chat (llama.cpp) | http://localhost:8081 |
| Prometheus | http://localhost:9090 |
| Knowledge graph view | `workspaces/openclaw/knowledge-graph.html` |

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

## License

Private project. All third-party components retain their own licenses (OpenClaw, llama.cpp, LangGraph, Chroma, Hermes 3 weights per NousResearch's license).
