from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── OpenRouter ────────────────────────────────────────────────────────────
    openrouter_api_key: str = "mock-or-dev-key"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "https://localhost"
    openrouter_app_name: str = "NaturalLangData"

    openai_api_key: str = "mock-or-dev-key"
    openai_base_url: str = "https://api.openai.com/v1"

    chat_model: str = "openai/gpt-4o-mini"
    embedding_model: str = "qwen/qwen3-embedding-8b"
    rerank_model: str = "cohere/rerank-v3.5"
    vision_model: str = "openai/gpt-4o-mini"
    embedding_dim: int = 4096

    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "pdf_chunks"
    qdrant_bi_collection: str = "bi_schemas"

    pdf_dir: Path = Path("data/pdfs")
    tabular_db_path: Path = Path("data/index/tabular.db")
    sqlite_db_path: Path = Path("data/operational.db")
    analytics_data_dir: Path = Path("data/analytics")

    tabular_row_batch_size: int = 25
    tabular_max_rows_for_embedding: int = 1000
    tabular_max_columns_per_row: int = 14
    tabular_max_cell_chars: int = 120

    chunk_breakpoint_threshold: float = 0.78
    chunk_min_size: int = 100
    chunk_max_size: int = 1500

    pdf_vision_min_text_chars: int = 80

    retrieval_top_k: int = 20
    rerank_top_n: int = 5
    max_reflections: int = 2


def get_settings() -> Settings:
    return Settings()
