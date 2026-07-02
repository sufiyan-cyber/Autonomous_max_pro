"""The Cognee memory layer for ALIBI.

Every NPC has their own Cognee dataset — their brain. The full lifecycle
is used as game mechanics:

  remember() — every interrogation exchange, every rumor an NPC hears
  recall()   — NPC dialogue is grounded in what THEY actually remember
  improve()  — the overnight "gossip pass" bridges the day's sessions
               into each NPC's knowledge graph and enriches relationships
  forget()   — memories decay: low-salience details fade after two
               in-game days, so witnesses literally forget

Backends: "cloud" (cognee.serve → Cognee Cloud), "local" (self-hosted
cognee), "mock" (no-key dev store with keyword recall).
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from . import config


def npc_dataset(npc_id: str) -> str:
    return f"npc_{npc_id}"


class MemoryBackend:
    """Interface all backends implement."""

    async def setup(self) -> None: ...

    async def wipe(self) -> None: ...

    async def remember(self, text: str, dataset: str, session_id: Optional[str] = None,
                       salience: str = "high", day: int = 0) -> Optional[str]:
        """Store a memory. Returns a data id when the backend provides one."""
        raise NotImplementedError

    async def recall(self, query: str, datasets: list[str], top_k: int = 8) -> list[str]:
        raise NotImplementedError

    async def improve(self, dataset: str, session_ids: Optional[list[str]] = None) -> None:
        raise NotImplementedError

    async def forget(self, dataset: str, data_id: Optional[str] = None) -> None:
        raise NotImplementedError

    async def graph(self, datasets: list[str]) -> dict:
        """Return {nodes: [...], links: [...]} for the corkboard."""
        raise NotImplementedError


# --------------------------------------------------------------------------
# Real cognee backend (cloud + local share almost everything)
# --------------------------------------------------------------------------

class CogneeBackend(MemoryBackend):
    def __init__(self, cloud: bool):
        self.cloud = cloud
        self._connected = False

    async def _ensure(self):
        import cognee
        if self.cloud and not self._connected:
            await cognee.serve(url=config.COGNEE_CLOUD_URL, api_key=config.COGNEE_CLOUD_API_KEY)
            self._connected = True

    async def setup(self) -> None:
        await self._ensure()

    async def wipe(self) -> None:
        import cognee
        await self._ensure()
        try:
            await cognee.forget(everything=True)
        except Exception:
            pass  # nothing to forget on a fresh tenant

    async def remember(self, text: str, dataset: str, session_id: Optional[str] = None,
                       salience: str = "high", day: int = 0) -> Optional[str]:
        import cognee
        await self._ensure()
        result = await cognee.remember(text, dataset_name=dataset, session_id=session_id)
        # RememberResult shape varies across versions — capture an id if present.
        for attr in ("data_id", "id"):
            val = getattr(result, attr, None)
            if val:
                return str(val)
        return None

    async def recall(self, query: str, datasets: list[str], top_k: int = 8) -> list[str]:
        import cognee
        await self._ensure()
        results = await cognee.recall(query, datasets=datasets, top_k=top_k)
        out = []
        for r in results:
            text = getattr(r, "text", None) or str(r)
            out.append(text)
        return out

    async def improve(self, dataset: str, session_ids: Optional[list[str]] = None) -> None:
        import cognee
        await self._ensure()
        await cognee.improve(dataset, session_ids=session_ids)

    async def forget(self, dataset: str, data_id: Optional[str] = None) -> None:
        import cognee
        await self._ensure()
        if data_id:
            await cognee.forget(data_id=uuid.UUID(data_id), dataset=dataset)
        else:
            await cognee.forget(dataset=dataset)

    async def graph(self, datasets: list[str]) -> dict:
        """Export each dataset's knowledge graph and merge for the corkboard."""
        import cognee
        await self._ensure()
        nodes: dict[str, dict] = {}
        links: list[dict] = []
        for ds in datasets:
            try:
                snapshot = await cognee.export(dataset=ds, format="pydantic")
            except Exception:
                continue
            raw_nodes = getattr(snapshot, "nodes", None) or []
            raw_edges = getattr(snapshot, "edges", None) or getattr(snapshot, "relationships", None) or []
            for n in raw_nodes:
                nid = str(getattr(n, "id", None) or getattr(n, "node_id", uuid.uuid4()))
                label = (getattr(n, "name", None) or getattr(n, "label", None)
                         or getattr(n, "text", None) or "")
                ntype = str(getattr(n, "type", None) or getattr(n, "node_type", "entity"))
                if nid not in nodes:
                    nodes[nid] = {"id": nid, "label": str(label)[:80], "type": ntype, "dataset": ds}
            for e in raw_edges:
                src = str(getattr(e, "source_node_id", None) or getattr(e, "source", ""))
                dst = str(getattr(e, "target_node_id", None) or getattr(e, "target", ""))
                rel = str(getattr(e, "relationship_name", None) or getattr(e, "label", "") or "")
                if src and dst:
                    links.append({"source": src, "target": dst, "label": rel, "dataset": ds})
        return {"nodes": list(nodes.values()), "links": links}


# --------------------------------------------------------------------------
# Mock backend — keyless development. Naive keyword recall over stored text.
# --------------------------------------------------------------------------

class MockBackend(MemoryBackend):
    def __init__(self):
        self.store: dict[str, list[dict]] = {}
        self._load()

    def _load(self):
        if config.MOCK_MEMORY_FILE.exists():
            try:
                self.store = json.loads(config.MOCK_MEMORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.store = {}

    def _save(self):
        config.MOCK_MEMORY_FILE.write_text(
            json.dumps(self.store, indent=1), encoding="utf-8")

    async def setup(self) -> None:
        pass

    async def wipe(self) -> None:
        self.store = {}
        self._save()

    async def remember(self, text: str, dataset: str, session_id: Optional[str] = None,
                       salience: str = "high", day: int = 0) -> Optional[str]:
        data_id = str(uuid.uuid4())
        self.store.setdefault(dataset, []).append({
            "id": data_id, "text": text, "session": session_id,
            "salience": salience, "day": day, "ts": time.time(),
        })
        self._save()
        return data_id

    async def recall(self, query: str, datasets: list[str], top_k: int = 8) -> list[str]:
        words = {w.lower().strip(".,?!\"'") for w in query.split() if len(w) > 3}
        scored: list[tuple[int, str]] = []
        for ds in datasets:
            for item in self.store.get(ds, []):
                score = sum(1 for w in words if w in item["text"].lower())
                if score:
                    scored.append((score, item["text"]))
        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored[:top_k]]

    async def improve(self, dataset: str, session_ids: Optional[list[str]] = None) -> None:
        pass  # no-op in mock

    async def forget(self, dataset: str, data_id: Optional[str] = None) -> None:
        if data_id is None:
            self.store.pop(dataset, None)
        else:
            self.store[dataset] = [i for i in self.store.get(dataset, []) if i["id"] != data_id]
        self._save()

    async def graph(self, datasets: list[str]) -> dict:
        # Mock has no real graph — engine falls back to the claims ledger.
        return {"nodes": [], "links": []}


def get_backend() -> MemoryBackend:
    if config.MEMORY_BACKEND == "cloud":
        return CogneeBackend(cloud=True)
    if config.MEMORY_BACKEND == "local":
        return CogneeBackend(cloud=False)
    return MockBackend()
