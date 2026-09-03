"""Query execution engine targeting SQLite and DuckDB."""
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List
import duckdb

from naturallangdata.core.config import Settings


class QueryEngine:
    """Execute SQL queries against local SQLite database or DuckDB analytical views."""

    def __init__(self, settings: Settings) -> None:
        self._sqlite_path = settings.sqlite_db_path
        self._analytics_dir = settings.analytics_data_dir

    def execute_sqlite(self, sql: str) -> List[Dict[str, Any]]:
        """Execute query against SQLite operational database."""
        if not self._sqlite_path.exists():
            raise FileNotFoundError(f"SQLite database not found at {self._sqlite_path}")

        conn = sqlite3.connect(str(self._sqlite_path))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def execute_duckdb(self, sql: str) -> List[Dict[str, Any]]:
        """Execute query against DuckDB registering all analytics files as views."""
        con = duckdb.connect(database=":memory:")
        try:
            if self._analytics_dir.exists():
                for file_path in self._analytics_dir.iterdir():
                    suffix = file_path.suffix.lower()
                    if suffix not in (".parquet", ".csv"):
                        continue
                    clean_name = re.sub(r"[^a-zA-Z0-9_]+", "_", file_path.stem).strip("_")
                    read_fn = f"read_parquet('{file_path}')" if suffix == ".parquet" else f"read_csv_auto('{file_path}')"
                    if clean_name:
                        con.execute(f"CREATE VIEW \"{clean_name}\" AS SELECT * FROM {read_fn};")
                        if clean_name != file_path.stem:
                            try:
                                con.execute(f"CREATE VIEW \"{file_path.stem}\" AS SELECT * FROM {read_fn};")
                            except Exception:
                                pass

            df = con.execute(sql).fetchdf()
            return df.to_dict(orient="records")
        finally:
            con.close()

    def execute(self, sql: str, engine: str) -> List[Dict[str, Any]]:
        """Dispatch query execution to specified engine."""
        if engine == "duckdb":
            return self.execute_duckdb(sql)
        return self.execute_sqlite(sql)
