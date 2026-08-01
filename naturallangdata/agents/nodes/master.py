"""Master / supervisor nodes — validate state and initialise the pipeline."""
from naturallangdata.agents.state import IngestionState, QueryState


def ingestion_master_node(state: IngestionState) -> IngestionState:
    """Validate inputs and mark the pipeline as started."""
    if not state.get("file_path"):
        return {**state, "status": "error", "error": "file_path is required"}
    if not state.get("doc_id"):
        return {**state, "status": "error", "error": "doc_id is required"}
    return {**state, "status": "extracting", "error": None}


def query_master_node(state: QueryState) -> QueryState:
    """Validate inputs and mark the pipeline as started."""
    question = (state.get("question") or "").strip()
    if not question:
        return {**state, "status": "error", "error": "question cannot be empty"}
    return {**state, "question": question, "status": "retrieving", "error": None}
