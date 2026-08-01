"""Application entry point.

Services and graphs are initialised once in the lifespan context manager and
stored on app.state so every request re-uses the same singletons.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from naturallangdata.agents.ingestion_graph import build_ingestion_graph
from naturallangdata.agents.query_graph import build_query_graph
from naturallangdata.api.routes import documents, health, query
from naturallangdata.core.config import get_settings
from naturallangdata.services.document_extractor import DocumentExtractionService
from naturallangdata.services.embeddings import EmbeddingsService
from naturallangdata.services.pdf_extractor import PDFExtractionService
from naturallangdata.services.qdrant_service import QdrantService
from naturallangdata.services.reranker import OpenRouterRerankerService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    embeddings = EmbeddingsService(settings)
    pdf_extractor = PDFExtractionService(settings)
    document_extractor = DocumentExtractionService(pdf_extractor, settings)
    qdrant = QdrantService(settings)
    reranker = OpenRouterRerankerService(settings)
    qdrant.ensure_collection()

    app.state.settings = settings
    app.state.embeddings = embeddings
    app.state.document_extractor = document_extractor
    app.state.qdrant = qdrant
    app.state.reranker = reranker
    app.state.ingestion_graph = build_ingestion_graph(settings, embeddings, qdrant, document_extractor)
    app.state.query_graph = build_query_graph(settings, embeddings, qdrant, reranker)

    yield


def create_app() -> FastAPI:
    web_static_dir = Path(__file__).resolve().parent / "naturallangdata" / "web" / "static"
    application = FastAPI(
        title="NaturalLangData — PDF RAG API",
        version="0.2.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.mount("/static", StaticFiles(directory=web_static_dir), name="static")
    application.include_router(health.router, tags=["health"])
    application.include_router(documents.router, prefix="/documents", tags=["documents"])
    application.include_router(query.router, prefix="/query", tags=["query"])
    return application


app = create_app()
