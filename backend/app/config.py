import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _clean(name: str, default: str = "") -> str:
    """Env values pasted into hosting dashboards often pick up stray
    whitespace or wrapping quotes — sanitize before use."""
    return os.getenv(name, default).strip().strip('"').strip("'").strip()

# "cloud"  -> Cognee Cloud via cognee.serve()   (Best Use of Cognee Cloud track)
# "local"  -> self-hosted cognee (needs LLM_API_KEY for cognee's own pipeline)
# "mock"   -> in-process memory store, no keys needed (UI development only)
MEMORY_BACKEND = _clean("MEMORY_BACKEND", "mock").lower()

COGNEE_CLOUD_URL = _clean("COGNEE_CLOUD_URL").rstrip("/")
COGNEE_CLOUD_API_KEY = _clean("COGNEE_CLOUD_API_KEY")

GROQ_API_KEY = _clean("GROQ_API_KEY")
ALIBI_MODEL = _clean("ALIBI_MODEL", "llama-3.3-70b-versatile")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "game_state.json"
MOCK_MEMORY_FILE = DATA_DIR / "mock_memory.json"
