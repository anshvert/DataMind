"""Domain schemas shared across the API and agents."""
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    doc_id: str
    name: str


class UploadResponse(BaseModel):
    doc_id: str
    name: str
    chunks_indexed: int
    message: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    doc_id: Optional[str] = Field(None, description="Limit search to a single document")


class SourceChunk(BaseModel):
    doc_id: str
    doc_name: str
    text: str
    score: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[SourceChunk]


class HealthResponse(BaseModel):
    status: str
    qdrant: str
