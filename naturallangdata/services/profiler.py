"""Database and flat file schema profiler."""
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List
import duckdb

from naturallangdata.core.config import Settings


class SchemaProfiler:
    """Extract schema metadata, column types, and sample values across SQLite and DuckDB."""

    def __init__(self, settings: Settings) -> None:
        self._sqlite_path = settings.sqlite_db_path
        self._analytics_dir = settings.analytics_data_dir

    def profile_sqlite(self) -> List[Dict[str, Any]]:
        """Extract table names, column structures, and sample values from SQLite."""
        if not self._sqlite_path.exists():
            return []

        conn = sqlite3.connect(str(self._sqlite_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row["name"] for row in cursor.fetchall()]

        profiled_tables: List[Dict[str, Any]] = []

        for table in tables:
            cursor.execute(f"PRAGMA table_info({table});")
            columns_info = cursor.fetchall()

            columns: List[Dict[str, Any]] = []
            column_names: List[str] = []

            for col in columns_info:
                c_name = col["name"]
                c_type = col["type"] or "TEXT"
                column_names.append(c_name)

                cursor.execute(f"SELECT DISTINCT {c_name} FROM {table} WHERE {c_name} IS NOT NULL LIMIT 3;")
                samples = [row[0] for row in cursor.fetchall()]

                columns.append({
                    "name": c_name,
                    "type": c_type,
                    "samples": samples,
                })

            col_defs = ", ".join(f"{c['name']} {c['type']}" for c in columns)
            ddl = f"CREATE TABLE {table} ({col_defs});"

            profiled_tables.append({
                "table_name": table,
                "engine": "sqlite",
                "source": str(self._sqlite_path),
                "columns": column_names,
                "column_details": columns,
                "ddl": ddl,
            })

        conn.close()
        return profiled_tables

    def profile_duckdb(self) -> List[Dict[str, Any]]:
        """Extract schema and sample values from Parquet and CSV files in the analytics directory."""
        if not self._analytics_dir.exists():
            return []

        con = duckdb.connect(database=":memory:")
        profiled_tables: List[Dict[str, Any]] = []

        for file_path in self._analytics_dir.iterdir():
            suffix = file_path.suffix.lower()
            if suffix not in (".parquet", ".csv"):
                continue

            clean_name = re.sub(r"[^a-zA-Z0-9_]+", "_", file_path.stem).strip("_")
            read_fn = f"read_parquet('{file_path}')" if suffix == ".parquet" else f"read_csv_auto('{file_path}')"

            try:
                describe_df = con.execute(f"DESCRIBE SELECT * FROM {read_fn};").fetchall()
            except Exception:
                continue

            columns: List[Dict[str, Any]] = []
            column_names: List[str] = []

            for row in describe_df:
                c_name = str(row[0])
                c_type = str(row[1])
                column_names.append(c_name)

                try:
                    samples_res = con.execute(
                        f"SELECT DISTINCT \"{c_name}\" FROM {read_fn} WHERE \"{c_name}\" IS NOT NULL LIMIT 3;"
                    ).fetchall()
                    samples = [s[0] for s in samples_res]
                except Exception:
                    samples = []

                columns.append({
                    "name": c_name,
                    "type": c_type,
                    "samples": samples,
                })

            col_defs = ", ".join(f"\"{c['name']}\" {c['type']}" for c in columns)
            ddl = f"CREATE VIEW \"{clean_name}\" AS SELECT * FROM {read_fn}; -- ({col_defs})"

            profiled_tables.append({
                "table_name": clean_name,
                "engine": "duckdb",
                "source": str(file_path),
                "columns": column_names,
                "column_details": columns,
                "ddl": ddl,
            })

        con.close()
        return profiled_tables

    def profile_all(self) -> List[Dict[str, Any]]:
        """Run complete schema profiling across SQLite and DuckDB analytical sources."""
        return self.profile_sqlite() + self.profile_duckdb()
