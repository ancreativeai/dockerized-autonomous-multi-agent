"""GraphRAG vault indexer.

Continuously (every GRAPHRAG_REINDEX_SECONDS) ingests the Obsidian vault:
  * entity/relationship knowledge graph from [[wikilinks]] and #tags (networkx,
    persisted as GraphML in /data/graph)
  * vector embeddings per chunk (sentence-transformers -> Chroma, persisted in
    /data/memory) as the long-term memory cache

Queries do hybrid retrieval: vector top-k + 1-hop graph-neighbourhood expansion.
"""
import json
import os
import pathlib
import re
import threading
import time

import networkx as nx
from prometheus_client import Counter, Gauge, Histogram

VAULT = pathlib.Path("/app/obsidian-vault")
GRAPH_DIR = pathlib.Path("/data/graph")
CHROMA_DIR = "/data/memory/chroma"

WIKILINK = re.compile(r"\[\[([^\]|#]+)")
TAG = re.compile(r"(?<!\S)#([\w/-]+)")

DOCS_INDEXED = Counter("graphrag_documents_indexed_total", "Vault documents (re)indexed")
GRAPH_NODES = Gauge("graphrag_graph_nodes", "Knowledge graph node count")
GRAPH_EDGES = Gauge("graphrag_graph_edges", "Knowledge graph edge count")
QUERY_LATENCY = Histogram("graphrag_query_seconds", "GraphRAG query latency",
                          buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10))
LAST_INDEX_TS = Gauge("graphrag_last_index_timestamp", "Unix time of last index pass")


