"""
GitHub tools — read + write operations via the GitHub REST API.

Read tools (no approval needed):
  github_repo_info       — stars, forks, description, topics, language
  github_readme          — fetch README.md content
  github_file_tree       — full folder/file structure of a repo
  github_file_content    — read any specific file
  github_releases        — latest releases and changelogs
  github_contributors    — top contributors with commit counts
  github_branches        — list branches
  github_search_code     — search code inside a repo
  github_user_repos      — list repos for the authenticated user
  github_repo_languages  — language breakdown (bytes per language)
  github_list_issues     — list issues (existing)
  github_list_prs        — list pull requests (existing)
  github_list_commits    — list recent commits (existing)

Write tools (sensitive=True → HITL approval required):
  github_create_issue    — open a new issue
  github_comment_on_issue — add a comment to an issue
  github_comment_on_pr   — add a review comment on a PR
  github_close_issue     — close an issue

Token: GITHUB_TOKEN in .env (optional but recommended for 5000 req/hr vs 60).
"""
import base64
import re

import httpx

from backend.config import settings
from backend.tools.base import Tool, ToolResult

GITHUB_API = "https://api.github.com"
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


def _validate_repo(repo: str) -> ToolResult | None:
    """Return an error ToolResult if repo doesn't look like 'owner/name'."""
    if not _REPO_RE.match(repo):
        return ToolResult(ok=False, error=f"Invalid repo '{repo}'. Expected 'owner/name'.")
    return None


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers


async def _get(url: str, params: dict | None = None) -> tuple[int, any]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers=_headers(), params=params or {})
    return resp.status_code, resp


async def _post(url: str, body: dict) -> tuple[int, any]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.post(url, headers=_headers(), json=body)
    return resp.status_code, resp


async def _patch(url: str, body: dict) -> tuple[int, any]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.patch(url, headers=_headers(), json=body)
    return resp.status_code, resp


# ---------------------------------------------------------------------------
# Existing tools (issues, PRs, commits) — unchanged
# ---------------------------------------------------------------------------

class GitHubIssuesTool(Tool):
    name = "github_list_issues"
    description = (
        "List issues for a GitHub repository. Use this to find, count, or "
        "summarize issues. Pull requests are excluded."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name', e.g. 'facebook/react'."},
            "state": {"type": "string", "description": "Which issues: 'open', 'closed', or 'all'. Default: open."},
            "limit": {"type": "number", "description": "Max issues to return. Default: 10."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, state: str = "open", limit=10) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        state = state if state in ("open", "closed", "all") else "open"
        limit = int(limit) if str(limit).isdigit() else 10
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/issues", {"state": state, "per_page": 100})
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            issues = [
                {"number": i["number"], "title": i["title"], "state": i["state"],
                 "labels": [l["name"] for l in i.get("labels", [])],
                 "author": i["user"]["login"], "url": i["html_url"]}
                for i in resp.json() if "pull_request" not in i
            ][:limit]
            return ToolResult(ok=True, data=issues)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubPRsTool(Tool):
    name = "github_list_prs"
    description = "List pull requests for a GitHub repository (open, closed, or all)."
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "state": {"type": "string", "description": "'open', 'closed', or 'all'. Default: open."},
            "limit": {"type": "number", "description": "Max PRs to return. Default: 10."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, state: str = "open", limit=10) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        state = state if state in ("open", "closed", "all") else "open"
        limit = int(limit) if str(limit).isdigit() else 10
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/pulls",
                                      {"state": state, "per_page": min(max(limit, 1), 50)})
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            prs = [
                {"number": i["number"], "title": i["title"], "state": i["state"],
                 "author": i["user"]["login"], "url": i["html_url"],
                 "draft": i.get("draft", False)}
                for i in resp.json()
            ][:limit]
            return ToolResult(ok=True, data=prs)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubCommitsTool(Tool):
    name = "github_list_commits"
    description = "List the most recent commits for a GitHub repository."
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "branch": {"type": "string", "description": "Branch name. Default: repo's default branch."},
            "limit": {"type": "number", "description": "Max commits to return. Default: 10."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, branch: str = "", limit=10) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        limit = int(limit) if str(limit).isdigit() else 10
        params: dict = {"per_page": min(max(limit, 1), 50)}
        if branch:
            params["sha"] = branch
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/commits", params)
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            commits = [
                {"sha": i["sha"][:7], "message": i["commit"]["message"],
                 "author": i["commit"]["author"]["name"],
                 "date": i["commit"]["author"]["date"], "url": i["html_url"]}
                for i in resp.json()
            ][:limit]
            return ToolResult(ok=True, data=commits)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# New read tools
