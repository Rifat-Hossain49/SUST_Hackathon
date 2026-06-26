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

### Pull a prebuilt image (if published)
```bash
docker pull <DOCKERHUB_USER>/queuestorm-investigator:latest
docker run -d -p 8000:8000 <DOCKERHUB_USER>/queuestorm-investigator:latest
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

## Validate a running instance

```bash
pip install -r requirements-dev.txt
python scripts/smoke_test.py http://localhost:8000      # or your live URL
```
Checks `/health`, schema + enums, the evidence-reasoning fields against the public
expected outputs, the safety rules, malformed-input handling, and reports p95 latency.

## Optional: enable LLM text polish (off by default)
```bash
docker run -d -p 8000:8000 \
  -e USE_LLM=true -e ANTHROPIC_API_KEY=sk-ant-... \
  -e MODEL_NAME=claude-haiku-4-5 \
  queuestorm-investigator
```
Decisions and the safety filter are unchanged; only the wording of the text fields
may be rephrased, and a 4 s timeout falls back to the deterministic text.

## Troubleshooting
- **Port already in use:** map a different host port, e.g. `-p 8080:8000`.
- **Health not ready:** the app starts in well under 60 s; check `docker logs qsi`.
- **No secrets required:** if you see auth errors, you set `USE_LLM=true` without a
  valid key — unset `USE_LLM` to run the default rule-based service.
