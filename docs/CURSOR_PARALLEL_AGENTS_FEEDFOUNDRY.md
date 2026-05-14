# FeedFoundry — Cursor parallel agents playbook

This document implements the **“Parallel agents on one app (FeedFoundry)”** runbook: what Cursor actually provides, how to start **six parallel Cloud Agent** runs on one repo, and how that ties to **Git branches** and the **integration** branch.

> **Important:** A chat assistant in the IDE **cannot** start Cursor Cloud Agents or open the Agents Window for you. **You** start agents from Cursor Web, the Desktop Cloud UI, or other entry points below.

---

## 1. Agents Window vs Command Palette (`verify-palette`)

Cursor’s UI and command titles have shifted between docs and releases. **Try these exact Command Palette substrings** (`Cmd+Shift+P` on macOS, `Ctrl+Shift+P` on Windows/Linux):

| Search substring | Source |
|------------------|--------|
| **`Agents Window`** | [Cursor 3.0 changelog](https://cursor.com/changelog/3-0): *“Cmd+Shift+P -> Agents Window”* |
| **`Open Agent Window`** | [Glass marketing copy](https://cursor.com/en-US/glass) (singular **Agent**) |
| **`Open Agents Window`** | [Agents Window doc](https://cursor.com/docs/agent/agents-window) (plural **Agents**) |
| **`Open Editor Window`** | Same Agents Window doc — switches back to the classic editor |

If **none** of these appear:

- Your build or **team/enterprise policy** may hide the Agents Window ([Agents Window doc](https://cursor.com/docs/agent/agents-window) mentions enterprise rollout).
- Use **Cloud Agents** (section 2) or **multiple local Agent Tabs** (see [Cursor 3.0 changelog](https://cursor.com/changelog/3-0) — Agent Tabs; changelog also notes **cloud agents were removed from the Editor** in favor of other surfaces).

This repo cannot read your palette; use the substrings above until a command matches.

---

## 2. Six parallel Cloud Agents on FeedFoundry (`cloud-six-lanes`)

Cursor **Cloud Agents** run in **isolated cloud environments**, clone from **GitHub/GitLab**, and push work as branches/PRs. Cursor documents that you may run **many agents in parallel**. See [Cloud Agents](https://cursor.com/docs/cloud-agent).

### 2.1 Where to start them

1. **Web (recommended for “six at once”):** [https://cursor.com/agents](https://cursor.com/agents)
2. **Desktop:** In the agent UI, use the **dropdown under the agent input** and choose **Cloud** (wording may vary slightly by build — same doc: *“Select Cloud in the dropdown under the agent input”*).

Other entry points (Slack, GitHub `@cursor`, Linear, API) are optional; see the same doc.

### 2.2 Control rod (paste at the top of **every** lane prompt)

```text
Do not invent extra product scope. Do not generalise the platform. Do not redesign unrelated systems. The only accepted work is the named lane. If you find unrelated issues, write them in a TODO section and keep moving.
```

### 2.3 Read first (every lane)

- [docs/MVP_PARALLEL_CONTRACT.md](MVP_PARALLEL_CONTRACT.md)
- [.cursor/rules/feedfoundry-mvp.mdc](../.cursor/rules/feedfoundry-mvp.mdc)

### 2.4 Six lanes → branches → Cloud Agent checklist

Start **one Cloud Agent per row** (six separate runs). Each run:

| Step | Action |
|------|--------|
| 1 | Repository: **FeedFoundry** (GitHub remote your Cursor account can access). |
| 2 | Branch: use the **lane branch** in the table below (create or push if missing). |
| 3 | Paste **control rod** + lane-specific instructions (from your MVP brief / contract lane table). |
| 4 | Require the agent to read **MVP_PARALLEL_CONTRACT** + **feedfoundry-mvp** rule file first. |
| 5 | Handoff: changed files, migrations, test commands, integration points for other lanes. |

| Lane | Scope (summary) | Git branch |
|------|-------------------|------------|
| **A** | Auth / account ownership | `agent/auth-account-ownership` |
| **B** | Processing-time ledger, goodwill, reserve/consume/release | `agent/processing-time-ledger` |
| **C** | Stripe Checkout + webhooks (annual + top-up) | `agent/stripe-access-processing-time` |
| **D** | Customer dashboard / upload / jobs / outputs UI | `agent/customer-dashboard-mvp` |
| **E** | Admin ops | `agent/admin-ops-mvp` |
| **F** | Railway / AI runtime controls | `agent/railway-ai-controls` |

**Do not** use the integration branch as the working branch for A–F; see section 4.

---

## 3. Permissions and troubleshooting (`permissions`)

From [Cloud Agents — troubleshooting](https://cursor.com/docs/cloud-agent):

| Issue | What to check |
|-------|----------------|
| **Runs do not start** | Logged in; **GitHub or GitLab** connected with correct account; **repository read-write** access for push; **paid Cursor plan** where required. |
| **Secrets missing in cloud** | Add secrets in **[cursor.com/dashboard/cloud-agents](https://cursor.com/dashboard/cloud-agents)** (team/workspace scoped). Restart the agent after adding secrets. |
| **Spend / billing** | First-time Cloud Agent use may prompt for a **spend limit** ([Cloud Agents — Billing](https://cursor.com/docs/cloud-agent)). |
| **Team policy** | Enterprise/team admins can restrict Cloud Agents, secrets, or integrations ([Cloud Agents doc](https://cursor.com/docs/cloud-agent), settings links therein). |

**Git:** Cloud agents clone from the remote; ensure lane branches exist or let the agent create them from `main` / `mvp/private-pilot-v01` per your process.

---

## 4. Single integration branch and merge order (`merge-handoff`)

### 4.1 Integration branch in **this** repo

- **`mvp/private-pilot-v01`** exists on `origin` and is the **private pilot integration line** used for merged MVP work.
- The contract also names **`agent/integration-mvp-v01`** for merge captain **G**; that branch **may or may not** exist yet. If you add captain work, create `agent/integration-mvp-v01` from `mvp/private-pilot-v01` or merge lane PRs into `mvp/private-pilot-v01` directly — **pick one integration line** and stick to it so PRs have a clear target.

### 4.2 Merge order (from [MVP_PARALLEL_CONTRACT.md](MVP_PARALLEL_CONTRACT.md))

- **Core sequencing:** **A** and **B** first; **C, D, E, F** can run in parallel against the contract.
- **Suggested merge order after A/B land:** **A → B → F → C → D → E** (captain adjusts for conflicts).
- **Operations table:** merge steps 4–5 reference the same order; then smoke test and ship.

Lane **G** (integration captain) reconciles branches; use PRs into **`mvp/private-pilot-v01`** (or `agent/integration-mvp-v01` if you introduce it).

### 4.3 Local worktrees (optional, matches contract)

Use **one git worktree per lane** so local and cloud work do not stomp the same tree. Example base path pattern: `../feedfoundry-agent-<lane>` with branch checked out per [MVP_PARALLEL_CONTRACT.md](MVP_PARALLEL_CONTRACT.md).

---

## 5. Quick verification checklist

- [ ] Palette: `Agents Window`, `Open Agent Window`, `Open Agents Window`, `Open Editor Window`.
- [ ] Web: [cursor.com/agents](https://cursor.com/agents) — start a test Cloud Agent on **FeedFoundry**.
- [ ] GitHub: RW + branch strategy agreed.
- [ ] Billing / spend limit / secrets dashboard if cloud runs fail.
- [ ] Six lane agents started (or queued) with control rod + contract reads.

---

## References (external)

- [Agents Window](https://cursor.com/docs/agent/agents-window)
- [Cursor 3.0 changelog](https://cursor.com/changelog/3-0)
- [Glass](https://cursor.com/en-US/glass)
- [Cloud Agents](https://cursor.com/docs/cloud-agent)
- [Cloud agents dashboard / secrets](https://cursor.com/dashboard/cloud-agents)
