"""Query execution node targeting SQLite or DuckDB engines."""
from typing import Any, Callable, Dict, List

from naturallangdata.agents.bi_state import BIAgentState
from naturallangdata.core.config import Settings
from naturallangdata.services.executor import QueryEngine


def make_bi_executor_node(settings: Settings) -> Callable[[BIAgentState], BIAgentState]:
    """Create an executor node instance."""
    engine_runner = QueryEngine(settings)

    def executor_node(state: BIAgentState) -> BIAgentState:
        sql = state.get("generated_sql", "")
        engine = state.get("target_engine", "sqlite")
        traces: List[Dict[str, Any]] = list(state.get("trace_steps", []))

        print(f"\n[QueryMind/BI Executor] Executing query on {engine.upper()}:\n{sql}", flush=True)

        try:
            results = engine_runner.execute(sql, engine)
            print(f"[QueryMind/BI Executor] Success: {len(results)} rows returned", flush=True)
            traces.append({
                "node": "executor",
                "message": f"Executed query successfully on {engine}. Returned {len(results)} rows.",
                "row_count": len(results),
            })
            return {
                **state,
                "data_result": results,
                "error_trace": None,
                "trace_steps": traces,
            }
        except Exception as exc:
            err_msg = f"Execution error on {engine}: {exc}"
            print(f"[QueryMind/BI Executor] Failed: {err_msg}", flush=True)
            traces.append({
                "node": "executor",
                "message": err_msg,
                "error": err_msg,
            })
            return {
                **state,
                "sql_valid": False,
                "error_trace": err_msg,
                "trace_steps": traces,
            }

    return executor_node
