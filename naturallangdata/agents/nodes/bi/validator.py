"""Deterministic AST validation node using sqlglot."""
from typing import Any, Callable, Dict, List, Set
import sqlglot
from sqlglot import exp

from naturallangdata.agents.bi_state import BIAgentState
from naturallangdata.core.redis_cache import RedisCache

FORBIDDEN_EXP_TYPES = (
    exp.Drop,
    exp.Alter,
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Command,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
)


def validate_sql_ast(
    sql_query: str,
    dialect: str,
    verified_schemas: Dict[str, Dict[str, Any]],
) -> tuple[bool, str | None]:
    """Inspect query AST for security constraints and verified table/column schema presence."""
    if not sql_query or not sql_query.strip():
        return False, "Query is empty"

    try:
        statements = [s for s in sqlglot.parse(sql_query, read=dialect) if s is not None]
    except Exception as exc:
        return False, f"SQL syntax parsing failure: {exc}"

    if len(statements) != 1:
        return False, f"Forbidden multi-statement execution detected ({len(statements)} statements)"

    tree = statements[0]

    for forbidden in FORBIDDEN_EXP_TYPES:
        if tree.find(forbidden):
            return False, f"Forbidden non-SELECT DDL/DML expression detected: {forbidden.__name__}"

    if not isinstance(tree, (exp.Select, exp.Union)):
        return False, f"Root AST node must be a SELECT or UNION expression, got {type(tree).__name__}"

    ctes: Set[str] = set()
    with_exp = tree.args.get("with")
    if with_exp:
        for cte in with_exp.expressions:
            if cte.alias:
                ctes.add(cte.alias.lower())

    verified_tables = {k.lower(): [c.lower() for c in v.get("columns", [])] for k, v in verified_schemas.items()}
    engine_tables = {
        k.lower(): v.get("engine", "").lower()
        for k, v in verified_schemas.items()
        if v.get("engine")
    }

    referenced_tables: Set[str] = set()
    for table_exp in tree.find_all(exp.Table):
        t_name = table_exp.name.lower()
        if t_name and t_name not in ctes:
            referenced_tables.add(t_name)

    for t_name in referenced_tables:
        if verified_tables and t_name not in verified_tables:
            return False, f"Referenced table '{t_name}' does not exist in verified schemas ({list(verified_tables.keys())})"
        if dialect in ("sqlite", "duckdb") and t_name in engine_tables:
            expected_engine = engine_tables[t_name]
            if expected_engine != dialect:
                return False, f"Table '{t_name}' is for engine '{expected_engine}', not '{dialect}'"

    defined_aliases: Set[str] = {a.alias.lower() for a in tree.find_all(exp.Alias) if a.alias}

    for col_exp in tree.find_all(exp.Column):
        c_name = col_exp.name.lower()
        if c_name == "*" or not c_name or c_name in defined_aliases:
            continue

        tbl_name = col_exp.table.lower() if col_exp.table else None

        if tbl_name and tbl_name in verified_tables:
            valid_cols = verified_tables[tbl_name]
            if c_name not in valid_cols:
                return False, f"Column '{c_name}' does not exist on table '{tbl_name}'"
        elif not tbl_name and verified_tables:
            all_known_cols: Set[str] = set()
            for t in referenced_tables:
                all_known_cols.update(verified_tables.get(t, []))
            if all_known_cols and c_name not in all_known_cols:
                return False, f"Column '{c_name}' does not exist in referenced tables ({list(referenced_tables)})"

    return True, None


def make_bi_validator_node(redis_cache: RedisCache) -> Callable[[BIAgentState], BIAgentState]:
    """Create a validator node instance checking SQL statements against cached schemas."""

    def validator_node(state: BIAgentState) -> BIAgentState:
        sql_query = state.get("generated_sql", "")
        engine = state.get("target_engine", "sqlite")
        traces: List[Dict[str, Any]] = list(state.get("trace_steps", []))

        dialect = "duckdb" if engine == "duckdb" else "sqlite"
        schemas = redis_cache.get_all_schemas()

        if not schemas:
            for s in state.get("retrieved_schemas", []):
                t_name = s.get("table_name")
                if t_name:
                    schemas[t_name] = s

        is_valid, error_msg = validate_sql_ast(sql_query, dialect, schemas)

        print(f"\n[QueryMind/BI Validator] Checking SQL AST via sqlglot ({dialect}):\n{sql_query}", flush=True)
        if is_valid:
            print(f"[QueryMind/BI Validator] AST Status: PASSED", flush=True)
            traces.append({
                "node": "validator",
                "message": "Deterministic AST validation passed via sqlglot",
                "valid": True,
            })
            return {
                **state,
                "sql_valid": True,
                "error_trace": None,
                "trace_steps": traces,
            }
        else:
            print(f"[QueryMind/BI Validator] AST Status: REJECTED -> {error_msg}", flush=True)
            traces.append({
                "node": "validator",
                "message": f"Deterministic AST validation rejected query: {error_msg}",
                "valid": False,
                "error": error_msg,
            })
            return {
                **state,
                "sql_valid": False,
                "error_trace": error_msg,
                "trace_steps": traces,
            }

    return validator_node
