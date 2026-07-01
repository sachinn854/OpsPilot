"""
Linear tools — real Linear GraphQL API via personal API key.

Read tools:
  linear_get_teams     — list all teams in the workspace
  linear_get_issues    — search/filter issues with state/assignee/priority
  linear_get_issue     — get a single issue by ID or identifier
  linear_get_projects  — list projects (Initiatives)

Write tools (sensitive=True — HITL approval required):
  linear_create_issue  — create a new issue
  linear_update_issue  — update status, priority, or title
  linear_add_comment   — add a comment to an issue

Config: stored as token string in integration_tokens (service="linear").
  Token format: lin_api_xxxxxxxxxxxx
"""
import httpx

from backend.tools.base import Tool, ToolResult

LINEAR_GQL = "https://api.linear.app/graphql"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_token(org_id: str = "default") -> str | None:
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as session:
            return await get_token(session, org_id=org_id, service="linear")
    except Exception:
        return None


def _headers(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}


def _no_token_error() -> ToolResult:
    return ToolResult(
        ok=False,
        error="Linear not configured. Connect via Settings → Integrations → Linear.",
    )


async def _gql(token: str, query: str, variables: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            LINEAR_GQL,
            headers=_headers(token),
            json={"query": query, "variables": variables or {}},
        )
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


def _gql_error(data: dict) -> str:
    errs = data.get("errors", [])
    if errs:
        return errs[0].get("message", "Unknown GraphQL error")
    return "Unknown error"


# ---------------------------------------------------------------------------
# Tool 1 — Get teams
# ---------------------------------------------------------------------------

class LinearGetTeamsTool(Tool):
    name = "linear_get_teams"
    description = "List all teams in the Linear workspace. Returns team ID, name, key, and member count."
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self) -> ToolResult:
        token = await _get_token()
        if not token:
            return _no_token_error()
        query = """
        query {
          teams {
            nodes {
              id name key description
              members { totalCount }
            }
          }
        }
        """
        status, data = await _gql(token, query)
        if status != 200 or "errors" in data:
            return ToolResult(ok=False, error=f"Linear API error: {_gql_error(data)}")
        teams = [
            {
                "id": t["id"],
                "name": t["name"],
                "key": t["key"],
                "description": t.get("description", ""),
                "member_count": t.get("members", {}).get("totalCount", 0),
            }
            for t in data.get("data", {}).get("teams", {}).get("nodes", [])
        ]
        return ToolResult(ok=True, data={"teams": teams, "count": len(teams)})


# ---------------------------------------------------------------------------
# Tool 2 — Get issues
# ---------------------------------------------------------------------------

