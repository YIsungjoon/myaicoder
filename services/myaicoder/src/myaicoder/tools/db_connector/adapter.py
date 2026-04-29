import sqlite3
from typing import List, Dict, Any, Optional

class SQLiteAdapter:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def execute_query(self, query: str) -> Dict[str, Any]:
        """SQLite 쿼리를 실행하고 결과를 반환합니다."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                if not rows:
                    return {"status": "success", "columns": [], "data": [], "row_count": 0}
                columns = list(rows[0].keys())
                data = [dict(row) for row in rows]
                return {"status": "success", "columns": columns, "data": data, "row_count": len(data)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_schema(self) -> Dict[str, Any]:
        """SQLite 스키마 정보를 가져옵니다."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                schema = {}
                for table in tables:
                    cursor.execute(f"PRAGMA table_info({table});")
                    columns = cursor.fetchall()
                    schema[table] = [{"name": col[1], "type": col[2], "notnull": bool(col[3]), "pk": bool(col[5])} for col in columns]
                return {"status": "success", "schema": schema}
        except Exception as e:
            return {"status": "error", "message": str(e)}

class PostgresAdapter:
    def __init__(self, connection_string: str):
        self.conn_str = connection_string

    def execute_query(self, query: str) -> Dict[str, Any]:
        """PostgreSQL 쿼리를 실행합니다."""
        # TODO: psycopg2 연동
        return {"status": "error", "message": "PostgreSQL driver (psycopg2) not configured."}

    def get_schema(self) -> Dict[str, Any]:
        """PostgreSQL 스키마 정보를 가져옵니다."""
        # TODO: information_schema 조회 로직
        return {"status": "error", "message": "PostgreSQL schema inspection not implemented."}
