"""LangGraph state types for the ingestion and query pipelines."""
from typing import List, Optional
from typing_extensions import TypedDict


class IngestionState(TypedDict):
    doc_id: str
    doc_name: str
    file_path: str
    source_path: str
    raw_text: str
    chunks: List[str]
    embeddings: List[List[float]]
    chunks_count: int
    status: str           # pending | extracting | chunking | embedding | ingesting | done | error
    error: Optional[str]


class QueryState(TypedDict):
    question: str
    doc_id_filter: Optional[str]
    retrieved_docs: List[dict]
    reranked_docs: List[dict]
    answer: str
    sources: List[dict]
    status: str           # pending | retrieving | reranking | generating | done | error
    error: Optional[str]
