from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from naturallangdata.api.dependencies import QdrantDep
from naturallangdata.models.schemas import HealthResponse

router = APIRouter()


@router.get("/")
def root():
    html_path = Path(__file__).resolve().parents[2] / "web" / "index.html"
    return FileResponse(html_path)


@router.get("/health", response_model=HealthResponse)
def health(qdrant: QdrantDep):
    return HealthResponse(status="ok", qdrant=qdrant.health())
