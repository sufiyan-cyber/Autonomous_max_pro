"""ALIBI backend — FastAPI routes."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import engine, config

app = FastAPI(title="ALIBI", description="A detective game where the NPCs never forget. Powered by Cognee.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InterrogateBody(BaseModel):
    npc_id: str
    line: str


class AccuseBody(BaseModel):
    npc_id: str


@app.get("/api/health")
async def health():
    return {"ok": True, "memory_backend": config.MEMORY_BACKEND, "model": config.ALIBI_MODEL}


@app.get("/api/state")
async def state():
    return engine.public_state()


@app.post("/api/game/new")
async def new_game():
    return await engine.new_game()


@app.post("/api/interrogate")
async def interrogate(body: InterrogateBody):
    try:
        return await engine.interrogate(body.npc_id, body.line.strip())
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/day/end")
async def end_day():
    try:
        return await engine.end_day()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/accuse")
async def accuse(body: AccuseBody):
    try:
        return await engine.accuse(body.npc_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/corkboard")
async def corkboard():
    return await engine.corkboard()


@app.get("/api/session/{npc_id}")
async def session(npc_id: str):
    s = engine.load_state()
    return {"turns": s["sessions"].get(npc_id, [])}
