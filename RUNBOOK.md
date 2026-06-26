# RUNBOOK — QueueStorm Investigator

Copy-paste steps to bring the service up. No guessing, no missing commands. The
service needs **no API key** and makes **no external calls** in its default config.

The service listens on `0.0.0.0` and honors `$PORT` (defaults to `8000`).

---

## Option A — Docker (judge-side or local)

```bash
# from the repo root
docker build -t queuestorm-investigator .
docker run -d -p 8000:8000 --name qsi queuestorm-investigator

# verify
curl http://localhost:8000/health
# -> {"status":"ok"}

curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"TKT-001","complaint":"I sent 5000 taka to a wrong number around 2pm today.","transaction_history":[{"transaction_id":"TXN-9101","timestamp":"2026-04-14T14:08:22Z","type":"transfer","amount":5000,"counterparty":"+8801719876543","status":"completed"}]}'
```

Stop/remove: `docker rm -f qsi`

### Docker Compose
```bash
docker compose up --build      # http://localhost:8000/health
```

### Pull the prebuilt image (published on Docker Hub)
```bash
docker pull rifathosain/queuestorm-investigator:latest
docker run -d -p 8000:8000 rifathosain/queuestorm-investigator:latest
# verify:
curl http://localhost:8000/health        # -> {"status":"ok"}
```

---

## Option B — Local Python (no Docker)

```bash
python -m venv .venv
. .venv/Scripts/activate          # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
> Note: requires Python 3.12 (the pinned deps ship 3.12 wheels). On Python 3.13/3.14
> use latest deps: `pip install -U fastapi "pydantic>=2.12" "uvicorn[standard]"`.

---

## Option C — Deploy to a public host (Live URL)

**Render / Railway / Fly.io** — all detect the `Dockerfile` and inject `$PORT`:

- **Render:** New → Web Service → connect repo → Runtime: Docker → Create. Health
  check path: `/health`.
- **Railway:** New Project → Deploy from repo → it builds the Dockerfile. Expose the
  service to get a public URL.
- **Fly.io:** `fly launch` (uses the Dockerfile) → `fly deploy`.

After deploy, confirm: `curl https://<your-url>/health` → `{"status":"ok"}`.

---

## Option D — GitHub Actions CI/CD to DockerHub + Poridhi VM

The workflow in `.github/workflows/ci-cd.yml` runs on every push to `main` and on
manual dispatch:

1. Install dependencies and run `pytest`.
2. Build the Docker image.
3. Push `rifathosain/queuestorm-investigator:latest` and a `sha-xxxxxxx` tag to
   DockerHub.
4. SSH into the Poridhi VM, copy `scripts/deploy_vm.sh`, and restart the container
   on port `8011`.

### Required GitHub Secrets

Set these in GitHub: Repository → Settings → Secrets and variables → Actions.

| Secret | Required? | Value |
|---|---:|---|
| `DOCKERHUB_USERNAME` | Yes | DockerHub username — `rifathosain` |
| `DOCKERHUB_TOKEN` | Yes | DockerHub access token or password |
| `VM_HOST` | For VM deploy | SSH-reachable host/IP of the Poridhi VM |
| `VM_USER` | For VM deploy | SSH username on the VM |
| `VM_SSH_PRIVATE_KEY` | For VM deploy | Private key that can SSH into the VM |
| `VM_SSH_PORT` | Optional | SSH port, defaults to `22` |
| `VM_APP_PORT` | Optional | Host-side app port, defaults to `8011` |

**Gemini API key and LLM settings are NOT GitHub Secrets.** They are configured
directly on the Poridhi VM (see below). This keeps the key out of CI logs and
GitHub entirely.

### Gemini config on the Poridhi VM

The deploy script (`scripts/deploy_vm.sh`) starts the container with
`--env-file ~/queuestorm-investigator/runtime.env`. Edit that file on the VM to
control Gemini:

```bash
# on the Poridhi VM
nano ~/queuestorm-investigator/runtime.env
```

Example `runtime.env` with Gemini enabled:
```
PORT=8000
USE_LLM=true
GEMINI_API_KEY=<your-key>
MODEL_NAME=gemini-3.5-flash
LLM_FALLBACK_MODELS=gemini-2.0-flash-lite,gemini-1.5-flash-8b
LLM_TIMEOUT_SECONDS=4.0
LLM_MAX_TOKENS=600
```

The file persists across deploys — `deploy_vm.sh` never overwrites it if it already
exists. After editing, restart the container to pick up the new values:

```bash
docker rm -f qsi
~/queuestorm-investigator/deploy_vm.sh \
  rifathosain/queuestorm-investigator:latest qsi 8011
```

### Poridhi load-balancer note

The Poridhi load-balancer URL is for HTTP traffic to your app, not for SSH. If the
VM host is a private `100.x.x.x` address, GitHub-hosted runners usually cannot
reach it directly — use the Poridhi-provided public SSH endpoint, or install a
GitHub self-hosted runner inside the Poridhi lab/VM network.

After a successful deploy, verify:

```bash
curl http://6a3d596590003c8f7c598a2c_01495565.lb.poridhi.io/health
```

---

## Validate a running instance

```bash
pip install -r requirements-dev.txt
python scripts/smoke_test.py http://localhost:8000      # or your live URL
```
Checks `/health`, schema + enums, the evidence-reasoning fields against the public
expected outputs, the safety rules, malformed-input handling, and reports p95 latency.

---

## Optional: enable Gemini text polish (off by default)

The service uses a **three-model fallback chain** so a quota limit on one model
never takes down the LLM path:

```
gemini-3.5-flash  →  gemini-2.0-flash-lite  →  gemini-1.5-flash-8b  →  deterministic text
```

All three models share one 4-second deadline. Quota errors (HTTP 429) come back in
milliseconds, so switching models adds negligible latency. A timeout always stops
the chain immediately — total wall-clock time is always bounded.

### Run locally with Gemini enabled
```bash
docker run -d -p 8000:8000 \
  -e USE_LLM=true \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e MODEL_NAME=gemini-3.5-flash \
  -e LLM_FALLBACK_MODELS=gemini-2.0-flash-lite,gemini-1.5-flash-8b \
  queuestorm-investigator
```

Decisions and the safety filter are unchanged; only the wording of the three
free-text fields may be rephrased. The deterministic safety filter always re-runs
on the LLM output before it leaves the service.

### Override the fallback chain

To disable fallbacks entirely (use only the primary model):
```bash
-e LLM_FALLBACK_MODELS=""
```

To add or reorder models:
```bash
-e LLM_FALLBACK_MODELS=gemini-2.5-flash-lite,gemini-1.5-flash-8b
```

---

## Troubleshooting

- **Port already in use:** map a different host port, e.g. `-p 8080:8000`.
- **Health not ready:** the app starts in well under 60 s; check `docker logs qsi`.
- **Auth errors with USE_LLM=true:** the `GEMINI_API_KEY` is missing or invalid —
  unset `USE_LLM` to run the default rule-based service with no key required.
- **All models returning 429:** free-tier quota exhausted for the day — unset
  `USE_LLM` and the service continues rule-based with no degradation to scored fields.
