import re
import sqlite3
from pathlib import Path

import pandas as pd


class TabularStore:
    """Persist full tabular data to SQLite for low-cost future querying."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tabular_documents (
                    doc_id TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    column_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (doc_id, sheet_name)
                )
                """
            )

    @staticmethod
    def _sanitize_identifier(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip())
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned or "field"

    def _make_table_name(self, doc_id: str, sheet_name: str) -> str:
        doc_part = self._sanitize_identifier(doc_id)[:24]
        sheet_part = self._sanitize_identifier(sheet_name)[:24]
        return f"doc_{doc_part}_{sheet_part}"

    def _normalize_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        normalized = frame.copy()
        seen: dict[str, int] = {}
        final_columns: list[str] = []

        for col in normalized.columns:
            base = self._sanitize_identifier(str(col))
            count = seen.get(base, 0)
            seen[base] = count + 1
            final_name = base if count == 0 else f"{base}_{count + 1}"
            final_columns.append(final_name)

        normalized.columns = final_columns
        return normalized

    def ingest_dataframe(self, doc_id: str, sheet_name: str, frame: pd.DataFrame) -> str:
        table_name = self._make_table_name(doc_id, sheet_name)
        normalized = self._normalize_columns(frame)

        with self._connect() as conn:
            normalized.to_sql(table_name, conn, if_exists="replace", index=False)
            conn.execute(
                """
                INSERT INTO tabular_documents (doc_id, sheet_name, table_name, row_count, column_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(doc_id, sheet_name)
                DO UPDATE SET
                    table_name=excluded.table_name,
                    row_count=excluded.row_count,
                    column_count=excluded.column_count,
                    created_at=CURRENT_TIMESTAMP
                """,
                (doc_id, sheet_name, table_name, int(len(normalized)), int(len(normalized.columns))),
            )

        return table_name

    def delete_document(self, doc_id: str) -> None:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT table_name FROM tabular_documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchall()

            for (table_name,) in rows:
                conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')

            conn.execute("DELETE FROM tabular_documents WHERE doc_id = ?", (doc_id,))
