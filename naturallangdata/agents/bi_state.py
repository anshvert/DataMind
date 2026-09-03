"""State definitions for the Conversational BI LangGraph workflow."""
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class BIAgentState(TypedDict):
    """Workflow state holding conversational BI query context and execution artifacts."""

    query: str
    target_engine: str
    retrieved_schemas: List[Dict[str, Any]]
    generated_sql: str
    sql_valid: bool
    error_trace: Optional[str]
    retry_count: int
    data_result: List[Dict[str, Any]]
    chart_spec: Dict[str, Any]
    trace_steps: List[Dict[str, Any]]
    chat_history: List[Dict[str, str]]
    summary: Optional[str]