class VaultIndexer:
    def __init__(self, guard):
        self.guard = guard
        self.top_k = int(os.getenv("GRAPHRAG_TOP_K", "6"))
        self.graph = nx.DiGraph()
        self._mtimes = {}
        self._lock = threading.Lock()
        self._init_lock = threading.Lock()
        self._embedder = None
        self._collection = None
        GRAPH_DIR.mkdir(parents=True, exist_ok=True)
        graphml = GRAPH_DIR / "vault.graphml"
        if graphml.exists():
            try:
                self.graph = nx.read_graphml(graphml)
            except Exception:
                self.graph = nx.DiGraph()

    def _lazy_init(self):
        # Serialized: the indexer thread and the agent loop both call this, and a
        # single Chroma PersistentClient must not be created twice on one path
        # (raises KeyError on the shared-system cache in chromadb >= 1.5).
        if self._embedder is not None and self._collection is not None:
            return
        with self._init_lock:
            if self._embedder is None:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            if self._collection is None:
                import chromadb
                client = chromadb.PersistentClient(path=CHROMA_DIR)
                self._collection = client.get_or_create_collection(
                    "vault", metadata={"hnsw:space": "cosine"})

    # ── indexing ──
    def index_pass(self):
        self._lazy_init()
        changed = []
        seen = set()
        for path in sorted(VAULT.rglob("*.md")):
            rel = str(path.relative_to(VAULT))
            seen.add(rel)
            mtime = path.stat().st_mtime
            if self._mtimes.get(rel) != mtime:
                self._mtimes[rel] = mtime
                changed.append((rel, path))
        for rel, path in changed:
            try:
                self._index_file(rel, path.read_text(errors="replace"))
                DOCS_INDEXED.inc()
            except Exception as exc:  # one bad note must not stop the loop
                self.guard.audit("graphrag_index_error", file=rel, error=str(exc))
        # drop deleted notes from the graph
        with self._lock:
            stale = [n for n, d in self.graph.nodes(data=True)
                     if d.get("kind") == "note" and d.get("rel") not in seen]
            self.graph.remove_nodes_from(stale)
            GRAPH_NODES.set(self.graph.number_of_nodes())
            GRAPH_EDGES.set(self.graph.number_of_edges())
            if changed or stale:
                nx.write_graphml(self.graph, GRAPH_DIR / "vault.graphml")
                self._export_html()
        LAST_INDEX_TS.set(time.time())
        if changed:
            self.guard.audit("graphrag_index_pass", files_reindexed=len(changed))
        return len(changed)

    def _index_file(self, rel, text):
        title = pathlib.Path(rel).stem
        with self._lock:
            if title in self.graph:
                self.graph.remove_edges_from(list(self.graph.out_edges(title)))
            self.graph.add_node(title, kind="note", rel=rel)
            for target in set(WIKILINK.findall(text)):
                target = target.strip()
                if target:
                    self.graph.add_node(target, kind=self.graph.nodes.get(
                        target, {}).get("kind", "note"))
                    self.graph.add_edge(title, target, rel_type="links_to")
            for tag in set(TAG.findall(text)):
                node = f"#{tag}"
                self.graph.add_node(node, kind="tag")
                self.graph.add_edge(title, node, rel_type="tagged")
        # vector memory: chunk + embed + upsert
        chunks = [text[i:i + 1200] for i in range(0, len(text), 1000)][:40] or [title]
        ids = [f"{rel}::{i}" for i in range(len(chunks))]
        vectors = self._embedder.encode(chunks, show_progress_bar=False).tolist()
        self._collection.upsert(
            ids=ids, embeddings=vectors, documents=chunks,
            metadatas=[{"note": title, "rel": rel}] * len(chunks))

    def _export_html(self):
        """Interactive knowledge-graph view, regenerated every index pass.
        Open workspaces/openclaw/knowledge-graph.html in a browser."""
        nodes = [{"id": n, "label": n,
                  "group": d.get("kind", "note"),
                  "shape": "dot", "size": 8 + 2 * self.graph.degree(n)}
                 for n, d in self.graph.nodes(data=True)]
        edges = [{"from": u, "to": v, "title": d.get("rel_type", "")}
                 for u, v, d in self.graph.edges(data=True)]
        html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Vault knowledge graph</title>"
            "<script src='https://unpkg.com/vis-network/standalone/umd/"
            "vis-network.min.js'></script>"
            "<style>html,body,#g{height:100%;margin:0;background:#1e1e2e}</style>"
            "</head><body><div id='g'></div><script>"
            f"var nodes=new vis.DataSet({json.dumps(nodes)});"
            f"var edges=new vis.DataSet({json.dumps(edges)});"
            "new vis.Network(document.getElementById('g'),{nodes:nodes,edges:edges},"
            "{nodes:{font:{color:'#cdd6f4'}},edges:{color:{opacity:0.4}},"
            "groups:{tag:{color:'#f9e2af'},note:{color:'#89b4fa'}},"
            "physics:{solver:'forceAtlas2Based',stabilization:{iterations:60}}});"
            "</script></body></html>")
        out = pathlib.Path("/app/workspaces/openclaw/knowledge-graph.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html)

    # ── retrieval ──
    def query(self, text, k=None):
        self._lazy_init()
        start = time.time()
        try:
            vec = self._embedder.encode([text], show_progress_bar=False).tolist()
            res = self._collection.query(query_embeddings=vec, n_results=k or self.top_k)
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            notes = {m["note"] for m in metas if m}
            neighbours = set()
            with self._lock:
                for n in notes:
                    if n in self.graph:
                        neighbours.update(self.graph.successors(n))
                        neighbours.update(self.graph.predecessors(n))
            context = "\n---\n".join(docs)
            if neighbours:
                context += "\n---\nRelated notes/tags in knowledge graph: " + \
                           ", ".join(sorted(neighbours - notes)[:20])
            return context
        finally:
            QUERY_LATENCY.observe(time.time() - start)

    # ── background loop ──
    def run_forever(self, interval):
        while True:
            try:
                self.index_pass()
            except Exception as exc:
                self.guard.audit("graphrag_loop_error", error=str(exc))
            time.sleep(interval)
