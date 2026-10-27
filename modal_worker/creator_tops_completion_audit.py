from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = "nobleknights015-maker/Freeframe-mobile"
API = f"https://api.github.com/repos/{REPO}"
JOB_RE = re.compile(r"^produce \((\d+)\)$")


def _get_json(url: str) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _all_pages(url: str, key: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        sep = "&" if "?" in url else "?"
        data = _get_json(f"{url}{sep}per_page=100&page={page}")
        batch = list(data.get(key, []))
        out.extend(batch)
        if len(batch) < 100:
            return out
        page += 1


def _step_conclusion(job: dict, name: str) -> str | None:
    for step in job.get("steps") or []:
        if step.get("name") == name:
            return step.get("conclusion")
    return None


def audit(contract_path: Path, repo_root: Path) -> dict:
    c = json.loads(contract_path.read_text())
    assert c["schema"] == "plushbound.creator_tops_completion_contract.v1"
    run_id = int(c["bulk_run_id"])
    expected = [int(x) for x in c["expected_bulk_style_indices"]]
    assert len(expected) == int(c["expected_bulk_style_count"]) == 59
    assert len(expected) == len(set(expected))

    run = _get_json(f"{API}/actions/runs/{run_id}")
    jobs = _all_pages(f"{API}/actions/runs/{run_id}/jobs", "jobs")
    artifacts = _all_pages(f"{API}/actions/runs/{run_id}/artifacts", "artifacts")

    jobs_by_style: dict[int, list[dict]] = {i: [] for i in expected}
    unexpected_produce_jobs: list[str] = []
    for job in jobs:
        m = JOB_RE.match(str(job.get("name", "")))
        if not m:
            continue
        style = int(m.group(1))
        if style in jobs_by_style:
            jobs_by_style[style].append(job)
        else:
            unexpected_produce_jobs.append(str(job.get("name")))

    artifacts_by_style: dict[int, list[dict]] = {i: [] for i in expected}
    expected_names = {
        i: str(c["expected_artifact_name_template"]).format(style_index=i)
        for i in expected
    }
    name_to_style = {v: k for k, v in expected_names.items()}
    for artifact in artifacts:
        style = name_to_style.get(str(artifact.get("name", "")))
        if style is not None:
            artifacts_by_style[style].append(artifact)

    styles: dict[str, dict] = {}
    completed_success = 0
    active_or_queued = 0
    failed = 0
    contract_failures: list[str] = []

    for style in expected:
        js = jobs_by_style[style]
        ars = artifacts_by_style[style]
        entry = {
            "job_count": len(js),
            "artifact_count": len(ars),
            "status": None,
            "conclusion": None,
            "evidence_step": None,
            "artifact_step": None,
            "artifact_present": len(ars) == 1,
            "artifact_nonempty": len(ars) == 1 and int(ars[0].get("size_in_bytes", 0)) > 0,
            "artifact_unexpired": len(ars) == 1 and not bool(ars[0].get("expired", False)),
            "ready": False,
        }
        if len(js) != 1:
            contract_failures.append(f"style {style:03d}: expected exactly one job, found {len(js)}")
        else:
            job = js[0]
            entry["status"] = job.get("status")
            entry["conclusion"] = job.get("conclusion")
            entry["evidence_step"] = _step_conclusion(job, "Verify Creator Tops evidence")
            entry["artifact_step"] = _step_conclusion(job, "Upload Creator Tops evidence")
            if job.get("status") in ("queued", "in_progress", "waiting", "pending", "requested"):
                active_or_queued += 1
            elif job.get("conclusion") == "success":
                completed_success += 1
            else:
                failed += 1

        entry["ready"] = bool(
            len(js) == 1
            and entry["status"] == "completed"
            and entry["conclusion"] == "success"
            and entry["evidence_step"] == "success"
            and entry["artifact_step"] == "success"
            and len(ars) == 1
            and entry["artifact_nonempty"]
            and entry["artifact_unexpired"]
        )
        if entry["status"] == "completed" and not entry["ready"]:
            contract_failures.append(f"style {style:03d}: completed but does not satisfy evidence/artifact contract")
        styles[f"{style:03d}"] = entry

    unresolved_exceptions: list[dict] = []
    for rel in c.get("unresolved_exception_files", []):
        p = repo_root / rel
        if not p.exists():
            contract_failures.append(f"missing exception file: {rel}")
            continue
        e = json.loads(p.read_text())
        if e.get("blocks_tops_completion_contract") is True:
            unresolved_exceptions.append({
                "path": rel,
                "style_index": e.get("style_index"),
                "status": e.get("status"),
                "paid_state": e.get("paid_state"),
                "automatic_retry_allowed": e.get("automatic_retry_allowed"),
            })

    ready_count = sum(1 for x in styles.values() if x["ready"])
    ready_for_handoff = bool(
        run.get("status") == "completed"
        and ready_count == len(expected)
        and not unresolved_exceptions
        and not unexpected_produce_jobs
        and not contract_failures
    )

    return {
        "schema": "plushbound.creator_tops_completion_audit.v1",
        "bulk_run_id": run_id,
        "bulk_run_status": run.get("status"),
        "bulk_run_conclusion": run.get("conclusion"),
        "expected_style_count": len(expected),
        "ready_style_count": ready_count,
        "completed_success_job_count": completed_success,
        "active_or_queued_job_count": active_or_queued,
        "failed_job_count": failed,
        "unresolved_exceptions": unresolved_exceptions,
        "unexpected_produce_jobs": unexpected_produce_jobs,
        "contract_failures": sorted(set(contract_failures)),
        "ready_for_handoff": ready_for_handoff,
        "styles": styles,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", default="modal_worker/creator_tops_completion_contract.json")
    ap.add_argument("--output", default="creator-tops-completion-audit.json")
    args = ap.parse_args()
    root = Path.cwd()
    result = audit(root / args.contract, root)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in (
        "bulk_run_id", "bulk_run_status", "bulk_run_conclusion", "expected_style_count",
        "ready_style_count", "active_or_queued_job_count", "failed_job_count",
        "unresolved_exceptions", "ready_for_handoff"
    )}, indent=2))
    if result["ready_for_handoff"]:
        print("Creator Tops completion contract PASSED: handoff may be considered.")
    else:
        print("Creator Tops completion contract NOT YET PASSED: handoff remains closed.")


if __name__ == "__main__":
    main()
