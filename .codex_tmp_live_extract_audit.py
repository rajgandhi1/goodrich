import sys
import time
from collections import Counter
from pathlib import Path

import requests

API = "http://127.0.0.1:8000/api/v1"
USER = "shashnam@flosil.com"

paths = [Path(arg) for arg in sys.argv[1:]]


def headers(org: str) -> dict[str, str]:
    return {"X-Org-Id": org, "X-User-Id": USER}


def create_quote(org: str, file_path: Path) -> str:
    payload = {
        "customer": file_path.stem[:80],
        "project_ref": "Codex extraction audit",
        "items": [],
        "quote_data": {},
        "stage_meta": {"enquiry_stage": "draft"},
    }
    response = requests.post(f"{API}/quotes", headers=headers(org), json=payload, timeout=20)
    response.raise_for_status()
    return response.json()["id"]


def upload(org: str, quote_id: str, file_path: Path) -> str:
    with file_path.open("rb") as handle:
        response = requests.post(
            f"{API}/extractions",
            headers=headers(org),
            data={
                "source_type": "excel",
                "quote_id": quote_id,
                "customer": file_path.stem[:80],
                "project_ref": "Codex extraction audit",
            },
            files={"file": (file_path.name, handle, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=30,
        )
    response.raise_for_status()
    return response.json()["job_id"]


def wait_job(org: str, job_id: str, timeout_s: int = 600) -> dict:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        response = requests.get(f"{API}/jobs/{job_id}/status", headers=headers(org), timeout=20)
        response.raise_for_status()
        job = response.json()
        snapshot = (job["status"], job.get("message"), job.get("progress"))
        if snapshot != last:
            print("  job", job_id, snapshot, flush=True)
            last = snapshot
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(3)
    raise TimeoutError(f"job {job_id} did not finish in {timeout_s}s")


def get_quote(org: str, quote_id: str) -> dict:
    response = requests.get(f"{API}/quotes/{quote_id}", headers=headers(org), timeout=30)
    response.raise_for_status()
    return response.json()


for index, file_path in enumerate(paths, 1):
    org = f"codex-audit-{int(time.time())}-{index}"
    print(f"\n### {file_path.name}", flush=True)
    print(f"  org {org}", flush=True)
    try:
        quote_id = create_quote(org, file_path)
        job_id = upload(org, quote_id, file_path)
        job = wait_job(org, job_id)
        print("  final_job", job, flush=True)
        quote = get_quote(org, quote_id)
        statuses = Counter(item.get("status") for item in quote.get("items", []))
        print(
            "  quote",
            {
                "id": quote_id,
                "n_items": quote.get("n_items"),
                "n_ready": quote.get("n_ready"),
                "n_check": quote.get("n_check"),
                "n_missing": quote.get("n_missing"),
                "n_regret": quote.get("n_regret"),
                "statuses": dict(statuses),
            },
            flush=True,
        )
        for row_index, item in enumerate(quote.get("items", [])[:3], 1):
            print(
                "  sample",
                row_index,
                {
                    "line_no": item.get("line_no"),
                    "size": item.get("size"),
                    "rating": item.get("rating"),
                    "moc": item.get("moc"),
                    "gasket_type": item.get("gasket_type"),
                    "status": item.get("status"),
                    "flags": item.get("flags"),
                    "applied_defaults": item.get("applied_defaults"),
                },
                flush=True,
            )
        for row_index, item in list(enumerate(quote.get("items", []), 1))[-3:]:
            print(
                "  tail",
                row_index,
                {
                    "line_no": item.get("line_no"),
                    "size": item.get("size"),
                    "rating": item.get("rating"),
                    "moc": item.get("moc"),
                    "gasket_type": item.get("gasket_type"),
                    "status": item.get("status"),
                    "flags": item.get("flags"),
                    "applied_defaults": item.get("applied_defaults"),
                },
                flush=True,
            )
    except Exception as exc:
        print("  ERROR", repr(exc), flush=True)
