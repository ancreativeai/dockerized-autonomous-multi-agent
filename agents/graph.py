"""LangGraph stateful multi-agent workflow.

plan (Claude, constrained JSON) -> work (Hermes worker pool) -> report (writes
markdown + self-evolved skills to the shared workspace). State is checkpointed
to SQLite on a persistent volume, so sessions survive container restarts.
"""
import json
import os
import pathlib
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from prometheus_client import Counter

import llm

TRANSITIONS = Counter("langgraph_state_transitions_total",
                      "LangGraph node transitions", ["node"])
GOALS = Counter("agent_goals_total", "Goals processed", ["source", "status"])

STATE_DB = "/data/state/langgraph.sqlite"
REPORT_DIR = pathlib.Path("/app/workspaces/openclaw/reports")
SKILL_DIR = pathlib.Path("/app/workspaces/openclaw/skills")
WORKER_WS = pathlib.Path("/app/workspaces")

PLAN_SCHEMA = json.load(open("/app/schemas/plan_schema.json"))
PLANNER_SYSTEM = pathlib.Path("/app/prompts/planner_system.txt").read_text()
WORKER_SYSTEM = pathlib.Path("/app/prompts/worker_system.txt").read_text()


class AgentState(TypedDict, total=False):
    goal: str
    hermes_only: bool
    plan: dict
    results: list
    report_path: str


class AgentGraph:
    def __init__(self, guard, indexer):
        self.guard = guard
        self.indexer = indexer
        self.workers = max(1, int(os.getenv("WORKER_AGENT_COUNT", "2")))
        conn = sqlite3.connect(STATE_DB, check_same_thread=False)
        self.checkpointer = SqliteSaver(conn)

        g = StateGraph(AgentState)
        g.add_node("plan", self.plan_node)
        g.add_node("work", self.work_node)
        g.add_node("report", self.report_node)
        g.set_entry_point("plan")
        g.add_edge("plan", "work")
        g.add_edge("work", "report")
        g.add_edge("report", END)
        self.app = g.compile(checkpointer=self.checkpointer)

    # ── nodes ──
    def plan_node(self, state: AgentState):
        TRANSITIONS.labels("plan").inc()
        goal = state["goal"]
        context = self.indexer.query(goal)
        prompt = (f"GOAL:\n{goal}\n\nKNOWLEDGE BASE CONTEXT (GraphRAG):\n{context}\n\n"
                  "Decompose the goal into worker tasks per the schema.")
        use_claude = llm.claude_available() and not state.get("hermes_only")
        if use_claude:
            raw = llm.claude_plan(self.guard, PLANNER_SYSTEM, prompt, schema=PLAN_SCHEMA)
        else:
            raw = llm.hermes_work(self.guard, PLANNER_SYSTEM, prompt, schema=PLAN_SCHEMA)
        plan = llm.parse_json(raw, fallback=None) or {
            "summary": goal,
            "tasks": [{"id": "t1", "description": goal,
                       "expected_output": "best-effort answer"}],
            "new_skills": [],
        }
        self.guard.audit("plan_created", planner="claude" if use_claude else "hermes",
                         tasks=len(plan.get("tasks", [])))
        return {"plan": plan}

    def _run_task(self, task):
        ws = WORKER_WS / f"worker-{task['id']}"
        ws.mkdir(parents=True, exist_ok=True)
        context = self.indexer.query(task["description"])
        prompt = (f"TASK: {task['description']}\n"
                  f"EXPECTED OUTPUT: {task.get('expected_output', '')}\n\n"
                  f"CONTEXT (GraphRAG):\n{context}")
        try:
            answer = llm.hermes_work(self.guard, WORKER_SYSTEM, prompt)
        except Exception as exc:
            answer = f"[worker error: {exc}]"
        (ws / "last_output.md").write_text(answer)
        return {"id": task["id"], "description": task["description"], "answer": answer}

    def work_node(self, state: AgentState):
        TRANSITIONS.labels("work").inc()
        tasks = state["plan"].get("tasks", [])[:8]
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            results = list(pool.map(self._run_task, tasks))
        return {"results": results}

    def report_node(self, state: AgentState):
        TRANSITIONS.labels("report").inc()
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        SKILL_DIR.mkdir(parents=True, exist_ok=True)
        # self-evolve skills proposed by the planner
        for skill in state["plan"].get("new_skills", []):
            name = "".join(c for c in skill["name"] if c.isalnum() or c in "-_ ").strip()
            if name:
                (SKILL_DIR / f"{name}.md").write_text(
                    f"# Skill: {name}\n\n{skill['instructions']}\n")
                self.guard.audit("skill_evolved", skill=name)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = REPORT_DIR / f"report-{stamp}.md"
        lines = [f"# {state['plan'].get('summary', state['goal'])}",
                 f"\n_Goal:_ {state['goal']}\n"]
        for r in state.get("results", []):
            lines += [f"\n## Task {r['id']}: {r['description']}\n", r["answer"]]
        path.write_text("\n".join(lines))
        # also drop the report into the vault so GraphRAG re-ingests agent output
        vault_out = pathlib.Path("/app/obsidian-vault/agent-reports")
        vault_out.mkdir(parents=True, exist_ok=True)
        (vault_out / path.name).write_text(path.read_text())
        return {"report_path": str(path)}

    # ── entry ──
    def run_goal(self, goal, source="inbox", hermes_only=False):
        self.guard.verify_lock()
        thread_id = f"{source}-{uuid.uuid4().hex[:8]}"
        try:
            final = self.app.invoke(
                {"goal": goal, "hermes_only": hermes_only},
                config={"configurable": {"thread_id": thread_id}},
            )
            GOALS.labels(source, "ok").inc()
            self.guard.audit("goal_completed", source=source,
                             report=final.get("report_path"))
            return final
        except Exception as exc:
            GOALS.labels(source, "error").inc()
            self.guard.audit("goal_failed", source=source, error=str(exc))
            raise
