# Panelo Deploy Quickstart

This setup runs Panelo behind nginx at `/panelo` using `uv` + `systemd`.

## One-time host setup

1. Install `uv`.
2. Install `envsubst` (usually from package `gettext-base`).
3. Ensure nginx is installed and serving your site.

## App deploy flow

From repo root:

```bash
git pull
make deploy
```

That will sync dependencies, install/update `/etc/systemd/system/panelo.service`,
restart the service, and show status.

The installed service runs from `.venv/bin/panelo-web` by default (not `uv run`).

## nginx update

1. Copy the snippet into your nginx server block (or include it):

```bash
cat deploy/nginx-panelo.conf
```

2. Test and reload nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Persistence and cleanup

- Artifact storage path is set in the systemd unit as `PANELO_RUNS_ROOT`
- Default is repository-local `runs/` unless overridden
- Auto cleanup on app startup and each run:
  - `PANELO_RUN_RETENTION_DAYS=30`

## Useful commands

```bash
systemctl status panelo --no-pager
journalctl -u panelo -f
```
