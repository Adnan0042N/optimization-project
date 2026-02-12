import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DAZI_API_KEY: str = os.getenv("DAZI_API_KEY", "")
    DAZI_BASE_URL: str = os.getenv("DAZI_BASE_URL", "https://api.chatanywhere.tech")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4.1-nano")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    MEMORY_DIR: str = os.getenv("MEMORY_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "memory"))
    CACHE_DB: str = os.getenv("CACHE_DB", os.path.join(os.path.dirname(__file__), "..", "data", "memory", "cache.db"))
    MAX_TREE_DEPTH: int = 5
    CACHE_TTL_DAYS: int = 7
    SYNTHESIS_DIFFICULTY: str = "medium"
    SYNTHESIS_MAX_ATTEMPTS: int = 3
    TOP_K_EXACT: int = 3
    TOP_K_VECTOR: int = 5

config = Config()
