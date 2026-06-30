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


def _headers(token: str | None = None) -> dict:
    """Build GitHub API headers. Uses provided token, falls back to .env GITHUB_TOKEN."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    tok = token or settings.GITHUB_TOKEN
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


async def _get_org_token(org_id: str = "default") -> str | None:
    """Fetch GitHub token for this org from DB."""
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as session:
            return await get_token(session, org_id=org_id, service="github")
    except Exception:
        return None


async def _resolve_token(org_id: str = "default") -> str | None:
    """Best available token: DB first, then .env fallback."""
    return await _get_org_token(org_id) or settings.GITHUB_TOKEN or None


async def _get(url: str, params: dict | None = None, token: str | None = None) -> tuple[int, any]:
    tok = token if token is not None else await _resolve_token()
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers=_headers(tok), params=params or {})
    return resp.status_code, resp


async def _post(url: str, body: dict, token: str | None = None) -> tuple[int, any]:
    tok = token if token is not None else await _resolve_token()
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.post(url, headers=_headers(tok), json=body)
    return resp.status_code, resp


async def _patch(url: str, body: dict, token: str | None = None) -> tuple[int, any]:
    tok = token if token is not None else await _resolve_token()
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.patch(url, headers=_headers(tok), json=body)
    return resp.status_code, resp


async def _put(url: str, body: dict, token: str | None = None) -> tuple[int, any]:
    tok = token if token is not None else await _resolve_token()
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.put(url, headers=_headers(tok), json=body)
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
        "List all GitHub repositories for the authenticated user. "
        "ALWAYS call this first when the user mentions a repo by short name only "
        "(e.g. 'CortexTutor', 'my project') so you can find the full 'owner/name' "
        "before calling any other GitHub tool. Also use for 'list my repos' requests."
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
        tok = await _resolve_token()
        if not tok:
            return ToolResult(ok=False, error="No GitHub token found. Connect one via Settings.")
        sort = sort if sort in ("updated", "created", "pushed", "full_name") else "updated"
        limit = max(1, min(int(limit) if str(limit).isdigit() else 20, 100))
        try:
            status, resp = await _get(f"{GITHUB_API}/user/repos",
                                      {"sort": sort, "per_page": limit, "affiliation": "owner"},
                                      token=tok)
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


class GitHubCreatePRTool(Tool):
    name = "github_create_pr"
    description = (
        "Create a pull request in a GitHub repository. "
        "The head branch must already exist on GitHub with pushed commits. "
        "Requires human approval before executing."
    )
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "title": {"type": "string", "description": "PR title."},
            "head": {"type": "string", "description": "Branch to merge FROM (e.g. 'feature/my-branch')."},
            "base": {"type": "string", "description": "Branch to merge INTO (e.g. 'main'). Default: main."},
            "body": {"type": "string", "description": "PR description (markdown supported)."},
            "draft": {"type": "boolean", "description": "Open as draft PR. Default: false."},
        },
        "required": ["repo", "title", "head"],
    }

    async def run(
        self,
        repo: str,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        draft: bool = False,
    ) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        payload = {"title": title, "head": head, "base": base, "body": body, "draft": draft}
        try:
            status, resp = await _post(f"{GITHUB_API}/repos/{repo}/pulls", payload)
            if status == 422:
                detail = resp.json().get("errors", [{}])
                msg = detail[0].get("message", resp.text[:200]) if detail else resp.text[:200]
                return ToolResult(ok=False, error=f"GitHub rejected PR: {msg}")
            if status != 201:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={
                "number": d["number"],
                "url": d["html_url"],
                "title": d["title"],
                "state": d["state"],
                "draft": d.get("draft", False),
            })
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# Additional read tools
# ---------------------------------------------------------------------------

class GitHubGetIssueTool(Tool):
    name = "github_get_issue"
    description = "Get full details of a single GitHub issue including body, labels, assignees, and comments count."
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "issue_number": {"type": "number", "description": "Issue number."},
        },
        "required": ["repo", "issue_number"],
    }

    async def run(self, repo: str, issue_number: int) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/issues/{int(issue_number)}")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={
                "number": d["number"], "title": d["title"], "state": d["state"],
                "body": (d.get("body") or "")[:2000],
                "author": d["user"]["login"],
                "labels": [l["name"] for l in d.get("labels", [])],
                "assignees": [a["login"] for a in d.get("assignees", [])],
                "comments": d["comments"], "url": d["html_url"],
                "created_at": d["created_at"], "updated_at": d["updated_at"],
            })
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubGetPRTool(Tool):
    name = "github_get_pr"
    description = "Get full details of a single pull request including diff stats, reviewers, and merge status."
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "pr_number": {"type": "number", "description": "Pull request number."},
        },
        "required": ["repo", "pr_number"],
    }

    async def run(self, repo: str, pr_number: int) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/pulls/{int(pr_number)}")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={
                "number": d["number"], "title": d["title"], "state": d["state"],
                "draft": d.get("draft", False),
                "body": (d.get("body") or "")[:2000],
                "author": d["user"]["login"],
                "head": d["head"]["ref"], "base": d["base"]["ref"],
                "mergeable": d.get("mergeable"),
                "merged": d.get("merged", False),
                "additions": d.get("additions"), "deletions": d.get("deletions"),
                "changed_files": d.get("changed_files"),
                "reviewers": [r["login"] for r in d.get("requested_reviewers", [])],
                "url": d["html_url"],
                "created_at": d["created_at"],
            })
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubListWorkflowsTool(Tool):
    name = "github_list_workflows"
    description = "List GitHub Actions workflows defined in a repository."
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
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/actions/workflows")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            workflows = [
                {"id": w["id"], "name": w["name"], "state": w["state"], "path": w["path"]}
                for w in resp.json().get("workflows", [])
            ]
            return ToolResult(ok=True, data=workflows)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubWorkflowRunsTool(Tool):
    name = "github_workflow_runs"
    description = (
        "Get recent GitHub Actions CI/CD run history for a repository. "
        "Shows pass/fail status of the latest pipeline runs."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "limit": {"type": "number", "description": "Max runs to return. Default: 10."},
            "branch": {"type": "string", "description": "Filter by branch name (optional)."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, limit: int = 10, branch: str | None = None) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        limit = max(1, min(int(limit) if str(limit).isdigit() else 10, 50))
        params: dict = {"per_page": limit}
        if branch:
            params["branch"] = branch
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/actions/runs", params)
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            runs = [
                {
                    "id": r["id"], "name": r["name"], "status": r["status"],
                    "conclusion": r.get("conclusion"), "branch": r["head_branch"],
                    "commit": r["head_sha"][:8], "url": r["html_url"],
                    "created_at": r["created_at"],
                }
                for r in resp.json().get("workflow_runs", [])
            ]
            return ToolResult(ok=True, data=runs)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubCompareBranchesTool(Tool):
    name = "github_compare_branches"
    description = "Compare two branches (or commits) in a repository — shows ahead/behind count and changed files."
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "base": {"type": "string", "description": "Base branch or commit SHA."},
            "head": {"type": "string", "description": "Head branch or commit SHA to compare against base."},
        },
        "required": ["repo", "base", "head"],
    }

    async def run(self, repo: str, base: str, head: str) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/compare/{base}...{head}")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={
                "status": d["status"],
                "ahead_by": d["ahead_by"], "behind_by": d["behind_by"],
                "total_commits": d["total_commits"],
                "files_changed": len(d.get("files", [])),
                "files": [
                    {"filename": f["filename"], "status": f["status"],
                     "additions": f["additions"], "deletions": f["deletions"]}
                    for f in d.get("files", [])[:20]
                ],
                "url": d["permalink_url"],
            })
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubGetTagsTool(Tool):
    name = "github_get_tags"
    description = "List git tags (version tags) for a repository."
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "limit": {"type": "number", "description": "Max tags to return. Default: 20."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, limit: int = 20) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        limit = max(1, min(int(limit) if str(limit).isdigit() else 20, 100))
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/tags", {"per_page": limit})
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            tags = [{"name": t["name"], "sha": t["commit"]["sha"][:8]} for t in resp.json()]
            return ToolResult(ok=True, data=tags)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubListMilestonesTool(Tool):
    name = "github_list_milestones"
    description = "List milestones for a GitHub repository with open/closed issue counts."
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "state": {"type": "string", "description": "'open', 'closed', or 'all'. Default: open."},
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, state: str = "open") -> ToolResult:
        if err := _validate_repo(repo):
            return err
        state = state if state in ("open", "closed", "all") else "open"
        try:
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/milestones", {"state": state})
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            milestones = [
                {
                    "number": m["number"], "title": m["title"], "state": m["state"],
                    "open_issues": m["open_issues"], "closed_issues": m["closed_issues"],
                    "due_on": m.get("due_on"), "url": m["html_url"],
                }
                for m in resp.json()
            ]
            return ToolResult(ok=True, data=milestones)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# Additional write tools (sensitive=True — HITL approval required)
# ---------------------------------------------------------------------------

class GitHubMergePRTool(Tool):
    name = "github_merge_pr"
    description = "Merge an open pull request. Requires human approval before executing."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "pr_number": {"type": "number", "description": "Pull request number to merge."},
            "merge_method": {"type": "string", "description": "'merge', 'squash', or 'rebase'. Default: merge."},
            "commit_message": {"type": "string", "description": "Optional merge commit message."},
        },
        "required": ["repo", "pr_number"],
    }

    async def run(self, repo: str, pr_number: int, merge_method: str = "merge", commit_message: str = "") -> ToolResult:
        if err := _validate_repo(repo):
            return err
        merge_method = merge_method if merge_method in ("merge", "squash", "rebase") else "merge"
        payload: dict = {"merge_method": merge_method}
        if commit_message:
            payload["commit_message"] = commit_message
        try:
            status, resp = await _put(f"{GITHUB_API}/repos/{repo}/pulls/{int(pr_number)}/merge", payload)
            if status == 405:
                return ToolResult(ok=False, error="PR is not mergeable (conflicts or already merged).")
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={"sha": d.get("sha", "")[:8], "merged": d.get("merged", False), "message": d.get("message", "")})
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubClosePRTool(Tool):
    name = "github_close_pr"
    description = "Close an open pull request without merging. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "pr_number": {"type": "number", "description": "Pull request number to close."},
        },
        "required": ["repo", "pr_number"],
    }

    async def run(self, repo: str, pr_number: int) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        try:
            status, resp = await _patch(f"{GITHUB_API}/repos/{repo}/pulls/{int(pr_number)}", {"state": "closed"})
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={"number": d["number"], "state": d["state"], "url": d["html_url"]})
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubCreateBranchTool(Tool):
    name = "github_create_branch"
    description = "Create a new branch in a GitHub repository from a base branch or commit SHA. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "branch": {"type": "string", "description": "New branch name to create."},
            "from_branch": {"type": "string", "description": "Base branch to branch off from. Default: main."},
        },
        "required": ["repo", "branch"],
    }

    async def run(self, repo: str, branch: str, from_branch: str = "main") -> ToolResult:
        if err := _validate_repo(repo):
            return err
        try:
            # Get SHA of the base branch
            status, resp = await _get(f"{GITHUB_API}/repos/{repo}/git/refs/heads/{from_branch}")
            if status != 200:
                return ToolResult(ok=False, error=f"Base branch '{from_branch}' not found: {resp.text[:200]}")
            sha = resp.json()["object"]["sha"]

            status, resp = await _post(f"{GITHUB_API}/repos/{repo}/git/refs", {
                "ref": f"refs/heads/{branch}",
                "sha": sha,
            })
            if status == 422:
                return ToolResult(ok=False, error=f"Branch '{branch}' already exists.")
            if status != 201:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            return ToolResult(ok=True, data={"branch": branch, "sha": sha[:8], "from": from_branch})
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubUpdateIssueTool(Tool):
    name = "github_update_issue"
    description = "Update an existing GitHub issue — change title, body, state, or labels. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "issue_number": {"type": "number", "description": "Issue number to update."},
            "title": {"type": "string", "description": "New title (optional)."},
            "body": {"type": "string", "description": "New body/description (optional)."},
            "state": {"type": "string", "description": "'open' or 'closed' (optional)."},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "Replace labels with this list (optional)."},
        },
        "required": ["repo", "issue_number"],
    }

    async def run(self, repo: str, issue_number: int, title: str | None = None,
                  body: str | None = None, state: str | None = None,
                  labels: list | None = None) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        payload: dict = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if state in ("open", "closed"):
            payload["state"] = state
        if labels is not None:
            payload["labels"] = labels
        if not payload:
            return ToolResult(ok=False, error="Nothing to update — provide at least one field.")
        try:
            status, resp = await _patch(f"{GITHUB_API}/repos/{repo}/issues/{int(issue_number)}", payload)
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            d = resp.json()
            return ToolResult(ok=True, data={"number": d["number"], "title": d["title"], "state": d["state"], "url": d["html_url"]})
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class GitHubAddLabelsTool(Tool):
    name = "github_add_labels"
    description = "Add labels to a GitHub issue or pull request. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name'."},
            "issue_number": {"type": "number", "description": "Issue or PR number."},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to add."},
        },
        "required": ["repo", "issue_number", "labels"],
    }

    async def run(self, repo: str, issue_number: int, labels: list) -> ToolResult:
        if err := _validate_repo(repo):
            return err
        if not labels:
            return ToolResult(ok=False, error="Labels list cannot be empty.")
        try:
            status, resp = await _post(
                f"{GITHUB_API}/repos/{repo}/issues/{int(issue_number)}/labels",
                {"labels": labels},
            )
            if status != 200:
                return ToolResult(ok=False, error=f"GitHub API {status}: {resp.text[:200]}")
            applied = [l["name"] for l in resp.json()]
            return ToolResult(ok=True, data={"issue": issue_number, "labels_applied": applied})
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))
