import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# "cloud"  -> Cognee Cloud via cognee.serve()   (Best Use of Cognee Cloud track)
# "local"  -> self-hosted cognee (needs LLM_API_KEY for cognee's own pipeline)
# "mock"   -> in-process memory store, no keys needed (UI development only)
MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "mock").lower()

COGNEE_CLOUD_URL = os.getenv("COGNEE_CLOUD_URL", "")
COGNEE_CLOUD_API_KEY = os.getenv("COGNEE_CLOUD_API_KEY", "")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ALIBI_MODEL = os.getenv("ALIBI_MODEL", "llama-3.3-70b-versatile")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "game_state.json"
MOCK_MEMORY_FILE = DATA_DIR / "mock_memory.json"
