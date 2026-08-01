from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── OpenRouter ────────────────────────────────────────────────────────────
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "https://localhost"
    openrouter_app_name: str = "NaturalLangData"

    # ── Models ────────────────────────────────────────────────────────────────
    chat_model: str = "openai/gpt-4o-mini"
    embedding_model: str = "qwen/qwen3-embedding-8b"
    rerank_model: str = "cohere/rerank-v3.5"
    vision_model: str = "openai/gpt-4o-mini"
    # Dimension of the embedding model output vectors.
    # qwen/qwen3-embedding-8b default output dim is 4096.
    embedding_dim: int = 4096

    # ── Qdrant ────────────────────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "pdf_chunks"

    # ── Storage ───────────────────────────────────────────────────────────────
    pdf_dir: Path = Path("data/pdfs")
    tabular_db_path: Path = Path("data/index/tabular.db")

    # ── Tabular extraction / indexing (CSV, XLSX) ────────────────────────────
    tabular_row_batch_size: int = 25
    tabular_max_rows_for_embedding: int = 1000
    tabular_max_columns_per_row: int = 14
    tabular_max_cell_chars: int = 120

    # ── Semantic chunking ─────────────────────────────────────────────────────
    # Cosine similarity below this threshold creates a new chunk boundary.
    # Higher values are stricter and produce more/smaller chunks.
    chunk_breakpoint_threshold: float = 0.78
    chunk_min_size: int = 100
    chunk_max_size: int = 1500

    # ── PDF image-text extraction fallback ───────────────────────────────────
    # If a page has less text than this threshold, we treat it as likely scanned
    # or image-heavy and run vision extraction on the rendered page image.
    pdf_vision_min_text_chars: int = 80

    # ── Retrieval / reranking ─────────────────────────────────────────────────
    retrieval_top_k: int = 20
    rerank_top_n: int = 5


def get_settings() -> Settings:
    return Settings()
