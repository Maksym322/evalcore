"""CI artifact provenance tests (EC-001-PROVENANCE-FIX).

Validates machine-readable provenance manifest generation and verification:
1. Synthetic PR merge/head/base identities: visibly distinguishes merge-ref checkout
   from source branch head SHA.
2. Main push workflow event: records tested_sha without fabricating PR metadata.
3. Missing metadata: missing data remains missing (None), cannot become passing evidence.
4. Malformed metadata: rejects non-SHA and invalid structure.
5. Deliberately mismatched tested-head assertion: rejects mismatched commit identity.
6. Real CLI execution: executes scripts/ci_provenance.py and checks exit codes/manifests.
7. Live git rev-parse HEAD resolution matches repository state.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure scripts directory is on sys.path to import the exact workflow helper
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ci_provenance import (  # noqa: E402
    ProvenanceError,
    generate_provenance,
    get_tested_sha,
    verify_provenance,
    write_provenance,
)

MERGE_SHA = "1111111111111111111111111111111111111111"
PR_HEAD_SHA = "2222222222222222222222222222222222222222"
PR_BASE_SHA = "3333333333333333333333333333333333333333"
OTHER_SHA = "4444444444444444444444444444444444444444"


def test_ci_provenance_synthetic_pr_merge_identity(tmp_path: Path) -> None:
    """Verify synthetic PR merge ref checkout records merge SHA and keeps branch head distinct."""
    manifest_path = write_provenance(
        out_dir=tmp_path,
        component="evalcore",
        tested_sha=MERGE_SHA,
        repository="owner/evalcore-repo",
        event_name="pull_request",
        ref="refs/pull/42/merge",
        workflow="Offline CI",
        run_id="998877",
        run_attempt="1",
        python_version="3.12.1",
        pr_head_sha=PR_HEAD_SHA,
        pr_base_sha=PR_BASE_SHA,
        pr_number=42,
    )

    assert manifest_path.is_file()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Core identities
    assert data["component"] == "evalcore"
    assert data["tested_sha"] == MERGE_SHA
    assert data["pr_head_sha"] == PR_HEAD_SHA
    assert data["pr_base_sha"] == PR_BASE_SHA
    assert data["pr_number"] == 42
    assert data["is_pr_merge_ref"] is True

    # PR merge-ref checkout must remain visibly distinct from source branch head
    assert data["tested_sha"] != data["pr_head_sha"]

    # Validating against the actual tested merge commit succeeds
    verified = verify_provenance(
        manifest_path,
        expected_tested_sha=MERGE_SHA,
        expected_pr_head_sha=PR_HEAD_SHA,
        expected_component="evalcore",
    )
    assert verified["tested_sha"] == MERGE_SHA

    # Attempting to verify the merge commit as branch head must fail
    with pytest.raises(ProvenanceError, match="cannot verify merge commit as branch head"):
        verify_provenance(
            manifest_path,
            expected_tested_sha=PR_HEAD_SHA,
            expected_pr_head_sha=PR_HEAD_SHA,
        )


def test_ci_provenance_main_push(tmp_path: Path) -> None:
    """Verify main push event records tested commit without fabricating PR metadata."""
    manifest_path = write_provenance(
        out_dir=tmp_path,
        component="ticketpilot",
        tested_sha=MERGE_SHA,
        repository="owner/evalcore-repo",
        event_name="push",
        ref="refs/heads/main",
        workflow="Offline CI",
        run_id="112233",
        run_attempt="1",
    )

    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert data["component"] == "ticketpilot"
    assert data["tested_sha"] == MERGE_SHA
    assert data["event_name"] == "push"
    assert data["ref"] == "refs/heads/main"
    assert data["is_pr_merge_ref"] is False

    # Missing PR data must remain None, not fabricated
    assert data["pr_head_sha"] is None
    assert data["pr_base_sha"] is None
    assert data["pr_number"] is None

    verified = verify_provenance(
        manifest_path,
        expected_tested_sha=MERGE_SHA,
        expected_component="ticketpilot",
    )
    assert verified["tested_sha"] == MERGE_SHA


def test_ci_provenance_missing_metadata(tmp_path: Path) -> None:
    """Verify missing metadata remains missing (None) and cannot become passing evidence."""
    # When tested_sha cannot be resolved (e.g. outside git repo without override)
    manifest = generate_provenance(
        component="evalcore",
        tested_sha=None,
        repo_root=tmp_path,  # Empty folder with no git
    )

    # Missing data must remain missing, not fabricated
    assert manifest["tested_sha"] is None
    assert manifest["repository"] is None

    # Cannot verify as passing current-head evidence when tested_sha is missing
    with pytest.raises(ProvenanceError, match="Missing tested_sha"):
        verify_provenance(manifest)


def test_ci_provenance_malformed_metadata() -> None:
    """Verify malformed metadata (invalid SHA or schema) is rejected."""
    # Not a 40-hex SHA
    malformed_sha = {
        "schema_version": 1,
        "component": "evalcore",
        "tested_sha": "not-a-valid-sha-string",
        "python_version": "3.12.1",
    }
    with pytest.raises(ProvenanceError, match="Malformed tested_sha"):
        verify_provenance(malformed_sha)

    # Too short SHA
    short_sha = {
        "schema_version": 1,
        "component": "evalcore",
        "tested_sha": "1234abcd",
        "python_version": "3.12.1",
    }
    with pytest.raises(ProvenanceError, match="Malformed tested_sha"):
        verify_provenance(short_sha)

    # Malformed PR head SHA
    malformed_pr_head = {
        "schema_version": 1,
        "component": "evalcore",
        "tested_sha": MERGE_SHA,
        "python_version": "3.12.1",
        "pr_head_sha": "short-head",
    }
    with pytest.raises(ProvenanceError, match="Malformed pr_head_sha"):
        verify_provenance(malformed_pr_head)

    # Invalid schema version
    invalid_schema = {
        "schema_version": 0,
        "component": "evalcore",
        "tested_sha": MERGE_SHA,
        "python_version": "3.12.1",
    }
    with pytest.raises(ProvenanceError, match="Invalid schema_version"):
        verify_provenance(invalid_schema)


def test_ci_provenance_deliberate_mismatched_tested_head_assertion() -> None:
    """Verify deliberate mismatch between manifest tested_sha and expected SHA fails."""
    manifest = {
        "schema_version": 1,
        "component": "evalcore",
        "tested_sha": MERGE_SHA,
        "python_version": "3.12.1",
        "is_pr_merge_ref": False,
    }

    # Deliberate mismatch: asserting OTHER_SHA when manifest recorded MERGE_SHA
    with pytest.raises(ProvenanceError, match="Tested SHA mismatch"):
        verify_provenance(manifest, expected_tested_sha=OTHER_SHA)


def test_ci_provenance_cli_execution(tmp_path: Path) -> None:
    """Verify scripts/ci_provenance.py CLI invocation generates and verifies manifests."""
    script_path = SCRIPTS_DIR / "ci_provenance.py"
    out_dir = tmp_path / "reports" / "evalcore"

    # Run generation via CLI
    gen_cmd = [
        sys.executable,
        str(script_path),
        "--component",
        "evalcore",
        "--out-dir",
        str(out_dir),
        "--tested-sha",
        MERGE_SHA,
        "--repository",
        "owner/test-repo",
        "--event-name",
        "pull_request",
        "--ref",
        "refs/pull/99/merge",
        "--workflow",
        "Offline CI",
        "--run-id",
        "556677",
        "--run-attempt",
        "2",
        "--pr-head-sha",
        PR_HEAD_SHA,
        "--pr-base-sha",
        PR_BASE_SHA,
        "--pr-number",
        "99",
    ]
    result = subprocess.run(gen_cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"CLI generate failed: {result.stderr}"

    manifest_file = out_dir / "provenance.json"
    assert manifest_file.is_file()

    # Run verification via CLI (matching SHA)
    verify_cmd_pass = [
        sys.executable,
        str(script_path),
        "--verify",
        str(manifest_file),
        "--expected-tested-sha",
        MERGE_SHA,
        "--component",
        "evalcore",
    ]
    res_pass = subprocess.run(verify_cmd_pass, capture_output=True, text=True, check=False)
    assert res_pass.returncode == 0

    # Run verification via CLI (mismatched SHA) -> exits 1
    verify_cmd_fail = [
        sys.executable,
        str(script_path),
        "--verify",
        str(manifest_file),
        "--expected-tested-sha",
        OTHER_SHA,
    ]
    res_fail = subprocess.run(verify_cmd_fail, capture_output=True, text=True, check=False)
    assert res_fail.returncode == 1
    assert "Tested SHA mismatch" in res_fail.stderr


def test_ci_provenance_live_git_rev_parse() -> None:
    """Verify get_tested_sha() against the active git worktree matches git rev-parse HEAD."""
    tested_sha = get_tested_sha(ROOT)
    assert tested_sha is not None
    assert len(tested_sha) == 40

    # Cross-check directly with git
    direct_git = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT)).decode("utf-8").strip()
    )
    assert tested_sha.lower() == direct_git.lower()
