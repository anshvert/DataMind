"""Index profiled database schemas into Redis and Qdrant."""
import logging
from typing import Any, Dict, List

from naturallangdata.core.config import Settings
from naturallangdata.core.qdrant_schema_store import QdrantSchemaStore
from naturallangdata.core.redis_cache import RedisCache
from naturallangdata.services.profiler import SchemaProfiler

logger = logging.getLogger(__name__)


class SchemaIndexer:
    """Synchronize discovered schemas into Redis cache and Qdrant vector store."""

    def __init__(
        self,
        settings: Settings,
        redis_cache: RedisCache,
        qdrant_store: QdrantSchemaStore,
    ) -> None:
        self._settings = settings
        self._redis = redis_cache
        self._qdrant = qdrant_store
        self._profiler = SchemaProfiler(settings)

    def _build_description(self, table: Dict[str, Any]) -> str:
        col_snippets: List[str] = []
        for col in table.get("column_details", []):
            name = col["name"]
            col_type = col["type"]
            samples = col.get("samples", [])
            samples_str = f" (e.g. {', '.join(str(s) for s in samples[:3])})" if samples else ""
            col_snippets.append(f"{name} [{col_type}]{samples_str}")

        return (
            f"Table '{table['table_name']}' on engine '{table['engine']}'. "
            f"Attributes: {', '.join(col_snippets)}."
        )

    def index_all(self) -> List[Dict[str, Any]]:
        """Profile and sync all schemas into Redis and Qdrant."""
        tables = self._profiler.profile_all()

        for table in tables:
            engine = table["engine"]
            t_name = table["table_name"]
            description = self._build_description(table)
            table["description"] = description

            redis_key = f"schema:{engine}:{t_name}"
            self._redis.set(redis_key, table)

            self._qdrant.upsert_schema(
                table_name=t_name,
                engine=engine,
                description=description,
                columns=table["columns"],
                ddl=table["ddl"],
            )

        return tables