class LinearGetIssuesTool(Tool):
    name = "linear_get_issues"
    description = (
        "Search Linear issues. Filter by team, state, assignee, or priority. "
        "Priority values: 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low."
    )
    parameters = {
        "type": "object",
        "properties": {
            "team_key": {"type": "string", "description": "Team key (e.g. 'ENG', 'OPS'). Leave empty for all teams."},
            "state": {"type": "string", "description": "State name filter (e.g. 'In Progress', 'Todo', 'Done')."},
            "assignee_email": {"type": "string", "description": "Filter by assignee email."},
            "priority": {"type": "number", "description": "Priority filter: 1=Urgent, 2=High, 3=Medium, 4=Low."},
            "limit": {"type": "number", "description": "Max issues to return. Default 20."},
        },
        "required": [],
    }

    async def run(
        self,
        team_key: str = "",
        state: str = "",
        assignee_email: str = "",
        priority: int | None = None,
        limit: int = 20,
    ) -> ToolResult:
        token = await _get_token()
        if not token:
            return _no_token_error()

        filters: list[str] = []
        if team_key:
            filters.append(f'team: {{ key: {{ eq: "{team_key}" }} }}')
        if state:
            filters.append(f'state: {{ name: {{ eq: "{state}" }} }}')
        if assignee_email:
            filters.append(f'assignee: {{ email: {{ eq: "{assignee_email}" }} }}')
        if priority is not None:
            filters.append(f'priority: {{ eq: {int(priority)} }}')

        filter_str = f"filter: {{ {', '.join(filters)} }}" if filters else ""
        query = f"""
        query {{
          issues({filter_str} first: {min(limit, 50)}) {{
            nodes {{
              id identifier title
              state {{ name }}
              assignee {{ name email }}
              priority
              createdAt updatedAt
              url
              team {{ name key }}
              project {{ name }}
            }}
          }}
        }}
        """
        status, data = await _gql(token, query)
        if status != 200 or "errors" in data:
            return ToolResult(ok=False, error=f"Linear API error: {_gql_error(data)}")
        raw = data.get("data", {}).get("issues", {}).get("nodes", [])
        priority_label = {0: "No priority", 1: "Urgent", 2: "High", 3: "Medium", 4: "Low"}
        issues = [
            {
                "id": i["id"],
                "identifier": i.get("identifier"),
                "title": i.get("title"),
                "state": (i.get("state") or {}).get("name"),
                "assignee": (i.get("assignee") or {}).get("name"),
                "priority": priority_label.get(i.get("priority", 0), "Unknown"),
                "team": (i.get("team") or {}).get("key"),
                "project": (i.get("project") or {}).get("name"),
                "updated": i.get("updatedAt"),
                "url": i.get("url"),
            }
            for i in raw
        ]
        return ToolResult(ok=True, data={"issues": issues, "count": len(issues)})


# ---------------------------------------------------------------------------
# Tool 3 — Get single issue
# ---------------------------------------------------------------------------

class LinearGetIssueTool(Tool):
    name = "linear_get_issue"
    description = "Get full details of a Linear issue by its identifier (e.g. 'ENG-123') or internal ID."
    parameters = {
        "type": "object",
        "properties": {
            "identifier": {"type": "string", "description": "Issue identifier like 'ENG-123', or the internal UUID."},
        },
        "required": ["identifier"],
    }

    async def run(self, identifier: str) -> ToolResult:
        token = await _get_token()
        if not token:
            return _no_token_error()

        is_uuid = len(identifier) > 10 and "-" in identifier and not identifier[0].isalpha()
        if is_uuid:
            filter_str = f'id: {{ eq: "{identifier}" }}'
        else:
            filter_str = f'identifier: {{ eq: "{identifier.upper()}" }}'

        query = f"""
        query {{
          issue({filter_str}) {{
            id identifier title description
            state {{ name }}
            assignee {{ name email }}
            priority
            createdAt updatedAt
            url
            team {{ name key }}
            project {{ name }}
            comments {{ totalCount }}
          }}
        }}
        """
        status, data = await _gql(token, query)
        if status != 200 or "errors" in data:
            return ToolResult(ok=False, error=f"Issue '{identifier}' not found: {_gql_error(data)}")
        issue = data.get("data", {}).get("issue")
        if not issue:
            return ToolResult(ok=False, error=f"Issue '{identifier}' not found.")
        priority_label = {0: "No priority", 1: "Urgent", 2: "High", 3: "Medium", 4: "Low"}
        return ToolResult(ok=True, data={
            "id": issue["id"],
            "identifier": issue.get("identifier"),
            "title": issue.get("title"),
            "description": (issue.get("description") or "")[:1000],
            "state": (issue.get("state") or {}).get("name"),
            "assignee": (issue.get("assignee") or {}).get("name"),
            "priority": priority_label.get(issue.get("priority", 0), "Unknown"),
            "team": (issue.get("team") or {}).get("key"),
            "project": (issue.get("project") or {}).get("name"),
            "comment_count": issue.get("comments", {}).get("totalCount", 0),
            "created": issue.get("createdAt"),
            "updated": issue.get("updatedAt"),
            "url": issue.get("url"),
        })


# ---------------------------------------------------------------------------
# Tool 4 — Get projects
# ---------------------------------------------------------------------------

