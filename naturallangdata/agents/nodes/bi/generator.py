"""SQL generation node using LLM with conversational context and deterministic fallback."""
import re
from typing import Any, Callable, Dict, List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from naturallangdata.agents.bi_state import BIAgentState
from naturallangdata.core.config import Settings


def clean_sql(raw_sql: str) -> str:
    """Extract raw SQL code from potential markdown code fences."""
    cleaned = raw_sql.strip()
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    cleaned = re.sub(r";\s*$", "", cleaned).strip()
    return cleaned


def fallback_sql_generator(query: str, schemas: List[Dict[str, Any]], engine: str) -> str:
    """Deterministic fallback query builder for offline or test execution."""
    q = query.lower()

    if "customer" in q or (engine == "sqlite" and "order" not in q):
        if "active" in q:
            if "na" in q:
                return "SELECT customer_id, full_name, signup_date, region FROM customers WHERE is_active = 1 AND region = 'NA'"
            return "SELECT region, COUNT(*) AS active_count FROM customers WHERE is_active = 1 GROUP BY region"
        return "SELECT customer_id, full_name, signup_date, region FROM customers LIMIT 10"

    if "order" in q:
        return "SELECT status, COUNT(*) AS order_count, SUM(total_amount) AS revenue FROM orders GROUP BY status"

    if "arr" in q or "revenue" in q:
        if "emea" in q:
            return "SELECT quarter, gross_arr, churned_arr, net_arr FROM quarterly_arr WHERE region = 'EMEA' ORDER BY quarter"
        if "region" in q:
            return "SELECT region, SUM(gross_arr) AS total_gross_arr, SUM(net_arr) AS total_net_arr FROM quarterly_arr GROUP BY region ORDER BY total_net_arr DESC"
        return "SELECT quarter, region, gross_arr, net_arr FROM quarterly_arr ORDER BY quarter LIMIT 10"

    if "inventory" in q or "stock" in q or "product" in q or "sku" in q:
        if "top" in q or "value" in q:
            return "SELECT product_name, stock_count, unit_price, (stock_count * unit_price) AS total_value FROM product_inventory ORDER BY total_value DESC LIMIT 5"
        return "SELECT sku, product_name, category, stock_count, unit_price FROM product_inventory LIMIT 10"

    if "churn" in q:
        return "SELECT reason, COUNT(*) AS count, SUM(loss_amount) AS total_loss FROM churn_events GROUP BY reason"

    if schemas:
        first_table = schemas[0].get("table_name")
        cols = schemas[0].get("columns", ["*"])
        sel_cols = ", ".join(cols[:4]) if cols else "*"
        return f"SELECT {sel_cols} FROM \"{first_table}\" LIMIT 10"

    if engine == "sqlite":
        return "SELECT customer_id, full_name, signup_date, region FROM customers LIMIT 10"
    return "SELECT quarter, region, gross_arr, net_arr FROM quarterly_arr LIMIT 10"


def make_bi_generator_node(settings: Settings) -> Callable[[BIAgentState], BIAgentState]:
    """Create a generator node instance wired to the configured LLM."""
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
                temperature=0.0,
                default_headers=default_headers or None,
            )
        except Exception:
            llm = None

    def generator_node(state: BIAgentState) -> BIAgentState:
        query = state.get("query", "")
        schemas = state.get("retrieved_schemas", [])
        engine = state.get("target_engine", "sqlite")
        error_trace = state.get("error_trace")
        previous_sql = state.get("generated_sql", "")
        traces: List[Dict[str, Any]] = list(state.get("trace_steps", []))
        chat_history = state.get("chat_history", [])

        schema_context = "\n\n".join(
            f"Table: {s.get('table_name')}\nEngine: {s.get('engine')}\nDDL:\n{s.get('ddl')}"
            for s in schemas
        )

        history_lines = []
        for item in chat_history[-4:]:
            r = item.get("role", "user").capitalize()
            t = item.get("text", "")
            history_lines.append(f"{r}: {t}")
        history_context = "\n".join(history_lines)

        if llm:
            system_prompt = (
                f"You are a Senior Business Intelligence and Data Analytics Engineer writing SQL for {engine.upper()}.\n"
                "Return ONLY a single valid SELECT SQL statement.\n"
                "Do NOT include markdown backticks (```sql) or conversational explanations.\n"
                "Do NOT use DROP, ALTER, INSERT, UPDATE, DELETE, or multiple statements.\n"
                "Use ONLY the tables and columns provided in the schema context below.\n"
                "CRITICAL BUSINESS ANALYTICS GUIDELINES:\n"
                "- Prioritize aggregated analytical SQL queries suitable for reporting and data visualization.\n"
                "- When querying metrics, expenditures, revenue, stock, or quantities, ALWAYS aggregate using SUM(), AVG(), or COUNT() with GROUP BY on the key categorical dimension(s) (e.g. sector, class, region, category, quarter) and ORDER BY the aggregated metric DESC.\n"
                "- Do NOT return unaggregated duplicate rows or raw row-level details unless the user explicitly asks for 'raw records' or 'all rows'.\n"
                "- If column or table names contain special characters, spaces, or hyphens, wrap them in double quotes.\n\n"
                f"Schema Context:\n{schema_context}"
            )

            user_message = ""
            if history_context:
                user_message += f"Recent Conversation History:\n{history_context}\n\n"
            user_message += f"Current User Question: {query}"

            if error_trace:
                user_message += (
                    f"\n\nPrevious SQL Attempt:\n{previous_sql}\n\n"
                    f"Previous AST / Execution Error:\n{error_trace}\n\n"
                    "Fix the query so that it resolves this error strictly adhering to the schema."
                )

            print(f"\n[QueryMind/BI Generator] Model: {settings.chat_model} | Dialect: {engine.upper()}", flush=True)
            print(f"[QueryMind/BI Generator] User Prompt:\n{user_message}", flush=True)

            try:
                response = llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_message),
                ])
                content = response.content if hasattr(response, "content") else str(response)
                print(f"[QueryMind/BI Generator] Raw LLM Response:\n{content}", flush=True)
                generated_sql = clean_sql(content)
                print(f"[QueryMind/BI Generator] Cleaned SQL:\n{generated_sql}", flush=True)
            except Exception as exc:
                print(f"[QueryMind/BI Generator] LLM generation failed: {exc}. Using fallback...", flush=True)
                generated_sql = fallback_sql_generator(query, schemas, engine)
        else:
            generated_sql = fallback_sql_generator(query, schemas, engine)
            print(f"[QueryMind/BI Generator] Offline Fallback SQL:\n{generated_sql}", flush=True)

        traces.append({
            "node": "generator",
            "message": f"Synthesized SQL query for {engine}",
            "sql": generated_sql,
        })

        return {
            **state,
            "generated_sql": generated_sql,
            "trace_steps": traces,
        }

    return generator_node
