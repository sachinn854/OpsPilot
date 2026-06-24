"""
PostgreSQL query tool — run read-only SQL against the application database.

Mocked for now. A production version would use the existing async SQLAlchemy
session to execute parameterised, read-only queries. Write operations are
intentionally excluded (use dedicated HITL-guarded tools for mutations).
"""
from backend.tools.base import Tool, ToolResult


class ExecuteSQLTool(Tool):
    name = "execute_sql"
    description = (
        "Run a read-only SQL query against the application database. "
        "Only SELECT statements are permitted — use this to look up runs, "
        "documents, or operational data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A read-only SQL SELECT statement.",
            },
        },
        "required": ["query"],
    }

    async def run(self, query: str) -> ToolResult:
        # Validate that this is a single SELECT statement — reject anything else.
        # The startswith check is easily bypassed; we also reject semicolons to
        # block stacked queries like "SELECT 1; DROP TABLE users".
        q_stripped = query.strip()
        q_lower = q_stripped.lower()
        if not q_lower.startswith("select"):
            return ToolResult(ok=False, error="Only SELECT queries are allowed.")
        if ";" in q_stripped:
            return ToolResult(ok=False, error="Multiple statements are not allowed.")
        # Reject common write keywords anywhere in the query.
        _WRITE_KW = ("insert", "update", "delete", "drop", "truncate", "alter", "create", "replace")
        for kw in _WRITE_KW:
            if kw in q_lower:
                return ToolResult(ok=False, error=f"Forbidden keyword '{kw}' in query.")
        return ToolResult(
            ok=True,
            data={
                "query": query,
                "rows": [],
                "row_count": 0,
                "note": "simulated (read-only DB connection not wired yet)",
            },
        )
