# Production Operations Guidelines

> Executable contracts for Personal Media Ops server tooling.

## Guidelines Index

| Guide | Description | Status |
| --- | --- | --- |
| [Server Deployment](./server-deployment.md) | SSH, diagnostics, backup, deployment, and privilege contracts | Active |

## Quality Check

Run from the repository root:

```bash
bash -n scripts/server/*.sh
python3 /home/fezer/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .agents/skills/mediaops-server
```

If ShellCheck is installed, also run:

```bash
shellcheck scripts/server/*.sh scripts/server/lib/common.bash
```

Dry-run backup and deployment commands must complete without SSH access.

**Language**: All code-spec documentation should be written in **English**.