# ---------------------------------------------------------------------------

class GitHubRepoInfoTool(Tool):
    name = "github_repo_info"
    description = (
        "Get detailed information about a GitHub repository: description, stars, "
        "forks, language, topics, open issues count, last push date, license. "
        "Use this first when a user asks about a repo."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}")
            if status == 404:
                return ToolResult(ok=False, error=f"Repo '{repo}' not found or private.")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={
                "name": d["full_name"],
                "description": d.get("description") or "",
                "url": d["html_url"],
                "stars": d["stargazers_count"],
                "forks": d["forks_count"],
                "watchers": d["watchers_count"],
                "open_issues": d["open_issues_count"],
                "language": d.get("language") or "N/A",
                "topics": d.get("topics", []),
                "default_branch": d["default_branch"],
                "license": d["license"]["name"] if d.get("license") else "None",
                "created_at": d["created_at"],
                "pushed_at": d["pushed_at"],
                "size_kb": d["size"],
                "is_fork": d["fork"],
                "is_archived": d["archived"],
            })
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubReadmeTool(Tool):
    name = "github_readme"
    description = (
        "Fetch the README of a GitHub repository. Use this to understand what "
        "a project does, how to install it, or its documentation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/readme")
            if status == 404:
                return ToolResult(ok=False, error=f"No README found in '{repo}'.")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            content = base64.b64decode(d["content"]).decode("utf-8", errors="ignore")
            # Cap at 8000 chars so LLM context stays manageable
            if len(content) > 8000:
                content = content[:8000] + "\n\n...[README truncated at 8000 chars]"
            return ToolResult(ok=True, data={
                "filename": d["name"],
                "size_bytes": d["size"],
                "content": content,
            })
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubFileTreeTool(Tool):
    name = "github_file_tree"
    description = (
        "Get the complete folder and file structure of a GitHub repository. "
        "Use this to understand how the project is organized."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "branch": {"type": "string", "description": "Branch name. Default: repo's default branch."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, branch: str = "HEAD") -> ToolResult:
        if err := _validate_repo(repo):
            return err
        try:
            status, resp = await _get(
                f"{GITHUB_API}/repos/{repo}/git/trees/{branch}",
                {"recursive": "1"},
            )
            if status == 404:
                return ToolResult(ok=False, error=f"Repo/branch '{repo}/{branch}' not found.")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            # Return paths only (no blob SHAs) — cap at 300 entries to avoid bloat
            paths = [
                {"path": item["path"], "type": item["type"], "size": item.get("size")}
                for item in d.get("tree", [])
                if item["type"] in ("blob", "tree")
            ][:300]
            return ToolResult(ok=True, data={
                "total_files": len(d.get("tree", [])),
                "truncated": d.get("truncated", False),
                "tree": paths,
            })
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubFileContentTool(Tool):
    name = "github_file_content"
    description = (
        "Read the content of a specific file in a GitHub repository. "
        "Use this to inspect source code, config files, or any text file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "path": {"type": "string", "description": "File path, e.g. 'src/main.py' or 'README.md'."},
            "branch": {"type": "string", "description": "Branch name. Default: repo's default branch."},
        },
        "required": ["repo", "path"],
    }

    async def run(self, repo: str, path: str, branch: str = "") -> ToolResult:
        if err := _validate_repo(repo):
            return err
        # Strip leading slashes to avoid path traversal
        path = path.lstrip("/")
        params = {}
        if branch:
            params["ref"] = branch
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/contents/{path}", params)
            if status == 404:
                return ToolResult(ok=False, error=f"File '{path}' not found in '{repo}'.")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            if isinstance(d, list):
                return ToolResult(ok=False, error=f"'{path}' is a directory, not a file.")
            if d.get("encoding") == "base64":
                content = base64.b64decode(d["content"]).decode("utf-8", errors="ignore")
            else:
                content = d.get("content", "")
            # Cap at 6000 chars
            if len(content) > 6000:
                content = content[:6000] + "\n\n...[file truncated at 6000 chars]"
            return ToolResult(ok=True, data={
                "path": d["path"],
                "size_bytes": d["size"],
                "content": content,
                "url": d["html_url"],
            })
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubReleasesTool(Tool):
    name = "github_releases"
    description = (
        "List releases for a GitHub repository with version tags and changelogs. "
        "Use this to find the latest version or recent changes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "limit": {"type": "number", "description": "Max releases to return. Default: 5."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, limit=5) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        limit = max(1, min(int(limit) if str(limit).isdigit() else 5, 20))
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/releases",
                                      {"per_page": limit})
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            releases = [
                {
                    "tag": r["tag_name"],
                    "name": r["name"] or r["tag_name"],
                    "published_at": r["published_at"],
                    "prerelease": r["prerelease"],
                    "url": r["html_url"],
                    "body": (r.get("body") or "")[:500],
                }
                for r in resp.json()
            ]
            return ToolResult(ok=True, data=releases)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubContributorsTool(Tool):
    name = "github_contributors"
    description = (
        "List top contributors for a GitHub repository with their commit counts."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "limit": {"type": "number", "description": "Max contributors to return. Default: 10."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, limit=10) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        limit = max(1, min(int(limit) if str(limit).isdigit() else 10, 30))
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/contributors",
                                      {"per_page": limit})
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            contributors = [
                {"username": c["login"], "contributions": c["contributions"], "url": c["html_url"]}
                for c in resp.json()
            ]
            return ToolResult(ok=True, data=contributors)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubBranchesTool(Tool):
    name = "github_branches"
    description = "List branches in a GitHub repository."
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/branches",
                                      {"per_page": 50})
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            branches = [
                {"name": b["name"], "protected": b.get("protected", False),
                 "sha": b["commit"]["sha"][:7]}
                for b in resp.json()
            ]
            return ToolResult(ok=True, data=branches)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubSearchCodeTool(Tool):
    name = "github_search_code"
    description = (
        "Search for code inside a GitHub repository. Use this to find where a "
        "function, class, or keyword is used in the codebase."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "query": {"type": "string", "description": "Code or keyword to search for."},
            "limit": {"type": "number", "description": "Max results to return. Default: 10."},
        },
        "required": ["repo", "query"],
    }

    async def run(self, repo: str, query: str, limit=10) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        limit = max(1, min(int(limit) if str(limit).isdigit() else 10, 30))
        search_query = f"{query} repo:{repo}"
        try:
            status, resp = await _get(f"{GITHUB_API}/search/code",
                                      {"q": search_query, "per_page": limit})
            if status == 403:
                return ToolResult(ok=False, error="Code search requires authentication. Set GITHUB_TOKEN.")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            results = [
                {"file": item["path"], "url": item["html_url"],
                 "repository": item["repository"]["full_name"]}
                for item in d.get("items", [])
            ]
            return ToolResult(ok=True, data={"total_count": d["total_count"], "results": results})
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubUserReposTool(Tool):
    name = "github_user_repos"
    description = (
        "List GitHub repositories for the authenticated user (requires GITHUB_TOKEN). "
        "Use this when the user asks 'what are my repos' or 'list my repositories'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "sort": {"type": "string", "description": "Sort by: 'updated', 'created', 'pushed', 'full_name'. Default: updated."},
            "limit": {"type": "number", "description": "Max repos to return. Default: 20."},
        },
        "required": [],
    }

    async def run(self, sort: str = "updated", limit=20) -> ToolResult:
        if not settings.GITHUB_TOKEN:
            return ToolResult(ok=False, error="GITHUB_TOKEN is required to list user repos.")
        sort = sort if sort in ("updated", "created", "pushed", "full_name") else "updated"
        limit = max(1, min(int(limit) if str(limit).isdigit() else 20, 100))
        try:
            status, resp = await _get(f"{GITHUB_API}/user/repos",
                                      {"sort": sort, "per_page": limit, "affiliation": "owner"})
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            repos = [
                {"name": r["full_name"], "description": r.get("description") or "",
                 "stars": r["stargazers_count"], "language": r.get("language") or "N/A",
                 "private": r["private"], "url": r["html_url"],
                 "pushed_at": r["pushed_at"]}
                for r in resp.json()
            ]
            return ToolResult(ok=True, data=repos)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubRepoLanguagesTool(Tool):
    name = "github_repo_languages"
    description = (
        "Get the programming language breakdown of a GitHub repository "
        "(bytes of code per language)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/languages")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            lang_bytes: dict = resp.json()
            total = sum(lang_bytes.values()) or 1
            languages = [
                {"language": lang, "bytes": b, "percent": round(b / total * 100, 1)}
                for lang, b in sorted(lang_bytes.items(), key=lambda x: -x[1])
            ]
            return ToolResult(ok=True, data=languages)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# Write tools (sensitive=True — go through HITL approval)
