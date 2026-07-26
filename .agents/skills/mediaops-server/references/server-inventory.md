# MediaOps Production Inventory

This inventory contains operational locations only. It must never contain
passwords, private keys, tokens, cookies, or `.env` values.

## Environment

| Item | Value |
| --- | --- |
| Environment | `mediaops-prod` |
| Public IP | `47.105.36.220` |
| Operating system | Ubuntu 22.04 |
| Application user/group | `mediaops` / `mediaops` |
| Public URL | `https://ops.fezern8n.com` |
| Local API | `http://127.0.0.1:8000` |

## Application Paths

| Item | Path |
| --- | --- |
| Repository | `/opt/personal-media-ops` |
| Backend | `/opt/personal-media-ops/backend` |
| Frontend | `/opt/personal-media-ops/frontend` |
| Frontend build | `/opt/personal-media-ops/frontend/dist` |
| Nginx static root | `/www/wwwroot/ops.fezern8n.com` |
| Data root | `/var/lib/mediaops` |
| Log root | `/var/log/mediaops` |
| Backup root | `/var/backups/mediaops` |
| SQLite task database | `/var/lib/mediaops/mediaops.db` |
| Crawler output | `/var/lib/mediaops/crawler-output` |
| Crawler task logs | `/var/log/mediaops/crawler` |
| QR codes | `/var/lib/mediaops/qrcodes` |

## Services and Runtimes

| Item | Value |
| --- | --- |
| FastAPI service | `mediaops-api` |
| Crawler Worker service | `mediaops-crawler-worker` |
| BaoTa Nginx binary | `/www/server/nginx/sbin/nginx` |
| Node binary | `/www/server/nodejs/v22.22.3/bin/node` |
| Restricted release helper | `/usr/local/sbin/mediaops-release` |
| Release helper version | `1` |
| MediaCrawler checkout | `/opt/mediacrawler` |
| MediaCrawler Python | `/opt/mediacrawler/.venv/bin/python` |
| Reviewed Runner source | `/opt/personal-media-ops/scripts/crawler/run_mediacrawler.py` |
| Active Runner | `/var/lib/mediaops/bin/run_mediacrawler.py` |

The `mediaops` account can inspect the repository, install project
dependencies, run tests/builds, read permitted logs, call APIs, and check
process, port, disk, and memory status.

Routine static publication, application restarts, and Nginx validation/reload
must use the exact reviewed helper subcommands through `sudo -n`. Arbitrary root
commands, helper/sudoers installation, ownership changes, package/firewall/user
changes, and database deletion/restoration remain administrator-only.
