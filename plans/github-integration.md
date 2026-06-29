# GitHub Deep Integration Plan

## Goal
User apna GitHub Personal Access Token frontend mein set kare → uske saare repos,
issues, PRs, code sab kuch AI se query kar sake. Ek token → poora GitHub connected.

---

## Current State (kya hai abhi)

| Tool | Status |
|------|--------|
| `github_list_issues` | ✅ Done |
| `github_list_prs` | ✅ Done |
| `github_list_commits` | ✅ Done |

Token abhi `.env` mein hardcoded hai — single user, single token.

---

## Phase G1 — GitHub Tools Expand (Read-Only)

Ye sab tools `backend/tools/github.py` mein add honge aur `GitHubServer` mein register honge.

### Tools to Build

| # | Tool Name | Kya karega | Endpoint |
|---|-----------|-----------|----------|
| 1 | `github_repo_info` | Stars, forks, description, language, topics, last push | `GET /repos/{owner}/{repo}` |
| 2 | `github_readme` | README.md content fetch karo (markdown) | `GET /repos/{owner}/{repo}/readme` |
| 3 | `github_file_tree` | Poora folder/file structure | `GET /repos/{owner}/{repo}/git/trees/HEAD?recursive=1` |
| 4 | `github_file_content` | Koi bhi specific file padho (code, config) | `GET /repos/{owner}/{repo}/contents/{path}` |
| 5 | `github_releases` | Latest releases aur changelogs | `GET /repos/{owner}/{repo}/releases` |
| 6 | `github_contributors` | Top contributors + commit count | `GET /repos/{owner}/{repo}/contributors` |
| 7 | `github_branches` | Branches list + default branch | `GET /repos/{owner}/{repo}/branches` |
| 8 | `github_search_code` | Repo ke andar code/text search | `GET /search/code?q={query}+repo:{owner}/{repo}` |
| 9 | `github_user_repos` | User ke saare repos list karo | `GET /user/repos` |
| 10 | `github_repo_languages` | Repo mein kaunsi languages hain + percentage | `GET /repos/{owner}/{repo}/languages` |

### Repo Analyze Flow
```
User: "https://github.com/owner/repo batao"
  ↓
github_repo_info    → basic stats
github_readme       → README content
github_file_tree    → structure
github_repo_languages → tech stack
  ↓
Copilot sab mila ke ek clear summary deta hai
```

---

## Phase G2 — Per-User Token Management

### Problem
Abhi `.env` mein ek global token hai. Har user ka alag token chahiye.

### Solution — `IntegrationToken` DB Table

```
integrations table:
  id          UUID
  org_id      string (multi-tenant)
  service     string  (github | slack | jira | linear)
  token       string  (encrypted at rest)
  metadata    JSON    (username, workspace, etc.)
  created_at  datetime
```

### Token Flow
```
Frontend Settings page
  → User enters GitHub PAT
  → POST /v1/integrations/github { token: "ghp_..." }
  → Backend encrypts + stores in DB
  → Tools fetch token from DB per request (not from .env)
```

### Files to Create/Modify
- `backend/db/models.py` → `IntegrationToken` model add karo
- `backend/integrations/store.py` → token save/fetch/delete
- `backend/integrations/encrypt.py` → AES encryption (Fernet)
- `backend/api/routes/integrations.py` → REST endpoints
- `frontend/src/components/Settings.jsx` → Settings page
- `frontend/src/App.jsx` → Settings nav item add karo

### API Endpoints
```
POST   /v1/integrations/{service}     → token save karo
GET    /v1/integrations               → connected services list
DELETE /v1/integrations/{service}     → disconnect karo
GET    /v1/integrations/{service}/verify → token valid hai?
```

---

## Phase G3 — Write Operations (HITL Protected)

Ye sensitive tools hain — HITL approval ke baad hi execute honge.

| # | Tool Name | Kya karega |
|---|-----------|-----------|
| 11 | `github_create_issue` | Naya issue create karo |
| 12 | `github_comment_on_issue` | Issue pe comment karo |
| 13 | `github_comment_on_pr` | PR pe review comment |
| 14 | `github_close_issue` | Issue band karo |
| 15 | `github_create_branch` | Naya branch banao |

Inke liye `sensitive = True` flag set hoga — automatically HITL mein jayenge.

---

## Phase G4 — GitHub Webhooks (Real-time)

User apne repo pe webhook lagaye → events aate hain → agent automatically react kare.

### Events to Handle
| Event | Action |
|-------|--------|
| `push` | New commit → summary generate karo |
| `pull_request.opened` | New PR → auto-review summary |
| `issues.opened` | New issue → categorize + assign suggest karo |
| `release.published` | New release → changelog summary |

### Files to Create
- `backend/api/routes/webhooks.py` → `POST /v1/webhooks/github`
- `backend/workers/webhook_handler.py` → Celery task to process event

---

## File Structure (after all phases)

```
backend/
  tools/
    github.py              ← expand karo (10 read tools + 5 write tools)
  integrations/
    store.py               ← NEW: token save/fetch from DB
    encrypt.py             ← NEW: AES encryption
  api/routes/
    integrations.py        ← NEW: /v1/integrations endpoints
    webhooks.py            ← NEW: /v1/webhooks/github
  db/
    models.py              ← IntegrationToken model add karo
  mcp/servers/
    github_server.py       ← nayi tools register karo

frontend/src/
  components/
    Settings.jsx           ← NEW: token connect page
  App.jsx                  ← Settings nav add karo
```

---

## Build Order

```
Step 1: github.py mein 10 read tools add karo
Step 2: GitHubServer mein register karo
Step 3: Test karo — repo URL deke chat karo
Step 4: IntegrationToken DB model + encrypt
Step 5: /v1/integrations API routes
Step 6: Settings.jsx frontend page
Step 7: Write tools (create_issue etc.) with HITL
Step 8: Webhooks (optional, last mein)
```

---

## Config (.env additions needed)

```env
# Already exists:
GITHUB_TOKEN=ghp_...

# New — for token encryption:
ENCRYPTION_KEY=          # Fernet key, generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Status

| Phase | Status |
|-------|--------|
| G1 — 17 GitHub read + list tools | ✅ Done |
| G2 — Per-user token management + Settings UI | ✅ Done |
| G3 — Write tools + HITL security agent fix | ✅ Done |
| G4 — GitHub Webhooks | ✅ Done |

## Done When

- [x] User frontend mein GitHub token set kar sake
- [x] `/v1/integrations/github/verify` se confirm ho ki token valid hai
- [x] Chat mein repo URL paste karo → auto summary aa jaye
- [x] `github_file_content` se koi bhi file padh sake
- [x] Write tools HITL se protected hain
- [x] Webhooks: push/PR/issue/release events receive + process karo
