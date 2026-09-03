"""AST security validation unit tests for NaturalLangData BI engine."""
import pytest
from naturallangdata.agents.nodes.bi.validator import validate_sql_ast


@pytest.fixture
def mock_schemas():
    """Return mock verified schema dictionary for tests."""
    return {
        "customers": {
            "engine": "sqlite",
            "columns": ["customer_id", "full_name", "signup_date", "region", "is_active"],
        },
        "orders": {
            "engine": "sqlite",
            "columns": ["order_id", "customer_id", "order_date", "status", "total_amount"],
        },
        "quarterly_arr": {
            "engine": "duckdb",
            "columns": ["quarter", "region", "gross_arr", "churned_arr", "net_arr"],
        },
    }


def test_ddl_drop_table_blocked(mock_schemas):
    """Verify DROP TABLE statements are blocked."""
    sql = "DROP TABLE orders;"
    is_valid, err = validate_sql_ast(sql, "sqlite", mock_schemas)
    assert not is_valid
    assert "Forbidden non-SELECT DDL/DML" in err or "Root AST node" in err


def test_multi_statement_injection_blocked(mock_schemas):
    """Verify stacked multi-statement injection is blocked."""
    sql = "SELECT customer_id FROM customers; TRUNCATE TABLE customers;"
    is_valid, err = validate_sql_ast(sql, "sqlite", mock_schemas)
    assert not is_valid
    assert "Forbidden multi-statement" in err or "Forbidden non-SELECT" in err


def test_delete_statement_blocked(mock_schemas):
    """Verify DELETE statements are blocked."""
    sql = "DELETE FROM orders WHERE customer_id = 1;"
    is_valid, err = validate_sql_ast(sql, "sqlite", mock_schemas)
    assert not is_valid
    assert "Forbidden" in err or "Root AST node" in err


def test_hallucinated_column_flagged(mock_schemas):
    """Verify hallucinated column references are detected and rejected."""
    sql = "SELECT fake_column FROM customers;"
    is_valid, err = validate_sql_ast(sql, "sqlite", mock_schemas)
    assert not is_valid
    assert "fake_column" in err


def test_hallucinated_table_flagged(mock_schemas):
    """Verify hallucinated table references are detected and rejected."""
    sql = "SELECT * FROM secret_payroll_data;"
    is_valid, err = validate_sql_ast(sql, "sqlite", mock_schemas)
    assert not is_valid
    assert "secret_payroll_data" in err


def test_valid_select_query_passes(mock_schemas):
    """Verify compliant SELECT queries pass validation smoothly."""
    sql = "SELECT customer_id, full_name FROM customers WHERE is_active = 1"
    is_valid, err = validate_sql_ast(sql, "sqlite", mock_schemas)
    assert is_valid
    assert err is None


def test_valid_join_passes(mock_schemas):
    """Verify valid multi-table joins pass validation."""
    sql = """
        SELECT c.full_name, o.total_amount
        FROM customers AS c
        JOIN orders AS o ON c.customer_id = o.customer_id
        WHERE o.status = 'completed'
    """
    is_valid, err = validate_sql_ast(sql, "sqlite", mock_schemas)
    assert is_valid
    assert err is None


def test_valid_duckdb_aggregations_pass(mock_schemas):
    """Verify analytical queries with aggregations pass validation."""
    sql = "SELECT region, SUM(gross_arr) AS total_arr FROM quarterly_arr GROUP BY region"
    is_valid, err = validate_sql_ast(sql, "duckdb", mock_schemas)
    assert is_valid
    assert err is None


def test_engine_mismatch_flagged(mock_schemas):
    """Verify cross-engine table usage is flagged."""
    sql = "SELECT * FROM quarterly_arr"
    is_valid, err = validate_sql_ast(sql, "sqlite", mock_schemas)
    assert not is_valid
    assert "duckdb" in err
