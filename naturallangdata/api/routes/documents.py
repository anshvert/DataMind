import asyncio
from pathlib import Path
import re
from typing import List
import uuid

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from naturallangdata.agents.state import IngestionState
from naturallangdata.api.dependencies import DocumentExtractorDep, IngestionGraphDep, QdrantDep, SettingsDep
from naturallangdata.models.schemas import DocumentInfo, UploadResponse

router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".csv", ".xlsx", ".parquet"}


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    request: Request = None,
    settings: SettingsDep = None,
    ingestion_graph: IngestionGraphDep = None,
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, CSV, XLSX, and Parquet files are accepted")

    doc_id = uuid.uuid4().hex
    raw_stem = Path(file.filename).stem
    clean_stem = re.sub(r"[^a-zA-Z0-9_]+", "_", raw_stem).strip("_") or f"file_{doc_id[:8]}"

    content = await file.read()

    if suffix in (".parquet", ".csv"):
        analytics_dir: Path = settings.analytics_data_dir
        analytics_dir.mkdir(parents=True, exist_ok=True)
        save_path = analytics_dir / f"{clean_stem}{suffix}"
        save_path.write_bytes(content)

        if request and hasattr(request.app.state, "schema_indexer"):
            request.app.state.schema_indexer.index_all()

        return UploadResponse(
            doc_id=doc_id,
            name=clean_stem,
            chunks_indexed=1,
            message="Analytical dataset ingested for DuckDB and Schema RAG",
        )

    pdf_dir: Path = settings.pdf_dir
    pdf_dir.mkdir(parents=True, exist_ok=True)
    save_path = pdf_dir / f"{doc_id}{suffix}"
    save_path.write_bytes(content)

    initial_state: IngestionState = {
        "doc_id": doc_id,
        "doc_name": clean_stem,
        "file_path": str(save_path),
        "source_path": str(save_path),
        "raw_text": "",
        "chunks": [],
        "embeddings": [],
        "chunks_count": 0,
        "status": "pending",
        "error": None,
    }

    final_state: IngestionState = await asyncio.to_thread(
        ingestion_graph.invoke, initial_state
    )

    if final_state.get("status") == "error":
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail=final_state.get("error", "Ingestion pipeline failed"),
        )

    return UploadResponse(
        doc_id=doc_id,
        name=clean_stem,
        chunks_indexed=final_state.get("chunks_count", 0),
        message="Document ingested successfully",
    )


@router.get("/", response_model=List[DocumentInfo])
def list_documents(qdrant: QdrantDep):
    return [DocumentInfo(**d) for d in qdrant.list_documents()]


@router.delete("/{doc_id}", status_code=200)
def delete_document(
    doc_id: str,
    settings: SettingsDep,
    qdrant: QdrantDep,
    document_extractor: DocumentExtractorDep,
):
    for file_path in settings.pdf_dir.glob(f"{doc_id}.*"):
        file_path.unlink(missing_ok=True)
    qdrant.delete_document(doc_id)
    document_extractor.delete_document(doc_id)
    return {"message": f"Document {doc_id} deleted"}
