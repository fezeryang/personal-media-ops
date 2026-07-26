# Installed Helper v1 Observation

## Allowed Evidence

Only these commands were executed:

```bash
sudo -n /usr/local/sbin/mediaops-release version
sudo -n /usr/local/sbin/mediaops-release status
```

The installed file itself, root credentials, sudoers, `.env`, cookies, QR
codes, browser state, and private keys were not read.

## Observed Contract

- `version` prints exactly `1`.
- `status` identifies the host, action, application root, and helper version.
- It reports `api=active`, `worker=active`,
  `frontend_build=present`, and `published_frontend=present`.
- It runs the BaoTa Nginx configuration check.
- It calls the local FastAPI health endpoint and prints its JSON response.

The user supplied the full subcommand allowlist:

```text
version
status
publish-frontend
restart-services
nginx-check
nginx-reload
verify
finalize
```

Only `version` and `status` were authorized in this task. Repository source for
the remaining commands must implement fixed, minimal behavior consistent with
the standard release sequence; it must not be installed automatically.

## Deployment Integration Decision

The deploy orchestrator performs backup, Git, dependency, test, and build work
as `mediaops`. After all gates pass, it calls only:

```bash
sudo -n /usr/local/sbin/mediaops-release finalize
```

The helper performs privileged activation and verification. This reduces the
sudo surface and prevents the deploy script from assembling arbitrary root
commands.
