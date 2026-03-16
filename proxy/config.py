import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "4"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen2.5:7b")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