class LinearGetProjectsTool(Tool):
    name = "linear_get_projects"
    description = "List Linear projects (Initiatives). Returns name, state, progress, and team."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "number", "description": "Max projects to return. Default 20."},
        },
        "required": [],
    }

    async def run(self, limit: int = 20) -> ToolResult:
        token = await _get_token()
        if not token:
            return _no_token_error()
        query = f"""
        query {{
          projects(first: {min(limit, 50)}) {{
            nodes {{
              id name description state progress
              startDate targetDate
              teams {{ nodes {{ key name }} }}
            }}
          }}
        }}
        """
        status, data = await _gql(token, query)
        if status != 200 or "errors" in data:
            return ToolResult(ok=False, error=f"Linear API error: {_gql_error(data)}")
        raw = data.get("data", {}).get("projects", {}).get("nodes", [])
        projects = [
            {
                "id": p["id"],
                "name": p["name"],
                "description": (p.get("description") or "")[:200],
                "state": p.get("state"),
                "progress": p.get("progress"),
                "start_date": p.get("startDate"),
                "target_date": p.get("targetDate"),
                "teams": [t["key"] for t in (p.get("teams") or {}).get("nodes", [])],
            }
            for p in raw
        ]
        return ToolResult(ok=True, data={"projects": projects, "count": len(projects)})


# ---------------------------------------------------------------------------
# Tool 5 — Create issue (sensitive)
# ---------------------------------------------------------------------------

class LinearCreateIssueTool(Tool):
    name = "linear_create_issue"
    description = "Create a new Linear issue. SENSITIVE: creates a permanent record. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "team_key": {"type": "string", "description": "Team key, e.g. 'ENG' or 'OPS'."},
            "title": {"type": "string", "description": "Issue title."},
            "description": {"type": "string", "description": "Issue description (markdown supported)."},
            "priority": {"type": "number", "description": "Priority: 1=Urgent, 2=High, 3=Medium, 4=Low. Default: 3."},
        },
        "required": ["team_key", "title"],
    }

    async def run(self, team_key: str, title: str, description: str = "", priority: int = 3) -> ToolResult:
        token = await _get_token()
        if not token:
            return _no_token_error()
        team_query = f"""
        query {{
          teams(filter: {{ key: {{ eq: "{team_key.upper()}" }} }}) {{
            nodes {{ id name }}
          }}
        }}
        """
        _, team_data = await _gql(token, team_query)
        teams = team_data.get("data", {}).get("teams", {}).get("nodes", [])
        if not teams:
            return ToolResult(ok=False, error=f"Team '{team_key}' not found.")
        team_id = teams[0]["id"]

        mutation = """
        mutation CreateIssue($teamId: String!, $title: String!, $description: String, $priority: Int) {
          issueCreate(input: {
            teamId: $teamId
            title: $title
            description: $description
            priority: $priority
          }) {
            success
            issue { id identifier title url }
          }
        }
        """
        status, data = await _gql(token, mutation, {
            "teamId": team_id,
            "title": title,
            "description": description or None,
            "priority": priority,
        })
        if status != 200 or "errors" in data:
            return ToolResult(ok=False, error=f"Failed to create issue: {_gql_error(data)}")
        result = data.get("data", {}).get("issueCreate", {})
        if not result.get("success"):
            return ToolResult(ok=False, error="Issue creation failed.")
        issue = result.get("issue", {})
        return ToolResult(ok=True, data={
            "id": issue.get("id"),
            "identifier": issue.get("identifier"),
            "title": issue.get("title"),
            "url": issue.get("url"),
        })


# ---------------------------------------------------------------------------
# Tool 6 — Update issue (sensitive)
# ---------------------------------------------------------------------------

