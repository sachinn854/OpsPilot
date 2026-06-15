"""
GitHub tools (Phase 1).

Two focused tools the Copilot can call:
  - github_list_issues  → list issues for a repo
  - github_list_commits → list recent commits for a repo

They use the public GitHub REST API. A token (GITHUB_TOKEN in .env) is optional
but recommended — without it you hit a low unauthenticated rate limit.
"""
import httpx

from backend.config import settings
from backend.tools.base import Tool, ToolResult

GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers


class GitHubIssuesTool(Tool):
    name = "github_list_issues"
    description = (
        "List issues for a GitHub repository. Use this to find, count, or "
        "summarize issues. Pull requests are excluded."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository as 'owner/name', e.g. 'facebook/react'.",
            },
            "state": {
                "type": "string",
                "enum": ["open", "closed", "all"],
                "description": "Which issues to return.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of issues to return (max 50).",
            },
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, state: str = "open", limit: int = 10) -> ToolResult:
        url = f"{GITHUB_API}/repos/{repo}/issues"
        # GitHub's /issues endpoint returns issues AND pull requests. Fetch a
        # bigger page so that after filtering out PRs we still have enough issues.
        params = {"state": state, "per_page": 100}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=_headers(), params=params)
            if resp.status_code != 200:
                return ToolResult(
                    ok=False,
                    error=f"GitHub API {resp.status_code}: {resp.text[:200]}",
                )
            issues = [
                {
                    "number": item["number"],
                    "title": item["title"],
                    "state": item["state"],
                    "url": item["html_url"],
                }
                for item in resp.json()
                if "pull_request" not in item  # exclude PRs
            ][:limit]
            return ToolResult(ok=True, data=issues)
        except Exception as exc:  # network / parsing errors
            return ToolResult(ok=False, error=str(exc))


class GitHubCommitsTool(Tool):
    name = "github_list_commits"
    description = "List the most recent commits for a GitHub repository."
    parameters = {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository as 'owner/name', e.g. 'facebook/react'.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of commits to return (max 50).",
            },
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, limit: int = 10) -> ToolResult:
        url = f"{GITHUB_API}/repos/{repo}/commits"
        params = {"per_page": min(max(limit, 1), 50)}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=_headers(), params=params)
            if resp.status_code != 200:
                return ToolResult(
                    ok=False,
                    error=f"GitHub API {resp.status_code}: {resp.text[:200]}",
                )
            commits = [
                {
                    "sha": item["sha"][:7],
                    "message": item["commit"]["message"].split("\n")[0],
                    "author": item["commit"]["author"]["name"],
                    "date": item["commit"]["author"]["date"],
                    "url": item["html_url"],
                }
                for item in resp.json()
            ][:limit]
            return ToolResult(ok=True, data=commits)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))
