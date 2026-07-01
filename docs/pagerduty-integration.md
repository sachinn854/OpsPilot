# PagerDuty Integration — Planning Doc

## What is PagerDuty?
Incident alerting + on-call management tool. Used by DevOps/SRE teams for 24/7 production monitoring.
PagerDuty does NOT have direct server access — it receives alerts via webhooks from monitoring tools (Prometheus, Datadog, CloudWatch) and notifies the right engineer.

## Flow
```
Server failure
    → Monitoring tool (Prometheus/Datadog)
    → PagerDuty webhook
    → On-call engineer gets called/SMS
    → Engineer resolves
    → Incident closed
```

## What to build

### Tools (`backend/tools/pagerduty.py`)
| Tool | Type | Description |
|------|------|-------------|
| `pd_list_incidents` | read | List active/recent incidents |
| `pd_get_incident` | read | Get incident details by ID |
| `pd_get_oncall` | read | Who is on-call right now? |
| `pd_list_services` | read | List monitored services |
| `pd_acknowledge_incident` | write (sensitive) | Acknowledge an incident |
| `pd_resolve_incident` | write (sensitive) | Resolve an incident |
| `pd_create_incident` | write (sensitive) | Manually trigger an incident |

### Backend files to create
- `backend/tools/pagerduty.py` — 7 tools using PagerDuty REST API v2
- `backend/mcp/servers/pagerduty_server.py` — MCP server wrapper

### Backend files to update
- `backend/api/routes/integrations.py` — add `_verify_pagerduty()` (call `/users/me`)
- `backend/api/deps.py` — register `PagerDutyServer` in registry
- `backend/core/tool_router.py` — add PagerDuty tools to `build_default_router()`
- `backend/config.py` — add `pagerduty` to `TOOLS_ENABLED`

### Frontend (`frontend/src/components/Settings.jsx`)
- Add PagerDuty card to `SERVICES` array
- Single field: API key (from PagerDuty → User Settings → API Access Keys)

## PagerDuty API
- Base URL: `https://api.pagerduty.com`
- Auth: `Authorization: Token token=<api_key>`
- Docs: https://developer.pagerduty.com/api-reference/

## Config
```
# .env
PAGERDUTY_API_KEY=   # optional env fallback
```
- `SUPPORTED_SERVICES` already includes `"pagerduty"` — no store.py change needed
- Add `pagerduty` to `TOOLS_ENABLED` in config.py

## Use cases in the copilot
- "Who is on-call right now?" → `pd_get_oncall`
- "Show me all active incidents" → `pd_list_incidents`
- "Acknowledge incident INC-123" → `pd_acknowledge_incident` (HITL)
- Auto-workflow: GitHub alert → PagerDuty incident → Slack notify → Jira ticket
