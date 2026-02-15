import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
    NVIDIA_BASE_URL: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "z-ai/glm5")
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
