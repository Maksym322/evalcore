"""CI artifact provenance manifest generator and verifier.

Binds offline CI reports/artifacts to the actual tested Git revision and PR identity.
Records git rev-parse HEAD as the actual tested_sha, repository, event/ref,
workflow/run/attempt identity, component/Python version, and separate PR head/base
SHA when present. Visibly distinguishes PR merge-ref checkouts from branch head.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SHA_REGEX = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
PR_MERGE_REF_REGEX = re.compile(r"^refs/pull/\d+/merge$", re.IGNORECASE)


class ProvenanceError(ValueError):
    """Raised when provenance metadata is missing, malformed, or mismatched."""


def get_tested_sha(repo_root: Path | str | None = None) -> str | None:
    """Resolve the checked-out commit SHA using `git rev-parse HEAD`.

    Returns the 40-character hex commit SHA, or None if git is unavailable
    or the revision cannot be resolved. Missing data remains None;
    it is never fabricated.
    """
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            if SHA_REGEX.match(sha):
                return sha
    except (subprocess.SubprocessError, OSError):
        pass
    return None


def resolve_pr_metadata(
    *,
    event_name: str | None = None,
    ref: str | None = None,
    pr_head_sha: str | None = None,
    pr_base_sha: str | None = None,
    pr_number: int | str | None = None,
    event_path: Path | str | None = None,
) -> tuple[str | None, str | None, int | None, bool]:
    """Resolve PR head SHA, base SHA, PR number, and merge-ref status.

    Returns (pr_head_sha, pr_base_sha, pr_number, is_pr_merge_ref).
    """
    resolved_head = pr_head_sha.strip() if pr_head_sha and pr_head_sha.strip() else None
    resolved_base = pr_base_sha.strip() if pr_base_sha and pr_base_sha.strip() else None
    resolved_num: int | None = None
    if pr_number is not None and str(pr_number).strip():
        try:
            resolved_num = int(str(pr_number).strip())
        except ValueError:
            pass

    # Fall back to GITHUB_EVENT_PATH if available and fields are missing
    path_to_event = event_path or os.environ.get("GITHUB_EVENT_PATH")
    if path_to_event and Path(path_to_event).is_file():
        try:
            with open(path_to_event, encoding="utf-8") as f:
                event_data = json.load(f)
            pr_data = event_data.get("pull_request")
            if isinstance(pr_data, dict):
                if not resolved_head:
                    head_data = pr_data.get("head")
                    if isinstance(head_data, dict) and head_data.get("sha"):
                        resolved_head = str(head_data["sha"]).strip()
                if not resolved_base:
                    base_data = pr_data.get("base")
                    if isinstance(base_data, dict) and base_data.get("sha"):
                        resolved_base = str(base_data["sha"]).strip()
                if resolved_num is None and pr_data.get("number") is not None:
                    resolved_num = int(pr_data["number"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

    # Determine whether the ref is a PR merge ref
    active_ref = ref or os.environ.get("GITHUB_REF") or ""
    is_pr_merge_ref = bool(
        PR_MERGE_REF_REGEX.match(active_ref)
        or (event_name == "pull_request" and active_ref.endswith("/merge"))
    )

    return resolved_head, resolved_base, resolved_num, is_pr_merge_ref


def generate_provenance(
    *,
    component: str,
    repo_root: Path | str | None = None,
    tested_sha: str | None = None,
    repository: str | None = None,
    event_name: str | None = None,
    ref: str | None = None,
    workflow: str | None = None,
    run_id: str | None = None,
    run_attempt: str | None = None,
    python_version: str | None = None,
    pr_head_sha: str | None = None,
    pr_base_sha: str | None = None,
    pr_number: int | str | None = None,
    event_path: Path | str | None = None,
) -> dict[str, Any]:
    """Generate the complete provenance manifest dictionary.

    Extracts actual tested_sha via `git rev-parse HEAD` unless an explicit
    `tested_sha` is provided. Keeps missing metadata as None (never fabricated).
    """
    actual_tested_sha = tested_sha or get_tested_sha(repo_root)

    resolved_repo = (
        repository.strip()
        if repository and repository.strip()
        else os.environ.get("GITHUB_REPOSITORY")
    )
    resolved_event = (
        event_name.strip()
        if event_name and event_name.strip()
        else os.environ.get("GITHUB_EVENT_NAME")
    )
    resolved_ref = ref.strip() if ref and ref.strip() else os.environ.get("GITHUB_REF")
    resolved_workflow = (
        workflow.strip()
        if workflow and workflow.strip()
        else os.environ.get("GITHUB_WORKFLOW")
    )
    resolved_run_id = (
        run_id.strip() if run_id and run_id.strip() else os.environ.get("GITHUB_RUN_ID")
    )
    resolved_run_attempt = (
        run_attempt.strip()
        if run_attempt and run_attempt.strip()
        else os.environ.get("GITHUB_RUN_ATTEMPT")
    )
    resolved_py_version = (
        python_version.strip()
        if python_version and python_version.strip()
        else platform.python_version()
    )

    head_sha, base_sha, num, is_merge = resolve_pr_metadata(
        event_name=resolved_event,
        ref=resolved_ref,
        pr_head_sha=pr_head_sha or os.environ.get("PR_HEAD_SHA"),
        pr_base_sha=pr_base_sha or os.environ.get("PR_BASE_SHA"),
        pr_number=pr_number or os.environ.get("PR_NUMBER"),
        event_path=event_path,
    )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "component": component,
        "tested_sha": actual_tested_sha,
        "repository": resolved_repo,
        "event_name": resolved_event,
        "ref": resolved_ref,
        "workflow": resolved_workflow,
        "run_id": resolved_run_id,
        "run_attempt": resolved_run_attempt,
        "python_version": resolved_py_version,
        "is_pr_merge_ref": is_merge,
        "pr_head_sha": head_sha,
        "pr_base_sha": base_sha,
        "pr_number": num,
    }

    return manifest


def write_provenance(
    out_dir: Path | str,
    *,
    component: str,
    filename: str = "provenance.json",
    **kwargs: Any,
) -> Path:
    """Generate and write the provenance manifest to `out_dir / filename`."""
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / filename

    manifest = generate_provenance(component=component, **kwargs)
    out_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return out_file


def verify_provenance(
    manifest_or_path: dict[str, Any] | Path | str,
    *,
    expected_tested_sha: str | None = None,
    expected_pr_head_sha: str | None = None,
    expected_component: str | None = None,
) -> dict[str, Any]:
    """Verify that a provenance manifest contains valid metadata.

    Ensures tested_sha is a valid 40-hex SHA, matches expected_tested_sha if
    provided, and distinguishes PR merge checkouts from PR source head.
    Raises ProvenanceError on missing, malformed, or mismatched metadata.
    """
    if isinstance(manifest_or_path, (str, Path)):
        p = Path(manifest_or_path)
        if not p.is_file():
            raise ProvenanceError(f"Provenance file not found: {p}")
        try:
            manifest = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            raise ProvenanceError(f"Malformed JSON in provenance file: {err}") from err
    else:
        manifest = manifest_or_path

    if not isinstance(manifest, dict):
        raise ProvenanceError("Provenance manifest must be a dictionary")

    # Validate schema version
    version = manifest.get("schema_version")
    if not isinstance(version, int) or version < 1:
        raise ProvenanceError(f"Invalid schema_version: {version}")

    # Validate component
    comp = manifest.get("component")
    if not comp or not isinstance(comp, str):
        raise ProvenanceError(f"Invalid or missing component: {comp}")
    if expected_component and comp != expected_component:
        raise ProvenanceError(
            f"Component mismatch: got {comp}, expected {expected_component}"
        )

    # Validate tested_sha
    tested_sha = manifest.get("tested_sha")
    if not tested_sha or not isinstance(tested_sha, str):
        raise ProvenanceError(f"Missing tested_sha in provenance: {tested_sha}")
    if not SHA_REGEX.match(tested_sha):
        raise ProvenanceError(
            f"Malformed tested_sha (expected 40-char hex): {tested_sha}"
        )

    # Validate Python version
    py_ver = manifest.get("python_version")
    if not py_ver or not isinstance(py_ver, str):
        raise ProvenanceError(f"Missing or invalid python_version: {py_ver}")

    # Validate PR fields if present
    pr_head = manifest.get("pr_head_sha")
    if pr_head is not None:
        if not isinstance(pr_head, str) or not SHA_REGEX.match(pr_head):
            raise ProvenanceError(f"Malformed pr_head_sha: {pr_head}")
        if expected_pr_head_sha and pr_head.lower() != expected_pr_head_sha.lower():
            raise ProvenanceError(
                f"PR head SHA mismatch: manifest has {pr_head}, expected {expected_pr_head_sha}"
            )

    pr_base = manifest.get("pr_base_sha")
    if pr_base is not None and (
        not isinstance(pr_base, str) or not SHA_REGEX.match(pr_base)
    ):
        raise ProvenanceError(f"Malformed pr_base_sha: {pr_base}")

    # Validate PR merge-ref semantics:
    # A PR merge ref tests the merge commit, which must not be falsely claimed
    # as the branch head.
    is_merge = manifest.get("is_pr_merge_ref")
    if (
        is_merge
        and pr_head is not None
        and expected_tested_sha
        and expected_tested_sha.lower() == pr_head.lower()
        and tested_sha.lower() != pr_head.lower()
    ):
        raise ProvenanceError(
            f"PR merge-ref checkout ({tested_sha}) is distinct from PR head ({pr_head}); "
            "cannot verify merge commit as branch head."
        )

    if expected_tested_sha and tested_sha.lower() != expected_tested_sha.lower():
        raise ProvenanceError(
            f"Tested SHA mismatch: manifest has {tested_sha}, expected {expected_tested_sha}"
        )

    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify machine-readable CI provenance manifests."
    )
    parser.add_argument(
        "--component",
        type=str,
        help="Component name (evalcore or ticketpilot)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Output directory for provenance.json (default: reports/<component>)",
    )
    parser.add_argument(
        "--filename",
        type=str,
        default="provenance.json",
        help="Manifest filename (default: provenance.json)",
    )
    parser.add_argument(
        "--tested-sha",
        type=str,
        default=None,
        help="Explicit tested commit SHA override",
    )
    parser.add_argument(
        "--repository",
        type=str,
        default=None,
        help="Repository identity override",
    )
    parser.add_argument(
        "--event-name",
        type=str,
        default=None,
        help="Workflow event name override",
    )
    parser.add_argument(
        "--ref",
        type=str,
        default=None,
        help="Git ref override",
    )
    parser.add_argument(
        "--workflow",
        type=str,
        default=None,
        help="Workflow name override",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Workflow run ID override",
    )
    parser.add_argument(
        "--run-attempt",
        type=str,
        default=None,
        help="Workflow run attempt override",
    )
    parser.add_argument(
        "--python-version",
        type=str,
        default=None,
        help="Python version override",
    )
    parser.add_argument(
        "--pr-head-sha",
        type=str,
        default=None,
        help="PR head commit SHA",
    )
    parser.add_argument(
        "--pr-base-sha",
        type=str,
        default=None,
        help="PR base commit SHA",
    )
    parser.add_argument(
        "--pr-number",
        type=str,
        default=None,
        help="PR number",
    )
    parser.add_argument(
        "--verify",
        type=str,
        default=None,
        help="Path to provenance manifest JSON to verify",
    )
    parser.add_argument(
        "--expected-tested-sha",
        type=str,
        default=None,
        help="Expected tested commit SHA for verification",
    )
    parser.add_argument(
        "--expected-pr-head-sha",
        type=str,
        default=None,
        help="Expected PR head commit SHA for verification",
    )

    args = parser.parse_args(argv)

    if args.verify:
        try:
            verify_provenance(
                args.verify,
                expected_tested_sha=args.expected_tested_sha,
                expected_pr_head_sha=args.expected_pr_head_sha,
                expected_component=args.component,
            )
            print(f"Provenance verification succeeded: {args.verify}")
            return 0
        except ProvenanceError as e:
            print(f"Provenance verification failed: {e}", file=sys.stderr)
            return 1

    if not args.component:
        parser.error("--component is required when generating a manifest")

    out_dir = args.out_dir or f"reports/{args.component}"
    out_path = write_provenance(
        out_dir=out_dir,
        component=args.component,
        filename=args.filename,
        tested_sha=args.tested_sha,
        repository=args.repository,
        event_name=args.event_name,
        ref=args.ref,
        workflow=args.workflow,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        python_version=args.python_version,
        pr_head_sha=args.pr_head_sha,
        pr_base_sha=args.pr_base_sha,
        pr_number=args.pr_number,
    )
    print(f"Wrote provenance manifest to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
