"""
Filesystem tools — read and list files within the workspace.

These are sandboxed to a configurable workspace directory (WORKSPACE_PATH).
The mock implementations below simulate the operations without touching the
real filesystem beyond logging — wire real Path operations when ready.
"""
from backend.tools.base import Tool, ToolResult


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read the contents of a file from the workspace. "
        "Path must be relative to the workspace root."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path, e.g. 'logs/app.log'.",
            },
        },
        "required": ["path"],
    }

    async def run(self, path: str) -> ToolResult:
        # Mocked — wire real Path.read_text() when WORKSPACE_PATH is set.
        return ToolResult(
            ok=True,
            data={
                "path": path,
                "content": f"[Simulated content of '{path}']",
                "note": "simulated (WORKSPACE_PATH not configured)",
            },
        )


class ListFilesTool(Tool):
    name = "list_files"
    description = (
        "List files in a workspace directory. "
        "Returns filenames and sizes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Relative directory path (default: workspace root).",
                "default": ".",
            },
        },
        "required": [],
    }

    async def run(self, directory: str = ".") -> ToolResult:
        # Mocked.
        return ToolResult(
            ok=True,
            data={
                "directory": directory,
                "files": [
                    {"name": "app.log", "size_bytes": 4096},
                    {"name": "config.yaml", "size_bytes": 512},
                ],
                "note": "simulated (WORKSPACE_PATH not configured)",
            },
        )
