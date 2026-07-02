"""ALIBI game engine — orchestrates story, memory lifecycle, and dialogue."""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from . import config, llm
from .memory import get_backend, npc_dataset
from .story import CASE, NPCS, TOWN_RECORD, RELATIONSHIPS

backend = get_backend()

DEFAULT_STATE = {
    "started": False,
    "day": 1,
    "actions_left": CASE["actions_per_day"],
    "game_over": False,
    "ending": None,
    "trust": {npc: 0 for npc in NPCS},
    "revealed_secrets": [],          # ["sal:blackmail_payments", ...]
    "threads_found": [],             # subset of CASE.evidence_threads keys
    "sessions": {},                  # npc -> [ {detective, npc} ] for current day
    "claims": [],                    # corkboard ledger: {day, npc, subject, predicate, object, is_lie}
    "gossip_log": [],                # what spread each night
    "memory_ids": [],                # {id, dataset, day, salience} for decay
    "todays_events": [],             # notable events for tonight's gossip pass
    "journal": [],                   # detective's case journal entries
}

_state: Optional[dict] = None
_lock = asyncio.Lock()


def load_state() -> dict:
    global _state
    if _state is None:
        if config.STATE_FILE.exists():
            _state = json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
        else:
            _state = json.loads(json.dumps(DEFAULT_STATE))
    return _state


def save_state():
    config.STATE_FILE.write_text(json.dumps(_state, indent=1), encoding="utf-8")


# Map secrets to the evidence threads they unlock.
SECRET_TO_THREAD = {
    "sal:blackmail_payments": "blackmail_motive",
    "vera:customs_letter": "blackmail_motive",
    "vera:harbor_log": "log_contradiction",
    "doc:saw_rhodes": "witness_sighting",
}


async def new_game() -> dict:
    """Reset the world: forget() everything, then remember() each NPC's dossier."""
    global _state
    async with _lock:
        await backend.setup()
        await backend.wipe()
        _state = json.loads(json.dumps(DEFAULT_STATE))
        _state["started"] = True

        seeds = []
        for npc_id, npc in NPCS.items():
            ds = npc_dataset(npc_id)
            rel = "; ".join(f"{NPCS[k]['name']}: {v}" for k, v in RELATIONSHIPS[npc_id].items())
            seeds.append((f"{TOWN_RECORD}", ds))
            seeds.append((f"My private knowledge and memories: {npc['dossier']}", ds))
            seeds.append((f"My opinions of the others: {rel}", ds))
        for text, ds in seeds:
            data_id = await backend.remember(text, dataset=ds, salience="core", day=0)
            if data_id:
                _state["memory_ids"].append({"id": data_id, "dataset": ds, "day": 0, "salience": "core"})
        save_state()
        return public_state()


def public_state() -> dict:
    s = load_state()
    return {
        "started": s["started"],
        "day": s["day"],
        "days_total": CASE["days"],
        "actions_left": s["actions_left"],
        "game_over": s["game_over"],
        "ending": s["ending"],
        "case": {"title": CASE["title"], "setting": CASE["setting"], "victim": CASE["victim"]},
        "suspects": [
            {
                "id": npc_id,
                "name": npc["name"],
                "role": npc["role"],
                "portrait": npc["portrait"],
                "public_story": npc["public_story"],
                "trust": s["trust"][npc_id],
            }
            for npc_id, npc in NPCS.items()
        ],
        "threads_found": s["threads_found"],
        "threads_total": len(CASE["evidence_threads"]),
        "journal": s["journal"][-30:],
        "gossip_log": s["gossip_log"][-20:],
    }


async def interrogate(npc_id: str, line: str) -> dict:
    s = load_state()
    if not s["started"] or s["game_over"]:
        raise ValueError("No active game.")
    if s["actions_left"] <= 0:
        raise ValueError("No questions left today. End the day.")
    if npc_id not in NPCS:
        raise ValueError("Unknown suspect.")

    async with _lock:
        ds = npc_dataset(npc_id)
        day = s["day"]
        session_id = f"day{day}_{npc_id}"

        # recall(): what does this NPC remember that's relevant?
        memories = await backend.recall(line, datasets=[ds], top_k=8)
        # Also recall what they remember about the detective's past statements.
        past = await backend.recall(f"detective said asked claimed {line}", datasets=[ds], top_k=4)
        memories = list(dict.fromkeys(memories + past))[:10]

        gossip = [g["rumor"] for g in s["gossip_log"] if g.get("to_npc") == npc_id][-4:]
        recent = s["sessions"].get(npc_id, [])

        turn = await llm.npc_reply(npc_id, line, s["trust"][npc_id], day,
                                   memories, gossip, recent)

        # remember(): both sides of the exchange become this NPC's memory.
        exchange = (
            f"Day {day}. The detective said to me: \"{line}\". "
            f"I replied: \"{turn.dialogue}\". "
            + (f"(Privately: {turn.inner_note})" if turn.inner_note else "")
        )
        data_id = await backend.remember(exchange, dataset=ds, session_id=session_id,
                                         salience="high", day=day)
        if data_id:
            s["memory_ids"].append({"id": data_id, "dataset": ds, "day": day, "salience": "high"})

        # Claims feed the corkboard and the day's gossip pool.
        for c in turn.claims:
            s["claims"].append({
                "day": day, "npc": npc_id,
                "subject": c.subject, "predicate": c.predicate,
                "object": c.object, "is_lie": c.is_lie,
            })
            s["todays_events"].append(
                f"{NPCS[npc_id]['name']} told the detective: {c.subject} {c.predicate} {c.object}")

        # Trust + secrets + evidence threads.
        s["trust"][npc_id] = max(-5, min(5, s["trust"][npc_id] + turn.trust_delta))
        newly_found = []
        for sec in turn.revealed_secrets:
            key = f"{npc_id}:{sec}"
            if key not in s["revealed_secrets"]:
                s["revealed_secrets"].append(key)
                s["journal"].append(f"Day {day} — {NPCS[npc_id]['name']} revealed: "
                                    + next((x["text"] for x in NPCS[npc_id]["secrets"] if x["id"] == sec), sec))
                thread = SECRET_TO_THREAD.get(key)
                if thread and thread not in s["threads_found"]:
                    s["threads_found"].append(thread)
                    newly_found.append(CASE["evidence_threads"][thread])

        s["sessions"].setdefault(npc_id, []).append({"detective": line, "npc": turn.dialogue})
        s["actions_left"] -= 1
        save_state()

        return {
            "dialogue": turn.dialogue,
            "npc": npc_id,
            "name": NPCS[npc_id]["name"],
            "trust": s["trust"][npc_id],
            "trust_delta": turn.trust_delta,
            "caught_contradiction": turn.caught_contradiction,
            "new_threads": newly_found,
            "actions_left": s["actions_left"],
            "memories_recalled": len(memories),
        }


