"""Reflection node for error self-correction and retry loop management."""
from typing import Any, Callable, Dict, List
from naturallangdata.agents.bi_state import BIAgentState


def make_bi_reflection_node(max_retries: int = 2) -> Callable[[BIAgentState], BIAgentState]:
    """Create a reflection node instance managing retry budget and error context."""

    def reflection_node(state: BIAgentState) -> BIAgentState:
        current_retries = state.get("retry_count", 0)
        error = state.get("error_trace", "Unknown error")
        traces: List[Dict[str, Any]] = list(state.get("trace_steps", []))

        next_retry = current_retries + 1
        traces.append({
            "node": "reflection",
            "message": f"Reflection cycle {next_retry}/{max_retries}: Adjusting SQL for error '{error}'",
            "retry_count": next_retry,
            "error": error,
        })

        return {
            **state,
            "retry_count": next_retry,
            "trace_steps": traces,
        }

    return reflection_node
