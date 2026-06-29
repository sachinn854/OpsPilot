# Integrations Roadmap — OpsPilot

Top applications jahan MCP / AI integrations sabse zyada use hote hain.
Priority = enterprise adoption + ops value + MCP ecosystem demand.

---

## Current State

| Service | Status |
|---------|--------|
| GitHub | ✅ Fully done (17 tools + webhooks) |
| Slack | 🔶 Token store done, tool mocked |
| Jira | 🔶 Token store only |
| Linear | 🔶 Token store only |

---

## Priority 1 — Communication & Alerts (sabse zyada use)

| # | Service | Kya karta hai | Tools to Build |
|---|---------|---------------|----------------|
| 1 | **Slack** | Team messaging, alerts, incident channels | `post_message`, `list_channels`, `get_messages`, `create_channel` |
| 2 | **Microsoft Teams** | Enterprise messaging (banks, MNCs) | `send_message`, `list_teams`, `list_channels` |
| 3 | **Discord** | Dev communities, bots, ops alerts | `send_message`, `list_servers` |
| 4 | **Gmail / Google Workspace** | Email alerts, reports, summaries | `send_email`, `list_emails`, `search_emails` |
| 5 | **PagerDuty** | Incident management, on-call alerts | `create_incident`, `list_incidents`, `ack_incident`, `resolve_incident` |

---

## Priority 2 — Project Management (dev teams ka core)

| # | Service | Kya karta hai | Tools to Build |
|---|---------|---------------|----------------|
| 6 | **Jira** | Bug tracking, sprints, epics | `list_issues`, `create_issue`, `update_issue`, `list_sprints`, `search_issues` |
| 7 | **Linear** | Modern issue tracker (startups) | `list_issues`, `create_issue`, `update_issue`, `list_cycles` |
| 8 | **Notion** | Docs + knowledge base + tasks | `search_pages`, `create_page`, `update_page`, `list_databases` |
| 9 | **Asana** | Task management, project timelines | `list_tasks`, `create_task`, `update_task` |
| 10 | **Trello** | Kanban boards | `list_boards`, `list_cards`, `create_card`, `move_card` |

---

## Priority 3 — Cloud & DevOps (ops copilot ke liye critical)

| # | Service | Kya karta hai | Tools to Build |
|---|---------|---------------|----------------|
| 11 | **AWS** | Cloud infra — EC2, S3, Lambda, CloudWatch | `list_ec2`, `describe_instance`, `get_logs`, `list_s3_buckets`, `invoke_lambda` |
| 12 | **Kubernetes** | Container orchestration | `list_pods`, `get_pod_logs`, `describe_deployment`, `restart_deployment` |
| 13 | **Vercel** | Frontend deployments | `list_deployments`, `get_deployment_logs`, `rollback` |
| 14 | **Netlify** | JAMstack deployments | `list_sites`, `list_deploys`, `get_deploy_log` |
| 15 | **GitLab** | Self-hosted Git (enterprises) | `list_repos`, `list_mrs`, `list_pipelines`, `get_pipeline_status` |

---

## Priority 4 — Monitoring & Observability

| # | Service | Kya karta hai | Tools to Build |
|---|---------|---------------|----------------|
| 16 | **Datadog** | Metrics, logs, APM, alerts | `list_monitors`, `get_metrics`, `list_alerts`, `search_logs` |
| 17 | **Sentry** | Error tracking, crash reports | `list_issues`, `get_issue`, `list_events`, `resolve_issue` |
| 18 | **Grafana** | Dashboards + alerts (already in project) | `list_dashboards`, `get_panel_data`, `list_alerts` |
| 19 | **New Relic** | APM + infrastructure monitoring | `get_metrics`, `list_alerts` |

---

## Priority 5 — Databases & Data

| # | Service | Kya karta hai | Tools to Build |
|---|---------|---------------|----------------|
| 20 | **PostgreSQL** | SQL queries (already basic done) | `execute_query`, `list_tables`, `describe_table` |
| 21 | **Supabase** | Postgres + Auth + Storage (BaaS) | `query`, `list_tables`, `storage_list` |
| 22 | **MongoDB** | NoSQL ops | `find`, `aggregate`, `list_collections` |
| 23 | **Airtable** | Spreadsheet-database hybrid | `list_bases`, `list_records`, `create_record`, `update_record` |

---

## Priority 6 — Business & CRM

| # | Service | Kya karta hai | Tools to Build |
|---|---------|---------------|----------------|
| 24 | **HubSpot** | CRM, deals, contacts, marketing | `list_contacts`, `create_contact`, `list_deals`, `create_deal` |
| 25 | **Salesforce** | Enterprise CRM | `list_leads`, `create_opportunity`, `list_cases` |
| 26 | **Stripe** | Payments, subscriptions, invoices | `list_customers`, `list_payments`, `create_invoice`, `list_subscriptions` |
| 27 | **Zendesk** | Customer support tickets | `list_tickets`, `create_ticket`, `update_ticket`, `reply_ticket` |

---

## Priority 7 — Documentation & Knowledge

| # | Service | Kya karta hai | Tools to Build |
|---|---------|---------------|----------------|
| 28 | **Confluence** | Atlassian wiki (pairs with Jira) | `search_pages`, `get_page`, `create_page`, `list_spaces` |
| 29 | **Google Drive** | Docs, Sheets, Slides storage | `list_files`, `search_files`, `read_file`, `create_doc` |
| 30 | **Dropbox** | File storage | `list_files`, `download_file` |

---

## Build Order (recommended)

```
Phase 1 — Already done:
  ✅ GitHub (17 tools + webhooks)

Phase 2 — Communication core:
  → Slack (real API)
  → PagerDuty
  → Gmail (optional)

Phase 3 — Project tracking:
  → Jira
  → Linear
  → Notion

Phase 4 — Cloud/DevOps:
  → AWS
  → Kubernetes
  → Sentry

Phase 5 — Business:
  → Stripe
  → HubSpot / Zendesk
  → Airtable
```

---

## Notes

- **MCP ecosystem mein sabse popular:** GitHub, Slack, Notion, Jira, Google Drive, Postgres, Stripe
- **Ops Copilot ke liye highest value:** GitHub ✅, Slack, PagerDuty, AWS, Kubernetes, Datadog, Sentry
- Har integration ke liye same pattern: token store → verify endpoint → tools → MCP server → webhook (optional)
