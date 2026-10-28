from __future__ import annotations

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
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
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


def _step(job: dict, name: str) -> str | None:
    for step in job.get("steps") or []:
        if step.get("name") == name:
            return step.get("conclusion")
    return None


def audit(contract_path: Path, repo_root: Path) -> dict:
    c = json.loads(contract_path.read_text())
    assert c["schema"] == "plushbound.creator_full_outfits_bulk_completion_contract.v1"
    expected = [int(x) for x in c["expected_style_indices"]]
    assert len(expected) == int(c["expected_style_count"]) == 45
    assert len(expected) == len(set(expected))
    assert not ({1, 49, 95} & set(expected))
    assert int(c["expected_paid_renders_per_style"]) == 5
    assert int(c["expected_paid_extractions_per_style"]) == 0
    assert c["allow_duplicate_style_artifacts"] is False
    assert c["require_exact_triggering_sha"] is True
    assert c["require_canary_ready_for_bulk"] is True

    canary_path = repo_root / c["canary_contract"]
    canary = json.loads(canary_path.read_text())
    canary_ok = bool(
        canary.get("schema") == "plushbound.creator_full_outfits_canary_completion_contract.v1"
        and canary.get("locked_body_visual_qc_passed") is True
        and canary.get("canary_verified") is True
        and canary.get("ready_for_bulk") is True
        and canary.get("bulk_authorized") is True
    )

    run_id = int(c["production_run_id"])
    expected_sha = str(c["production_head_sha"])
    run = _get_json(f"{API}/actions/runs/{run_id}")
    jobs = _all_pages(f"{API}/actions/runs/{run_id}/jobs", "jobs")
    artifacts = _all_pages(f"{API}/actions/runs/{run_id}/artifacts", "artifacts")

    failures: list[str] = []
    if str(run.get("head_sha")) != expected_sha:
        failures.append(f"run head SHA mismatch: expected {expected_sha}, got {run.get('head_sha')}")
    if not canary_ok:
        failures.append("canary contract is not verified/authorized for bulk")

    jobs_by_style: dict[int, list[dict]] = {i: [] for i in expected}
    unexpected_jobs: list[str] = []
    for job in jobs:
        m = JOB_RE.match(str(job.get("name", "")))
        if not m:
            continue
        style = int(m.group(1))
        if style in jobs_by_style:
            jobs_by_style[style].append(job)
        else:
            unexpected_jobs.append(str(job.get("name")))

    expected_names = {
        i: str(c["expected_artifact_name_template"]).format(style_index=i, production_run_id=run_id)
        for i in expected
    }
    name_to_style = {name: style for style, name in expected_names.items()}
    artifacts_by_style: dict[int, list[dict]] = {i: [] for i in expected}
    for artifact in artifacts:
        style = name_to_style.get(str(artifact.get("name", "")))
        if style is not None:
            artifacts_by_style[style].append(artifact)

    styles: dict[str, dict] = {}
    active = 0
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
            "artifact_nonempty": len(ars) == 1 and int(ars[0].get("size_in_bytes", 0)) > 0,
            "artifact_unexpired": len(ars) == 1 and not bool(ars[0].get("expired", False)),
            "ready": False,
        }
        if len(js) == 1:
            job = js[0]
            entry["status"] = job.get("status")
            entry["conclusion"] = job.get("conclusion")
            entry["evidence_step"] = _step(job, "Verify Creator Full Outfits evidence")
            entry["artifact_step"] = _step(job, "Upload Creator Full Outfits evidence")
            if job.get("status") in ("queued", "in_progress", "waiting", "pending", "requested"):
                active += 1
            elif job.get("conclusion") != "success":
                failed += 1
        elif len(js) > 1:
            failures.append(f"style {style:03d}: duplicate jobs ({len(js)})")

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
            failures.append(f"style {style:03d}: completed but evidence/artifact contract failed")
        styles[f"{style:03d}"] = entry

    unresolved: list[dict] = []
    for rel in c.get("unresolved_exception_files", []):
        p = repo_root / rel
        if not p.exists():
            failures.append(f"missing exception file: {rel}")
            continue
        e = json.loads(p.read_text())
        if e.get("blocks_full_outfits_bulk_contract") is True:
            unresolved.append({
                "path": rel,
                "style_index": e.get("style_index"),
                "status": e.get("status"),
                "paid_state": e.get("paid_state"),
                "automatic_retry_allowed": e.get("automatic_retry_allowed"),
            })

    ready_count = sum(1 for x in styles.values() if x["ready"])
    ready_for_handoff = bool(
        run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and ready_count == len(expected)
        and active == 0
        and failed == 0
        and not unresolved
        and not unexpected_jobs
        and not failures
        and canary_ok
    )

    return {
        "schema": "plushbound.creator_full_outfits_bulk_completion_audit.v1",
        "production_run_id": run_id,
        "production_head_sha": run.get("head_sha"),
        "run_status": run.get("status"),
        "run_conclusion": run.get("conclusion"),
        "expected_style_count": len(expected),
        "ready_style_count": ready_count,
        "active_or_queued_job_count": active,
        "failed_job_count": failed,
        "canary_ready_for_bulk": canary_ok,
        "unresolved_exceptions": unresolved,
        "unexpected_produce_jobs": unexpected_jobs,
        "contract_failures": sorted(set(failures)),
        "ready_for_handoff": ready_for_handoff,
        "styles": styles,
    }


def main() -> None:
    root = Path.cwd()
    result = audit(root / "modal_worker/creator_full_outfits_bulk_completion_contract.json", root)
    Path("creator-full-outfits-bulk-completion-audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({k: result[k] for k in (
        "production_run_id", "run_status", "run_conclusion", "expected_style_count",
        "ready_style_count", "active_or_queued_job_count", "failed_job_count",
        "canary_ready_for_bulk", "unresolved_exceptions", "ready_for_handoff"
    )}, indent=2))


if __name__ == "__main__":
    main()
