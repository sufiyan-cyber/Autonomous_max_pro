"""NPC dialogue engine — Groq (Llama) gives each suspect a voice.

Each reply is structured JSON: the spoken dialogue plus the factual claims
the NPC just made (which feed both Cognee memory and the corkboard), a
trust delta, and any secrets revealed this turn.
"""
from __future__ import annotations

import json
from typing import Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from . import config
from .story import CASE, NPCS

_client: Optional[AsyncOpenAI] = None


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


T = TypeVar("T", bound=BaseModel)


async def _json_completion(model_cls: Type[T], system: str, messages: list[dict],
                           max_tokens: int = 1200) -> Optional[T]:
    """Chat completion constrained to JSON matching a pydantic schema."""
    schema = json.dumps(model_cls.model_json_schema(), indent=0)
    system_full = (
        system
        + "\n\nRespond ONLY with a single JSON object matching this JSON schema "
          "(no markdown, no commentary):\n" + schema
    )
    resp = await client().chat.completions.create(
        model=config.ALIBI_MODEL,
        max_tokens=max_tokens,
        temperature=0.8,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system_full}, *messages],
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        return model_cls.model_validate_json(raw)
    except ValidationError:
        # Second chance: strip anything around the outermost braces.
        try:
            start, end = raw.index("{"), raw.rindex("}") + 1
            return model_cls.model_validate_json(raw[start:end])
        except Exception:
            return None


class Claim(BaseModel):
    subject: str = Field(description="Who/what the claim is about, e.g. 'Captain Rhodes'")
    predicate: str = Field(description="Short relation, e.g. 'was seen at', 'claims he was'")
    object: str = Field(description="The rest of the claim, e.g. 'the lighthouse path at 11:30 PM'")
    is_lie: bool = Field(default=False, description="True if the NPC knows this claim is false")


class NpcTurn(BaseModel):
    dialogue: str = Field(description="The NPC's spoken reply, in their voice. 1-4 sentences usually; more if confessing.")
    inner_note: str = Field(default="", description="One private sentence: what the NPC is thinking/hiding right now.")
    claims: list[Claim] = Field(default_factory=list, description="Factual claims the NPC just made aloud (empty if pure deflection).")
    trust_delta: int = Field(default=0, description="-2..+2 change in trust toward the detective based on this exchange.")
    revealed_secrets: list[str] = Field(default_factory=list, description="IDs of the NPC's secrets fully revealed in this reply, if any.")
    caught_contradiction: bool = Field(default=False, description="True if the NPC caught the DETECTIVE misrepresenting a past statement.")


def npc_system_prompt(npc_id: str, trust: int, day: int, memories: list[str],
                      heard_gossip: list[str]) -> str:
    npc = NPCS[npc_id]
    secrets = "\n".join(
        f"- id '{s['id']}': {s['text']} (unlock: {s['hint']})" for s in npc["secrets"])
    mem_block = "\n".join(f"- {m}" for m in memories) if memories else "- (nothing relevant recalled)"
    gossip_block = "\n".join(f"- {g}" for g in heard_gossip) if heard_gossip else "- (none)"
    return f"""You are roleplaying {npc['name']}, {npc['role']}, in a 1947 noir murder mystery game.

SETTING: {CASE['setting']}

YOUR CHARACTER: {npc['persona']}

YOUR PUBLIC STORY: {npc['public_story']}

YOUR SECRETS (with ids and unlock conditions):
{secrets}

WHAT YOU REMEMBER (retrieved from your persistent memory — this is ground truth
for you; it includes your private knowledge, past conversations with the
detective across ALL previous sessions and days, and rumors you have heard):
{mem_block}

RUMORS YOU HEARD RECENTLY:
{gossip_block}

CURRENT STATE: It is day {day} of the investigation. Your trust toward the
detective is {trust} on a scale of -5 (hostile) to +5 (confiding).

RULES:
1. Stay in character and period. Never mention being an AI, memory systems, or games.
2. Your memory is real: if the detective claims you said something you don't
   remember saying, or contradicts what you remember, call it out — set
   caught_contradiction true and confront them in dialogue.
3. Reveal secrets ONLY per their unlock conditions (trust level, or being
   confronted with the specific fact). When a secret comes out in your dialogue,
   include its id in revealed_secrets.
4. Lies you tell must be consistent with lies you remember telling before.
5. Trust moves: politeness, honesty, and respecting your nature raise it (+1/+2);
   accusations without evidence, rudeness, and prying into sore spots lower it (-1/-2).
6. Keep dialogue tight and atmospheric — noir, not melodrama.
"""


