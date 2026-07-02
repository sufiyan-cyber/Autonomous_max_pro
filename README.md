# ALIBI — the town that remembers

> *A detective game where the suspects have real, persistent memory.*
> Built for **"The Hangover Part AI: Where's My Context?"** — the WeMakeDevs × Cognee hackathon.

**Grayharbor, 1947.** Elias Crane — tavern owner, moneylender, the most quietly
hated man in town — is dead at the foot of the lighthouse stairs. The constable
calls it a fall. You have three days to prove it wasn't.

Five suspects. Each one has their **own Cognee-backed memory** — a private
knowledge graph seeded with everything they know, saw, and are hiding. They
remember every word you say to them, **across sessions, across days, across
restarts of the app**. Lie to the barmaid on Monday and she'll catch you on
Wednesday. Accuse the captain and by morning the whole town has heard.

---

## ⏱️ Judge this in 90 seconds

1. **Click TAKE THE CASE** — watch it seed five separate knowledge graphs on
   Cognee Cloud (one brain per suspect, ~60s).
2. **Ask Vera Webb:** *"Did the Mariposa leave her mooring the night of the
   storm?"* — her answer comes from `recall()` against her own graph: mooring
   12, log entries at 22:00, 23:00, 00:30. An evidence thread lights up.
3. **Kill the backend process. Restart it. Reload.** Ask Captain Rhodes what
   he told you earlier — he repeats his exact lie, and remembers being
   cornered with the log. **No context window survived that restart. His
   memory did.**
4. **Click END THE DAY** — `improve()` folds the day into each suspect's
   graph, rumors spread NPC→NPC along relationship lines (the killer gets
   warned the detective is close), and stale memories `forget()` away.
5. **Open THE CORKBOARD** — that force-graph is not a mockup. It's the
   suspects' actual knowledge graphs pulled live from the Cognee Cloud API,
   with testimony (and detected lies, in red) pinned on top.

Every observed behavior above is emergent from real memory — none of it is
scripted dialogue.

---

## Why this is a Cognee showcase, not just a game

Most memory demos call `remember()` and `recall()` and stop there. In ALIBI the
**entire memory lifecycle is the game mechanic**:

| Cognee API | Game mechanic |
|---|---|
| `remember()` | Every interrogation exchange becomes the suspect's memory — their dataset, their session. Rumors are remembered as hearsay. |
| `recall()` | Suspects answer *from what they actually remember* — dossier, past conversations, gossip. If you misquote them, they catch the contradiction, because the recall says otherwise. |
| `improve()` | **Nightfall.** The day's interrogation sessions are bridged into each suspect's knowledge graph, and the "gossip pass" spreads rumors between NPCs along relationship lines. |
| `forget()` | **Memory decay.** Low-salience details fade after two in-game days. Witnesses literally forget — you can race the decay, or wait for it. |

And the game's **detective corkboard is the knowledge graph itself** — nodes
and edges exported from Cognee, red-string testimony overlaid on top.

The AI never loses context. That's not a feature of this game. It *is* the game.

## The killer demo moment

1. Interrogate Captain Rhodes. He tells you he rode out the storm at sea.
2. **Close the app. Kill the server. Reopen it.**
3. Ask him: *"Remind me — where were you that night?"*
4. He repeats the same lie, in the same words he remembers using — because his
   alibi lives in a real memory store, not a context window.
5. Then show him the harbormaster's log, and watch him remember that too.

## Architecture

```
┌────────────────┐     ┌──────────────────┐     ┌───────────────────────────┐
│  Next.js noir  │────▶│  FastAPI engine   │────▶│  Cognee Cloud             │
│  UI + corkboard│     │  game state,      │     │  5 NPC memory datasets    │
│  (force graph) │◀────│  gossip, decay    │◀────│  remember/recall/         │
└────────────────┘     │        │          │     │  improve/forget           │
                       │        ▼          │     └───────────────────────────┘
                       │  Groq (Llama 3.3) │
                       │  NPC dialogue +   │
                       │  structured claims│
                       └──────────────────┘
```

- **One Cognee dataset per suspect** (`npc_martha`, `npc_cap`, …) — five
  separate brains, seeded with private dossiers at game start.
- **Session memory per day per suspect** (`day2_cap`) — bridged into the
  persistent graph by `improve()` at nightfall.
- **Structured NPC turns** — every reply extracts the claims the suspect just
  made (subject/predicate/object + whether they know it's a lie), which flow
  into both Cognee and the corkboard.

## How to play

You are the detective. **Three days. Eight questions a day. One accusation.**

- **Interrogate** any of the five suspects in free-form dialogue — earn trust,
  press on details, or bluff (careful: they remember, and they catch
  misquotes).
- **End the day** to trigger nightfall — sessions become long-term memory,
  gossip spreads, details fade.
- **Accuse** when you're ready. You get exactly one shot, and you need at
  least two evidence threads to make it stick.

## The mystery is actually solvable

Three independent evidence threads convict the killer — each locked behind a
different suspect's memory and trust:

- **Motive** — someone saw the blackmail payments cross the bar.
- **The log** — someone's records prove an alibi is impossible.
- **The witness** — someone was on the lighthouse path that night, and is lying
  about why.

You need at least two threads to make the accusation stick. Accuse without
evidence and the inquest lets the killer walk.

## Run it

```bash
# backend
cd backend
pip install -r requirements.txt
cp .env.example .env        # add your keys (see below)
uvicorn app.main:app --port 8000

# frontend
cd frontend
npm install
npm run dev                 # → http://localhost:3000
```

`.env` settings:

```ini
MEMORY_BACKEND=cloud                     # cloud | local | mock
COGNEE_CLOUD_URL=https://<tenant>.aws.cognee.ai
COGNEE_CLOUD_API_KEY=...                 # platform.cognee.ai → API Keys
GROQ_API_KEY=...                         # NPC dialogue (Llama 3.3 70B)
ALIBI_MODEL=llama-3.3-70b-versatile
```

- `cloud` — Cognee Cloud (the hackathon track this targets)
- `local` — self-hosted cognee
- `mock` — keyless dev mode (keyword recall; for UI work only)

## Stack

Next.js · FastAPI · **Cognee Cloud** (memory: vector + graph) · Groq / Llama 3.3
70B (dialogue) · react-force-graph (corkboard)

No bolted-on vector DB. No separate graph DB. Cognee *is* the memory.

---

*Built  for the WeMakeDevs × Cognee hackathon*
