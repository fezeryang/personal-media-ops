---
name: mediaops-server
description: Operate Personal Media Ops production safely. Use for deployment, service checks, production logs, unreachable API diagnosis, idle Worker diagnosis, frontend version checks, GitHub/server revision comparison, Nginx and FastAPI verification, SQLite backup preparation, read-only production diagnostics, controlled deployment commands, and post-release health checks.
---

# MediaOps Server Operations

Operate `mediaops-prod` with evidence-first, bounded commands. Default to
read-only diagnosis. Never claim a server action succeeded without its output
and a follow-up check.

## Load the Right Context

Before acting:

1. Read [references/server-inventory.md](references/server-inventory.md).
2. For deployments, backups, permissions, or recovery planning, also read
   [references/deployment.md](references/deployment.md).
3. Read the repository's root `AGENTS.md` and relevant deployment documentation.
4. State the target host, requested operation, and whether it is read-only.

## Connection Boundary

Use the SSH alias in `MEDIAOPS_SSH_HOST`, defaulting to `mediaops-prod`. Do not
embed `mediaops@47.105.36.220` in commands or scripts.

Before connecting, inspect the local SSH resolution:

```bash
ssh -G "${MEDIAOPS_SSH_HOST:-mediaops-prod}"
```

Connect non-interactively:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 mediaops-prod '<read-only command>'
```

If the alias, key, or network is unavailable, report the missing prerequisite
once and stop. Never request, print, or retry an interactive password. If the
execution environment cannot access production, say so plainly.

## Use the Repository Tools

Run the canonical tools through the dispatcher:

```bash
.agents/skills/mediaops-server/scripts/run-server-tool.sh connect
.agents/skills/mediaops-server/scripts/run-server-tool.sh status
.agents/skills/mediaops-server/scripts/run-server-tool.sh healthcheck
.agents/skills/mediaops-server/scripts/run-server-tool.sh logs --api --lines 200
.agents/skills/mediaops-server/scripts/run-server-tool.sh backup
.agents/skills/mediaops-server/scripts/run-server-tool.sh deploy --commit <sha>
```

`connect`, `status`, and `healthcheck` are read-only. Log reads are bounded
unless `--follow` is explicit. `backup` and `deploy` are dry runs unless
`--execute` is provided.

## Diagnostic Workflow

1. Run `connect`, then `status`.
2. Compare the server commit with the expected GitHub `main` commit.
3. Check the local API and public routes with `healthcheck --with-ssh`.
4. Read only the relevant bounded log source.
5. Form a diagnosis from the collected evidence.
6. Propose the smallest repair and identify whether it requires `mediaops` or
   root privileges.

Do not restart every service without evidence. Do not treat permission failures
as proof that a service or file is absent.

## Deployment Workflow

Start with a dry run:

```bash
scripts/server/deploy.sh --commit <origin-main-sha>
```

Before any mutation, confirm the host, clean server worktree, old commit, target
commit, backup destination, and exact actions. A requested deployment may run
the non-root preparation with `--execute`. Use `--root-stage` only when root or
reviewed passwordless sudo authorization is explicitly in scope.

If root permission is unavailable, stop after code preparation, report
“代码准备完成，生产操作待执行”, and return the exact root command list. Do not
pretend the release is live.

## Production Safety Rules

- Never edit code or built JS/CSS directly on production.
- Never modify `/opt/mediacrawler`.
- Never delete `/var/lib/mediaops`, clear `/var/log/mediaops`, or remove browser
  login state.
- Back up SQLite before a migration, restore, or deployment.
- Never use `git reset --hard`, interactive sudo, or unreviewed wildcard deletion.
- Do not alter BaoTa/Nginx, systemd, sudoers, firewall, ownership, or packages
  unless the task explicitly authorizes that operation.
- Do not expose `.env`, cookies, tokens, private keys, QR codes, or task data.
- Every production action requires command output and health verification.