class LinearUpdateIssueTool(Tool):
    name = "linear_update_issue"
    description = "Update a Linear issue's title, priority, or state. SENSITIVE: modifies existing data. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "issue_id": {"type": "string", "description": "Issue internal ID (UUID) or identifier like 'ENG-123'."},
            "title": {"type": "string", "description": "New title (optional)."},
            "priority": {"type": "number", "description": "New priority: 1=Urgent, 2=High, 3=Medium, 4=Low (optional)."},
            "state_name": {"type": "string", "description": "New state name e.g. 'In Progress', 'Done' (optional)."},
        },
        "required": ["issue_id"],
    }

    async def run(self, issue_id: str, title: str | None = None, priority: int | None = None, state_name: str | None = None) -> ToolResult:
        token = await _get_token()
        if not token:
            return _no_token_error()

        is_identifier = not (len(issue_id) > 20 and issue_id.count("-") > 1)
        if is_identifier:
            lookup = f"""
            query {{
              issue(identifier: {{ eq: "{issue_id.upper()}" }}) {{ id }}
            }}
            """
            _, ldata = await _gql(token, lookup)
            resolved = (ldata.get("data") or {}).get("issue", {}).get("id")
            if not resolved:
                return ToolResult(ok=False, error=f"Issue '{issue_id}' not found.")
            issue_id = resolved

        input_fields: dict = {}
        if title:
            input_fields["title"] = title
        if priority is not None:
            input_fields["priority"] = priority
        if state_name:
            state_q = f"""
            query {{
              workflowStates(filter: {{ name: {{ eq: "{state_name}" }} }}) {{
                nodes {{ id name }}
              }}
            }}
            """
            _, sdata = await _gql(token, state_q)
            states = (sdata.get("data") or {}).get("workflowStates", {}).get("nodes", [])
            if not states:
                return ToolResult(ok=False, error=f"State '{state_name}' not found.")
            input_fields["stateId"] = states[0]["id"]

        if not input_fields:
            return ToolResult(ok=False, error="Nothing to update. Provide title, priority, or state_name.")

        mutation = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue { id identifier title }
          }
        }
        """
        status, data = await _gql(token, mutation, {"id": issue_id, "input": input_fields})
        if status != 200 or "errors" in data:
            return ToolResult(ok=False, error=f"Update failed: {_gql_error(data)}")
        result = data.get("data", {}).get("issueUpdate", {})
        if not result.get("success"):
            return ToolResult(ok=False, error="Issue update failed.")
        issue = result.get("issue", {})
        return ToolResult(ok=True, data={"id": issue.get("id"), "identifier": issue.get("identifier"), "updated": list(input_fields.keys())})


# ---------------------------------------------------------------------------
# Tool 7 — Add comment (sensitive)
# ---------------------------------------------------------------------------

class LinearAddCommentTool(Tool):
    name = "linear_add_comment"
    description = "Add a comment to a Linear issue. SENSITIVE: creates a permanent comment. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "issue_id": {"type": "string", "description": "Issue internal ID (UUID) or identifier like 'ENG-123'."},
            "body": {"type": "string", "description": "Comment text (markdown supported)."},
        },
        "required": ["issue_id", "body"],
    }

    async def run(self, issue_id: str, body: str) -> ToolResult:
        token = await _get_token()
        if not token:
            return _no_token_error()

        is_identifier = not (len(issue_id) > 20 and issue_id.count("-") > 1)
        if is_identifier:
            lookup = f"""
            query {{
              issue(identifier: {{ eq: "{issue_id.upper()}" }}) {{ id }}
            }}
            """
            _, ldata = await _gql(token, lookup)
            resolved = (ldata.get("data") or {}).get("issue", {}).get("id")
            if not resolved:
                return ToolResult(ok=False, error=f"Issue '{issue_id}' not found.")
            issue_id = resolved

        mutation = """
        mutation AddComment($issueId: String!, $body: String!) {
          commentCreate(input: { issueId: $issueId, body: $body }) {
            success
            comment { id createdAt }
          }
        }
        """
        status, data = await _gql(token, mutation, {"issueId": issue_id, "body": body})
        if status != 200 or "errors" in data:
            return ToolResult(ok=False, error=f"Failed to add comment: {_gql_error(data)}")
        result = data.get("data", {}).get("commentCreate", {})
        if not result.get("success"):
            return ToolResult(ok=False, error="Comment creation failed.")
        return ToolResult(ok=True, data={"comment_id": result.get("comment", {}).get("id"), "text": body[:100]})
