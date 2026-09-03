"""Executive summary narrator node synthesizing plain-English business insights."""
import json
from typing import Any, Callable, Dict, List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from naturallangdata.agents.bi_state import BIAgentState
from naturallangdata.core.config import Settings


def fallback_summary_generator(query: str, data: List[Dict[str, Any]]) -> str:
    """Generate deterministic plain-English summary from result rows."""
    if not data:
        return "No data was returned for your query."

    first_row = data[0]
    keys = list(first_row.keys())

    metric_keys = [
        k for k in keys
        if isinstance(first_row.get(k), (int, float))
        and not any(term in k.lower() for term in ["year", "id", "code", "quarter"])
    ]
    dim_keys = [k for k in keys if k not in metric_keys]

    if not metric_keys:
        return f"Found {len(data)} matching records for '{query}'."

    primary_metric = metric_keys[0]
    total_val = sum(float(r.get(primary_metric) or 0) for r in data)
    metric_label = primary_metric.replace("_", " ")

    if dim_keys and len(data) > 1:
        dim_key = dim_keys[0]
        top_row = max(data, key=lambda r: float(r.get(primary_metric) or 0))
        top_name = str(top_row.get(dim_key, "Top item"))
        top_val = float(top_row.get(primary_metric) or 0)
        pct = (top_val / total_val * 100) if total_val else 0

        return (
            f"Total {metric_label} across {len(data)} {dim_key.replace('_', ' ')}s is {total_val:,.2f}. "
            f"The largest contributor is {top_name} with {top_val:,.2f} ({pct:.1f}% of total)."
        )

    return f"Total {metric_label} is {total_val:,.2f} across {len(data)} result rows."


def make_bi_narrator_node(settings: Settings) -> Callable[[BIAgentState], BIAgentState]:
    """Create an executive narrative synthesis node wired to the configured LLM."""
    api_key = settings.openrouter_api_key if settings.openrouter_api_key != "mock-or-dev-key" else settings.openai_api_key
    base_url = settings.openrouter_base_url if settings.openrouter_api_key != "mock-or-dev-key" else settings.openai_base_url
    has_real_key = bool(api_key and api_key != "mock-or-dev-key")

    llm: ChatOpenAI | None = None
    if has_real_key:
        try:
            default_headers = {}
            if "openrouter.ai" in base_url:
                default_headers = {
                    "HTTP-Referer": settings.openrouter_site_url,
                    "X-Title": settings.openrouter_app_name,
                }
            llm = ChatOpenAI(
                model=settings.chat_model,
                api_key=api_key,
                base_url=base_url,
                temperature=0.2,
                default_headers=default_headers or None,
            )
        except Exception:
            llm = None

    def narrator_node(state: BIAgentState) -> BIAgentState:
        query = state.get("query", "")
        sql = state.get("generated_sql", "")
        data = state.get("data_result", [])
        traces: List[Dict[str, Any]] = list(state.get("trace_steps", []))

        if not data:
            summary = "No matching records were found for your question."
        elif llm:
            system_prompt = (
                "You are an executive Business Intelligence Analyst. "
                "Based on the user's natural language question, the executed SQL query, and the data results, "
                "provide a concise, high-value 2-sentence executive summary directly answering the question. "
                "State key figures, total metrics, primary contributors, and meaningful takeaways clearly. "
                "Do NOT mention SQL syntax, technical details, or table names."
            )
            data_sample = data[:15]
            user_message = (
                f"User Question: {query}\n"
                f"Executed SQL: {sql}\n"
                f"Data Results ({len(data)} rows, showing sample):\n{json.dumps(data_sample, default=str)}"
            )

            try:
                response = llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_message),
                ])
                summary = response.content.strip() if hasattr(response, "content") else str(response).strip()
            except Exception as exc:
                print(f"[QueryMind/BI Narrator] LLM narration error: {exc}. Using fallback...", flush=True)
                summary = fallback_summary_generator(query, data)
        else:
            summary = fallback_summary_generator(query, data)

        print(f"\n[QueryMind/BI Narrator] Executive Summary:\n{summary}\n", flush=True)

        traces.append({
            "node": "narrator",
            "message": "Synthesized executive business summary",
            "summary": summary,
        })

        return {
            **state,
            "summary": summary,
            "trace_steps": traces,
        }

    return narrator_node