# ---------------------------------------------------------------------------

class GitHubCreateIssueTool(Tool):
    name = "github_create_issue"
    description = (
        "Create a new issue in a GitHub repository. "
        "Requires human approval before executing."
    )
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "title": {"type": "string", "description": "Issue title."},
            "body": {"type": "string", "description": "Issue description (markdown supported)."},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to apply."},
        },
        "required": ["repo", "title"],
    }

    async def run(self, repo: str, title: str, body: str = "", labels: list | None = None) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        if not settings.GITHUB_TOKEN:
            return ToolResult(ok=False, error="GITHUB_TOKEN required to create issues.")
        payload: dict = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        try:
            status, resp = await _post(f"{GITHUB_API}/repos/{repo}/issues", payload)
            if status != 201:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={"number": d["number"], "url": d["html_url"], "title": d["title"]})
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubCommentOnIssueTool(Tool):
    name = "github_comment_on_issue"
    description = "Add a comment to an existing GitHub issue. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "issue_number": {"type": "number", "description": "Issue number."},
            "body": {"type": "string", "description": "Comment text (markdown supported)."},
        },
        "required": ["repo", "issue_number", "body"],
    }

    async def run(self, repo: str, issue_number: int, body: str) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        if not settings.GITHUB_TOKEN:
            return ToolResult(ok=False, error="GITHUB_TOKEN required to comment.")
        try:
            status, resp = await _post(
                f"{GITHUB_API}/repos/{repo}/issues/{issue_number}/comments",
                {"body": body},
            )
            if status != 201:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={"comment_id": d["id"], "url": d["html_url"]})
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubCommentOnPRTool(Tool):
    name = "github_comment_on_pr"
    description = "Add a review comment on a GitHub pull request. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "pr_number": {"type": "number", "description": "Pull request number."},
            "body": {"type": "string", "description": "Comment text (markdown supported)."},
        },
        "required": ["repo", "pr_number", "body"],
    }

    async def run(self, repo: str, pr_number: int, body: str) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        if not settings.GITHUB_TOKEN:
            return ToolResult(ok=False, error="GITHUB_TOKEN required to comment on PRs.")
        try:
            status, resp = await _post(
                f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments",
                {"body": body},
            )
            if status != 201:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={"comment_id": d["id"], "url": d["html_url"]})
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubCloseIssueTool(Tool):
    name = "github_close_issue"
    description = "Close an open GitHub issue. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "issue_number": {"type": "number", "description": "Issue number to close."},
            "reason": {"type": "string", "description": "'completed' or 'not_planned'. Default: completed."},
        },
        "required": ["repo", "issue_number"],
    }

    async def run(self, repo: str, issue_number: int, reason: str = "completed") -> ToolResult:
        if err := _validate_repo(repo):
            return err
        if not settings.GITHUB_TOKEN:
            return ToolResult(ok=False, error="GITHUB_TOKEN required to close issues.")
        reason = reason if reason in ("completed", "not_planned") else "completed"
        try:
            status, resp = await _patch(
                f"{GITHUB_API}/repos/{repo}/issues/{issue_number}",
                {"state": "closed", "state_reason": reason},
            )
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={"number": d["number"], "state": d["state"], "url": d["html_url"]})
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))
