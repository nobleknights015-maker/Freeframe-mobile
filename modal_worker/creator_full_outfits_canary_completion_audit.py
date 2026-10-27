from __future__ import annotations

import argparse
import json
import os
import re
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


def _not_launched(c: dict) -> dict:
    expected = [int(x) for x in c["expected_style_indices"]]
    return {
        "schema": "plushbound.creator_full_outfits_canary_completion_audit.v1",
        "production_run_id": None,
        "production_head_sha": None,
        "run_status": "not_launched",
        "run_conclusion": None,
        "expected_style_count": len(expected),
        "ready_style_count": 0,
        "active_or_queued_job_count": 0,
        "failed_job_count": 0,
        "unresolved_exceptions": [],
        "unexpected_produce_jobs": [],
        "contract_failures": ["Full Outfits canary production_run_id is not populated"],
        "locked_body_visual_qc_passed": False,
        "canary_verified": False,
        "ready_for_bulk": False,
        "styles": {f"{i:03d}": {"ready": False, "status": "not_launched"} for i in expected},
    }


def audit(contract_path: Path, repo_root: Path) -> dict:
    c = json.loads(contract_path.read_text())
    assert c["schema"] == "plushbound.creator_full_outfits_canary_completion_contract.v1"
    expected = [int(x) for x in c["expected_style_indices"]]
    assert expected == [1, 49, 95]
    assert len(expected) == int(c["expected_style_count"]) == 3
    assert len(expected) == len(set(expected))
    assert int(c["expected_paid_renders_per_style"]) == 5
    assert int(c["expected_paid_extractions_per_style"]) == 0
    assert c["allow_duplicate_style_artifacts"] is False
    assert c["require_exact_triggering_sha"] is True
    assert c["require_locked_body_visual_qc"] is True
    assert c["require_no_unresolved_exceptions"] is True
    assert isinstance(c.get("bulk_authorized"), bool)
    assert isinstance(c.get("locked_body_visual_qc_passed", False), bool)

    if c.get("production_run_id") is None:
        return _not_launched(c)

    run_id = int(c["production_run_id"])
    expected_sha = str(c.get("production_head_sha") or "")
    assert expected_sha, "production_head_sha must be populated with the launched canary run"

    run = _get_json(f"{API}/actions/runs/{run_id}")
    jobs = _all_pages(f"{API}/actions/runs/{run_id}/jobs", "jobs")
    artifacts = _all_pages(f"{API}/actions/runs/{run_id}/artifacts", "artifacts")

    contract_failures: list[str] = []
    if str(run.get("head_sha")) != expected_sha:
        contract_failures.append(f"run head SHA mismatch: expected {expected_sha}, got {run.get('head_sha')}")

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

    names = {
        i: str(c["expected_artifact_name_template"]).format(style_index=i, production_run_id=run_id)
        for i in expected
    }
    name_to_style = {v: k for k, v in names.items()}
    artifacts_by_style: dict[int, list[dict]] = {i: [] for i in expected}
    for artifact in artifacts:
        style = name_to_style.get(str(artifact.get("name", "")))
        if style is not None:
            artifacts_by_style[style].append(artifact)

    styles: dict[str, dict] = {}
    active_or_queued = 0
    failed = 0
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
            entry["evidence_step"] = _step_conclusion(job, "Verify Creator Full Outfits evidence")
            entry["artifact_step"] = _step_conclusion(job, "Upload Creator Full Outfits evidence")
            if job.get("status") in ("queued", "in_progress", "waiting", "pending", "requested"):
                active_or_queued += 1
            elif job.get("conclusion") != "success":
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
        if e.get("blocks_full_outfits_canary_contract") is True:
            unresolved_exceptions.append({
                "path": rel,
                "style_index": e.get("style_index"),
                "status": e.get("status"),
                "paid_state": e.get("paid_state"),
                "automatic_retry_allowed": e.get("automatic_retry_allowed"),
            })

    ready_count = sum(1 for x in styles.values() if x["ready"])
    visual_qc_passed = bool(c.get("locked_body_visual_qc_passed", False))
    canary_verified = bool(
        run.get("status") == "completed"
        and ready_count == len(expected)
        and not unresolved_exceptions
        and not unexpected_produce_jobs
        and not contract_failures
        and visual_qc_passed
    )
    ready_for_bulk = bool(canary_verified and c.get("bulk_authorized") is True)

    return {
        "schema": "plushbound.creator_full_outfits_canary_completion_audit.v1",
        "production_run_id": run_id,
        "production_head_sha": run.get("head_sha"),
        "run_status": run.get("status"),
        "run_conclusion": run.get("conclusion"),
        "expected_style_count": len(expected),
        "ready_style_count": ready_count,
        "active_or_queued_job_count": active_or_queued,
        "failed_job_count": failed,
        "unresolved_exceptions": unresolved_exceptions,
        "unexpected_produce_jobs": unexpected_produce_jobs,
        "contract_failures": sorted(set(contract_failures)),
        "locked_body_visual_qc_passed": visual_qc_passed,
        "canary_verified": canary_verified,
        "ready_for_bulk": ready_for_bulk,
        "styles": styles,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", default="modal_worker/creator_full_outfits_canary_completion_contract.json")
    ap.add_argument("--output", default="creator-full-outfits-canary-completion-audit.json")
    args = ap.parse_args()
    root = Path.cwd()
    result = audit(root / args.contract, root)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in (
        "production_run_id", "run_status", "run_conclusion", "expected_style_count",
        "ready_style_count", "active_or_queued_job_count", "failed_job_count",
        "unresolved_exceptions", "locked_body_visual_qc_passed", "canary_verified", "ready_for_bulk"
    )}, indent=2))
    if result["ready_for_bulk"]:
        print("Full Outfits canary completion contract PASSED for separately authorized bulk expansion.")
    elif result["canary_verified"]:
        print("Full Outfits canary is verified; bulk remains closed until separately authorized.")
    else:
        print("Full Outfits canary contract NOT PASSED: bulk remains closed.")


if __name__ == "__main__":
    main()
