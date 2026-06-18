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
        # Mocked — wire a real read-only DB connection when ready.
        # Production: validate query is SELECT-only, then execute via AsyncSession.
        q_lower = query.strip().lower()
        if not q_lower.startswith("select"):
            return ToolResult(ok=False, error="Only SELECT queries are allowed.")
        return ToolResult(
            ok=True,
            data={
                "query": query,
                "rows": [],
                "row_count": 0,
                "note": "simulated (read-only DB connection not wired yet)",
            },
        )
