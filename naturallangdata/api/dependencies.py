"""FastAPI dependency providers that pull singletons off app.state."""
from typing import Annotated

from fastapi import Depends, Request

from naturallangdata.core.config import Settings
from naturallangdata.services.document_extractor import DocumentExtractionService
from naturallangdata.services.embeddings import EmbeddingsService
from naturallangdata.services.qdrant_service import QdrantService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_embeddings(request: Request) -> EmbeddingsService:
    return request.app.state.embeddings


def get_qdrant(request: Request) -> QdrantService:
    return request.app.state.qdrant


def get_ingestion_graph(request: Request):
    return request.app.state.ingestion_graph


def get_query_graph(request: Request):
    return request.app.state.query_graph


def get_document_extractor(request: Request) -> DocumentExtractionService:
    return request.app.state.document_extractor


# Typed aliases for route signatures
SettingsDep = Annotated[Settings, Depends(get_settings)]
EmbeddingsDep = Annotated[EmbeddingsService, Depends(get_embeddings)]
QdrantDep = Annotated[QdrantService, Depends(get_qdrant)]
IngestionGraphDep = Annotated[object, Depends(get_ingestion_graph)]
QueryGraphDep = Annotated[object, Depends(get_query_graph)]
DocumentExtractorDep = Annotated[DocumentExtractionService, Depends(get_document_extractor)]