async def npc_reply(npc_id: str, detective_line: str, trust: int, day: int,
                    memories: list[str], gossip: list[str],
                    recent_turns: list[dict]) -> NpcTurn:
    """One interrogation exchange. recent_turns = this session's chat so far."""
    system = npc_system_prompt(npc_id, trust, day, memories, gossip)
    messages: list[dict] = []
    for t in recent_turns[-10:]:
        messages.append({"role": "user", "content": t["detective"]})
        messages.append({"role": "assistant", "content": json.dumps({"dialogue": t["npc"]})})
    messages.append({"role": "user", "content": detective_line})

    turn = await _json_completion(NpcTurn, system, messages)
    if turn is None:
        turn = NpcTurn(dialogue="They look at you for a long moment and say nothing at all.")
    turn.trust_delta = max(-2, min(2, turn.trust_delta))
    valid_ids = {s["id"] for s in NPCS[npc_id]["secrets"]}
    turn.revealed_secrets = [s for s in turn.revealed_secrets if s in valid_ids]
    return turn


class GossipItem(BaseModel):
    to_npc: str = Field(description="NPC id who hears this rumor: martha|doc|sal|cap|vera")
    rumor: str = Field(description="The rumor as the hearer would receive it, phrased as hearsay: 'X told me that...' or 'Word around town is...'")
    salience: str = Field(default="low", description="'high' if scandalous/case-relevant, 'low' if mundane")


class GossipPass(BaseModel):
    items: list[GossipItem] = Field(default_factory=list)


async def generate_gossip(day: int, todays_events: list[str]) -> list[GossipItem]:
    """Night falls. The town talks. Turn today's public statements into
    rumors that spread along relationship lines."""
    from .story import RELATIONSHIPS
    if not todays_events:
        return []
    events = "\n".join(f"- {e}" for e in todays_events)
    rel = "\n".join(f"{k}: {v}" for k, v in RELATIONSHIPS.items())
    system = (
        "You simulate overnight gossip in the small town of Grayharbor, 1947, "
        "during a murder investigation. Given today's notable interrogation "
        "events, produce 3-8 rumors that would realistically spread between "
        "these NPCs (ids: martha, doc, sal, cap, vera), respecting their "
        f"relationships:\n{rel}\n\n"
        "Rumors distort slightly, as gossip does. The killer (cap) hearing "
        "that the detective is close should produce defensive rumors. Do not "
        "invent events that did not happen today. A rumor's to_npc must NOT "
        "be the person who made the original statement."
    )
    parsed = await _json_completion(
        GossipPass, system,
        [{"role": "user", "content": f"Day {day} events:\n{events}"}],
        max_tokens=1600,
    )
    return parsed.items if parsed else []


class Verdict(BaseModel):
    correct: bool = False
    narration: str = Field(default="", description="2-4 paragraph noir ending scene narrating the outcome of the accusation, second person.")
    epilogue: str = Field(default="THE FOG SETTLES", description="One-line epilogue title, e.g. 'CASE CLOSED' or 'THE WRONG MAN'.")


async def accusation_verdict(accused_id: str, threads_found: list[str],
                             evidence_summary: list[str]) -> Verdict:
    npc = NPCS[accused_id]
    is_killer = npc["is_killer"]
    strong = len(threads_found) >= 2
    outcome = (
        "The accusation is CORRECT and the evidence is strong — the killer is arrested and, "
        "faced with the threads of evidence, confesses in cold fury."
        if is_killer and strong else
        "The accusation is CORRECT but the evidence is thin — the inquest lets him slip away on doubt; a hollow victory."
        if is_killer else
        "The accusation is WRONG. An innocent person is disgraced, and the real killer sails free."
    )
    system = (
        "You write the ending scene of a 1947 noir murder mystery, in second "
        "person ('you'). Setting: " + CASE["setting"] + " The truth: " + CASE["truth"]
    )
    parsed = await _json_completion(
        Verdict, system,
        [{"role": "user", "content":
          f"The detective accuses {npc['name']} ({npc['role']}). Outcome: {outcome}\n"
          f"Evidence threads the detective uncovered: {threads_found or ['none']}\n"
          f"Key discoveries: {evidence_summary or ['very little']}"}],
        max_tokens=1400,
    )
    if parsed is None:
        parsed = Verdict(narration=outcome)
    parsed.correct = bool(is_killer and strong)
    return parsed
