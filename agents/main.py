"""Agent service entrypoint: persistent autonomous background multi-agent loop.

Threads:
  1. GraphRAG vault indexer  — re-ingests the Obsidian vault every N seconds
  2. Agent loop              — processes goal files from workspaces/inbox/*.md
                               (planner=Claude, workers=Hermes); when idle,
                               runs Hermes-only self-maintenance tasks
  3. Housekeeping            — guardrail lock verification, audit retention
Prometheus metrics served on :9091.
"""
import os
import pathlib
import shutil
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prometheus_client import Gauge, start_http_server

from guardrails import Guardrails, TokenBudgetExceeded
from indexer import VaultIndexer

UPTIME = Gauge("agent_service_uptime_seconds", "Agent service uptime")
SPEND_PCT = Gauge("token_budget_spend_pct", "Monthly paid-token budget consumed (%)")
START = time.time()

INBOX = pathlib.Path("/app/workspaces/inbox")
DONE = pathlib.Path("/app/workspaces/done")


def log(msg):
    print(f"[agent-service] {msg}", flush=True)


def wait_for_hermes():
    import requests
    base = os.getenv("HERMES_BASE_URL", "http://hermes-llm:8080/v1")
    url = base.rsplit("/v1", 1)[0] + "/health"
    log(f"waiting for Hermes at {url} (first boot downloads the model — may take a while)")
    while True:
        try:
            if requests.get(url, timeout=5).status_code == 200:
                log("Hermes is up.")
                return
        except Exception:
            pass
        time.sleep(15)


def agent_loop(guard, agent_graph):
    interval = int(os.getenv("AUTONOMOUS_INTERVAL_SECONDS", "1800"))
    hermes_only_idle = os.getenv("AUTONOMOUS_HERMES_ONLY", "true").lower() == "true"
    last_selftask = 0.0
    log(f"autonomous loop live — drop goal files into workspaces/inbox/ "
        f"(idle self-task every {interval}s, hermes_only={hermes_only_idle})")
    while True:
        try:
            guard.verify_lock()
            goals = sorted(INBOX.glob("*.md")) + sorted(INBOX.glob("*.txt"))
            if goals:
                goal_file = goals[0]
                goal = goal_file.read_text().strip()
                log(f"processing goal from inbox: {goal_file.name}")
                if goal:
                    final = agent_graph.run_goal(goal, source="inbox")
                    log(f"goal done -> {final.get('report_path')}")
                DONE.mkdir(parents=True, exist_ok=True)
                shutil.move(str(goal_file), DONE / goal_file.name)
                continue  # drain inbox before self-tasks
            if time.time() - last_selftask > interval:
                last_selftask = time.time()
                goal = ("Review the most recently updated notes in the knowledge base. "
                        "Summarise new themes, list notes that lack outgoing links or tags, "
                        "and propose 3 concrete improvements to the vault structure.")
                log("running autonomous self-maintenance task")
                agent_graph.run_goal(goal, source="autonomous",
                                     hermes_only=hermes_only_idle)
        except TokenBudgetExceeded as exc:
            log(f"TOKEN CAP REACHED — pausing paid work 1h: {exc}")
            time.sleep(3600)
        except Exception as exc:
            log(f"agent loop error (continuing): {exc}")
            time.sleep(30)
        time.sleep(10)


def housekeeping(guard):
    while True:
        try:
            guard.verify_lock()
            guard.retention_sweep()
            SPEND_PCT.set(guard.spend_pct())
            UPTIME.set(time.time() - START)
        except Exception as exc:
            log(f"housekeeping error: {exc}")
        time.sleep(60)


def main():
    start_http_server(9091)
    log("Prometheus metrics on :9091")

    guard = Guardrails()
    guard.verify_lock()
    guard.audit("agent_service_start",
                planner=os.getenv("CLAUDE_MODEL", "claude-opus-4-8"),
                workers=os.getenv("WORKER_AGENT_COUNT", "2"))
    if not os.getenv("ANTHROPIC_API_KEY"):
        log("WARNING: ANTHROPIC_API_KEY not set — planning falls back to local Hermes "
            "until a key is added to .env")

    indexer = VaultIndexer(guard)
    reindex = int(os.getenv("GRAPHRAG_REINDEX_SECONDS", "300"))
    threading.Thread(target=indexer.run_forever, args=(reindex,),
                     daemon=True, name="graphrag-indexer").start()
    log(f"GraphRAG indexer live (every {reindex}s)")

    threading.Thread(target=housekeeping, args=(guard,),
                     daemon=True, name="housekeeping").start()

    wait_for_hermes()

    from graph import AgentGraph
    agent_graph = AgentGraph(guard, indexer)
    log("LangGraph multi-agent state engine compiled "
        "(checkpointer: /data/state/langgraph.sqlite)")
    agent_loop(guard, agent_graph)


if __name__ == "__main__":
    main()