async def end_day() -> dict:
    """Night falls: improve() bridges sessions into graphs, gossip spreads
    via remember(), and old low-salience memories decay via forget()."""
    s = load_state()
    if not s["started"] or s["game_over"]:
        raise ValueError("No active game.")

    async with _lock:
        day = s["day"]

        # 1. improve(): fold the day's session memory into each NPC's graph.
        for npc_id in NPCS:
            if npc_id in s["sessions"]:
                try:
                    await backend.improve(npc_dataset(npc_id),
                                          session_ids=[f"day{day}_{npc_id}"])
                except Exception:
                    pass

        # 2. Gossip pass: rumors spread along relationship lines.
        gossip_items = []
        try:
            gossip_items = await llm.generate_gossip(day, s["todays_events"][-24:])
        except Exception:
            pass
        spread = []
        for g in gossip_items:
            if g.to_npc not in NPCS:
                continue
            data_id = await backend.remember(
                f"Day {day}, rumor I heard: {g.rumor}",
                dataset=npc_dataset(g.to_npc), salience=g.salience, day=day)
            if data_id:
                s["memory_ids"].append({"id": data_id, "dataset": npc_dataset(g.to_npc),
                                        "day": day, "salience": g.salience})
            entry = {"day": day, "to_npc": g.to_npc, "rumor": g.rumor}
            s["gossip_log"].append(entry)
            spread.append(entry)

        # 3. forget(): low-salience memories older than 2 days decay.
        survivors = []
        forgotten = 0
        for m in s["memory_ids"]:
            if m["salience"] == "low" and m["day"] <= day - 2 and m["day"] > 0:
                try:
                    await backend.forget(m["dataset"], data_id=m["id"])
                    forgotten += 1
                    continue
                except Exception:
                    pass
            survivors.append(m)
        s["memory_ids"] = survivors

        # 4. Advance the calendar.
        s["day"] += 1
        s["sessions"] = {}
        s["todays_events"] = []
        s["actions_left"] = CASE["actions_per_day"]

        out_of_time = s["day"] > CASE["days"]
        if out_of_time:
            s["game_over"] = True
            s["ending"] = {
                "correct": False,
                "epilogue": "THE INQUEST CLOSES",
                "narration": (
                    "The third morning comes gray and final. The inquest rules death "
                    "by misadventure, the file is tied with string, and the Mariposa "
                    "slips her mooring on the evening tide. You never made an arrest. "
                    "Somewhere out past the breakwater, a man who owed everything "
                    "and paid nothing raises his glass to the fog."
                ),
            }
        save_state()
        return {"day": s["day"], "gossip": spread, "memories_faded": forgotten,
                "game_over": s["game_over"], "ending": s["ending"]}


async def accuse(npc_id: str) -> dict:
    s = load_state()
    if not s["started"] or s["game_over"]:
        raise ValueError("No active game.")
    if npc_id not in NPCS:
        raise ValueError("Unknown suspect.")

    async with _lock:
        verdict = await llm.accusation_verdict(
            npc_id,
            [CASE["evidence_threads"][t] for t in s["threads_found"]],
            s["journal"][-10:],
        )
        s["game_over"] = True
        s["ending"] = {"correct": verdict.correct, "epilogue": verdict.epilogue,
                       "narration": verdict.narration, "accused": npc_id}
        save_state()
        return s["ending"]


async def corkboard() -> dict:
    """The detective's board: Cognee's merged knowledge graph when available,
    always overlaid with the claims ledger (testimony edges)."""
    s = load_state()
    datasets = [npc_dataset(n) for n in NPCS]
    g = {"nodes": [], "links": []}
    try:
        g = await backend.graph(datasets)
    except Exception:
        pass

    nodes = {n["id"]: n for n in g["nodes"]}
    links = list(g["links"])

    def ensure_node(nid: str, label: str, ntype: str):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": label, "type": ntype, "dataset": "claims"}

    for npc_id, npc in NPCS.items():
        ensure_node(f"npc:{npc_id}", npc["name"], "suspect")
    ensure_node("victim", CASE["victim"], "victim")

    for i, c in enumerate(s["claims"]):
        cid = f"claim:{i}"
        ensure_node(cid, f"{c['subject']} {c['predicate']} {c['object']}"[:90],
                    "lie" if c["is_lie"] else "claim")
        links.append({"source": f"npc:{c['npc']}", "target": cid,
                      "label": f"said (day {c['day']})", "dataset": "claims"})

    return {"nodes": list(nodes.values()), "links": links,
            "graph_source": "cognee" if g["nodes"] else "claims_ledger"}
