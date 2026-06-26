"""Generate sample_output.json — the service's actual responses to the 10 public
sample inputs. Run from the repo root:  python scripts/gen_sample_output.py
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests" / "data" / "sample_cases.json").read_text("utf-8"))["cases"]

client = TestClient(app)
out = []
for c in CASES:
    resp = client.post(settings.MAIN_ENDPOINT, json=c["input"])
    out.append({
        "id": c["id"],
        "label": c["label"],
        "input": c["input"],
        "service_output": resp.json(),
        "expected_output_reference": c["expected_output"],
    })

(ROOT / "sample_output.json").write_text(
    json.dumps({"endpoint": settings.MAIN_ENDPOINT, "cases": out}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"Wrote sample_output.json with {len(out)} cases.")
