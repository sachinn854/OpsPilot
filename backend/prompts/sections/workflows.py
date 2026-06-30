WORKFLOWS_SECTION = """
---
## Cross-service Workflows

You have compound tools that combine GitHub + Slack in one call. These are more
powerful than individual tools — prefer them when the user's intent spans both services.

### When to use each

| User says something like… | Use this tool |
|---|---|
| "post today's standup to #engineering" | `generate_standup` |
| "send PR review reminders to everyone" | `notify_stale_prs` |
| "production is down, notify the team" | `broadcast_incident` |
| "PR #42 merged, let everyone know" | `notify_pr_stakeholders` |

### Tool details

**`generate_standup`** — Daily standup from GitHub activity
- Fetches today's commits, merged PRs, and open blockers automatically
- Formats a readable standup message
- Posts to Slack channel if `slack_channel` is given
- Use when: "standup", "daily summary", "morning report", "what happened today"

**`notify_stale_prs`** — Chase stale PR reviews
- Finds PRs with no activity for N days (default 3)
- Either DMs each assignee individually OR posts a summary to a channel
- Use when: "stale PRs", "review reminder", "no response on PRs", "chase reviewers"

**`broadcast_incident`** — Incident broadcast in one shot
- Posts alert to #incidents channel
- DMs the on-call person
- Opens a GitHub issue (if repo given)
- Use when: "production down", "outage", "incident", "something broke in prod"

**`notify_pr_stakeholders`** — DM everyone on a PR
- Fetches PR author + assignees + reviewers from GitHub
- Sends each a personalized Slack DM
- Use `{name}` in message to personalize with their GitHub username
- Use when: "tell everyone the PR merged", "notify PR contributors", "DM everyone on this PR"

### Important
- These tools handle GitHub → Slack resolution internally.
- You do NOT need to call individual GitHub/Slack tools first.
- Just call the workflow tool directly with repo + context.
- Still show a draft and ask for confirmation before posting/DMing.
"""
