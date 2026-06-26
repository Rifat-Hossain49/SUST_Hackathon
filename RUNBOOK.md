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

## Option D - GitHub Actions CI/CD to DockerHub + VM

The workflow in `.github/workflows/ci-cd.yml` runs on pushes to `main` and manual
dispatch:

1. Install dependencies and run `pytest`.
2. Build the Docker image.
3. Push `rifathosain/queuestorm-investigator:latest` and a `sha-xxxxxxx` tag.
4. If SSH secrets are present, copy `scripts/deploy_vm.sh` to the VM and restart
   the container on port `8011`.

### Required GitHub Secrets

Set these in GitHub: Repository -> Settings -> Secrets and variables -> Actions.
Do not commit the actual values.

| Secret | Required? | Value |
|---|---:|---|
| `DOCKERHUB_USERNAME` | Yes | DockerHub username, e.g. `rifathosain` |
| `DOCKERHUB_TOKEN` | Yes | DockerHub access token or password |
| `VM_HOST` | For deploy | SSH-reachable VM host/IP |
| `VM_USER` | For deploy | SSH username on the VM |
| `VM_SSH_PRIVATE_KEY` | For deploy | Private key that can SSH into the VM |
| `VM_SSH_PORT` | Optional | SSH port, defaults to `22` |
| `VM_APP_PORT` | Optional | Host app port, defaults to `8011` |
| `USE_LLM` | Optional | `true` to enable Gemini, otherwise omit or set `false` |
| `GEMINI_API_KEY` | Optional | Gemini API key, only if `USE_LLM=true` |
| `MODEL_NAME` | Optional | Defaults to `gemini-3.5-flash` |
| `LLM_TIMEOUT_SECONDS` | Optional | Defaults to `4.0` |
| `LLM_MAX_TOKENS` | Optional | Defaults to `600` |

Important: the Poridhi load-balancer URL is for HTTP traffic to your app, not SSH.
If the VM host is a private `100.x.x.x` address, GitHub-hosted runners usually
cannot reach it directly. In that case either use a Poridhi/public SSH endpoint,
or install a GitHub self-hosted runner inside the Poridhi lab/VM network.

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

## Optional: enable Gemini text polish (off by default)
```bash
docker run -d -p 8000:8000 \
  -e USE_LLM=true \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e MODEL_NAME=gemini-3.5-flash \
  queuestorm-investigator
```
Decisions and the safety filter are unchanged; only the wording of the text fields
may be rephrased, and a 4 s timeout falls back to the deterministic text. Set the
real key only in your deploy environment or the private judging field.

## Troubleshooting
- **Port already in use:** map a different host port, e.g. `-p 8080:8000`.
- **Health not ready:** the app starts in well under 60 s; check `docker logs qsi`.
- **No secrets required:** if you see auth errors, you set `USE_LLM=true` without a
  valid `GEMINI_API_KEY` — unset `USE_LLM` to run the default rule-based service.
