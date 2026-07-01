# OpenMontage Runner — Deployment

The runner service (`runner/`) driving OpenMontage headlessly. Runs as `montage` on the worker (CX33, `62.238.38.97`), exposed via Caddy at `video.thevpncompany.net`.

## Prerequisites
- DNS: `A  video.thevpncompany.net → 62.238.38.97`.
- Env (append to `/opt/openmontage/.env`, mode 600 — secrets pasted by the operator, never committed):
  - `RUNNER_SECRET` — shared secret for `X-Runner-Secret` (also set in the bot).
  - `RUNNER_PORT=8088`
  - `RUNNER_PUBLIC_BASE` — public base URL for uploaded videos, e.g. `https://<hetzner-s3-host>/<bucket>`.
  - `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` — Hetzner S3.
  - (Provider + Anthropic keys already present from the spike.)

## systemd unit
`/etc/systemd/system/openmontage-runner.service`:
```ini
[Unit]
Description=OpenMontage Runner
After=network-online.target
Wants=network-online.target

[Service]
User=montage
WorkingDirectory=/opt/openmontage
EnvironmentFile=/opt/openmontage/.env
ExecStart=/opt/openmontage/.venv/bin/uvicorn --factory runner.main:build_app --host 127.0.0.1 --port 8088
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
```
systemctl daemon-reload && systemctl enable --now openmontage-runner
journalctl -u openmontage-runner -n 30 --no-pager
curl -s localhost:8088/health   # {"ok":true,...}
```

## Caddy
Append to the worker Caddyfile, then `systemctl reload caddy`:
```
video.thevpncompany.net {
    reverse_proxy 127.0.0.1:8088
}
```
Verify: `curl -s https://video.thevpncompany.net/health` → 200.

## Auth smoke
- `POST /generate-video` without `X-Runner-Secret` → 401.
- With the secret + a known pipeline → 202 + `{jobId}`.

## Runner API
- `POST /generate-video` (X-Runner-Secret) `{pipeline, callbackUrl, articleId?, mediaProfile?, budgetCapUsd?, inputs}` → `202 {jobId}`
- `GET /jobs/{id}` (X-Runner-Secret) → job status/result
- `GET /health` → `{ok, queueDepth, running}`

## Notes
- Single-concurrency queue (SQLite at `runner/runner.db`); one job at a time.
- Per-job workspace `projects/<jobId>/` is purged after each job.
- Cost = agent token cost (`claude --output-format json`) + Σ asset_manifest media costs; reported in the callback.
