# config.py —— 共用設定
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# === Embedding 與 Chroma 設定 ===
PERSIST_DIR = BASE_DIR / "chroma_db_openai_small"
COLLECTION_NAME = "esg_and_news"
EMBED_MODEL = "text-embedding-3-small"
