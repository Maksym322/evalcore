# Continuous Integration (CI) Documentation

## Overview

EvalCore and TicketPilot utilize bounded offline CI for pull requests and pushes to `main`. CI runs deterministic unit tests, formatting/style checks, strict type validation, and deterministic regression gates without external network calls, live databases, or paid LLM provider credentials.

## Workflow Configuration

The primary workflow is located at `.github/workflows/offline-ci.yml`.

- **Triggers**:
  - `pull_request` (evaluates PR merge ref against target branch `main`)
  - `push` to `main` branch
- **Security & Permissions**:
  - Top-level and job-level permissions explicitly set to `contents: read`
  - No `pull_request_target` trigger
  - Zero access to GitHub secrets, API keys, or provider credentials
- **Action Pinning**:
  All external actions are pinned to full 40-character commit SHAs:
  - `actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803`
  - `actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1`
  - `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f`
- **Job Boundaries & Diagnostic Artifacts**:
  - `timeout-minutes: 15` per job
  - Short-lived test/evaluation artifacts saved under `reports/` with `retention-days: 7`
  - Machine-readable provenance manifest (`provenance.json`) generated alongside component reports (`reports/<component>/`)
  - Provenance generation and artifact upload execute with `if: always()` so failed checks retain downloadable diagnostic evidence when safe

## Artifact Provenance & PR Merge-Ref Semantics

Every CI job emits an uploaded machine-readable provenance manifest (`provenance.json`) via `scripts/ci_provenance.py` recording:
- `tested_sha`: actual checked-out commit SHA obtained via `git rev-parse HEAD`
- `repository`: repository slug (`owner/repo`)
- `event_name`: workflow trigger event (`pull_request` or `push`)
- `ref`: git ref tested (e.g., `refs/pull/<pr>/merge` or `refs/heads/main`)
- `workflow`, `run_id`, `run_attempt`: run identity
- `component`, `python_version`: component name and runtime Python version
- Separate PR identity when present: `pr_head_sha`, `pr_base_sha`, `pr_number`, and `is_pr_merge_ref` flag

### PR Merge-Ref vs. Branch Head Distinction
When GitHub Actions triggers on a `pull_request` without an explicit checkout ref, it checks out `refs/pull/<pr>/merge`. This is a synthetic merge commit of the PR author's branch head into the base branch (`main`).
- The actual tested revision is this merge commit (`tested_sha`), NOT the PR author's source branch head alone (`pr_head_sha`).
- CI provenance manifests explicitly record `tested_sha` from `git rev-parse HEAD` and keep it visibly distinct from `pr_head_sha`.
- A downloaded report cannot misattribute merge-ref test results as source branch head evidence without checking the actual tested SHA.
- Missing data remains `None` (missing data is never fabricated).

## Supported & Tested Python Versions

- **Supported Versions**: Python `>=3.11` (Python 3.11, 3.12, 3.13, 3.14) as specified in `evalcore/pyproject.toml` and `ticketpilot/pyproject.toml`.
- **Tested Versions**:
  - **Python 3.12**: Verified locally in the offline dev environment (Python 3.12, pytest 9.1.1, Ruff 0.17.2, mypy 2.4.0).
  - **Python 3.14**: Verified in coordinator baseline environment.
  - **CI Runner**: Defaults to Python 3.12 on `ubuntu-latest`.

## Component Checks & Fixtures

From the component directories:

### EvalCore (`evalcore/`)
- **Unit Tests**:
  ```bash
  pytest -q -p no:cacheprovider
  ```
- **Linting & Formatting**:
  ```bash
  ruff check --no-cache .
  ruff format --check --no-cache .
  ```
- **Strict Typing**:
  ```bash
  mypy --no-incremental evalcore
  ```
- **Deterministic Gates & CLI**:
  ```bash
  pytest tests/test_gate.py tests/test_cli.py tests/test_ci_gate.py -q -p no:cacheprovider
  python -m evalcore.cli run --config examples/toy/evalcore.yaml --out-dir reports/evalcore
  ```
- **CI Gate Test Suite** (`evalcore/tests/test_ci_gate.py`):
  - `test_ci_gate_synthetic_pass_exit_0`: Genuine gate configuration with baseline match, exits 0.
  - `test_ci_gate_deliberate_regression_fail_exit_1`: Induced metric drop exceeding threshold, exits 1.
  - `test_ci_gate_toy_config_missing_gate_section_exit_2`: Unconfigured gate exits 2.
  - `test_ci_gate_missing_baseline_file_exit_2`: Missing baseline file exits 2.
  - `test_ci_gate_strict_config_hash_mismatch`: Config hash mismatch warns normally, fails under `--strict`.
  - `test_ci_toy_deterministic_eval_and_baseline_flow`: Full toy evaluation run writing real JSON reports.
- **CI Provenance Test Suite** (`evalcore/tests/test_ci_provenance.py`):
  - `test_ci_provenance_synthetic_pr_merge_identity`: Validates synthetic PR merge/head/base identities and visibly distinguishes merge SHA from source branch head.
  - `test_ci_provenance_main_push`: Validates main push event records tested commit without fabricating PR metadata.
  - `test_ci_provenance_missing_metadata`: Ensures missing metadata remains missing (None) and cannot become passing current-head evidence.
  - `test_ci_provenance_malformed_metadata`: Enforces rejection of invalid SHA formats and invalid schemas.
  - `test_ci_provenance_deliberate_mismatched_tested_head_assertion`: Asserts that mismatched commit identities fail verification.
  - `test_ci_provenance_cli_execution`: Executes `scripts/ci_provenance.py` via subprocess to generate and verify manifests.
  - `test_ci_provenance_live_git_rev_parse`: Verifies live worktree HEAD resolution against `git rev-parse HEAD`.

### TicketPilot (`ticketpilot/`)
- **Unit Tests**:
  ```bash
  pytest -q -p no:cacheprovider --junitxml=../reports/ticketpilot/junit.xml
  ```
- **Linting & Formatting**:
  ```bash
  ruff check --no-cache .
  ruff format --check --no-cache .
  ```
- **Strict Typing**:
  ```bash
  mypy --no-incremental app
  ```

## Provenance and Status

- **Historical Input**:
  - The final exact-head author report for task EC-001 is `275a611b-9048-4f03-a07f-3b677b6482dc` at commit `484cf0d7e67d865ade27ee97761e4debb3ca7317` (where all 8 offline checks passed).
  - Earlier run `9fcc8009-330f-4037-8863-b0084e6ca28f` was precommit evidence at head `6db6f46` with a different content fingerprint and is preserved as historical input.
- **Current Task (EC-001-PROVENANCE-FIX)**:
  - Adds `scripts/ci_provenance.py`, workflow provenance generation steps, failure-safe diagnostic upload, and the `evalcore/tests/test_ci_provenance.py` test suite.
  - New verification evidence for EC-001-PROVENANCE-FIX will be generated by the coordinator after commit.
- **Truthful Status & Limitations**:
  - Remote CI execution on GitHub, remote artifact downloads, and main-push execution remain pending coordinator review, branch push, PR creation, and account billing allowance checks.
  - Neither remote CI execution, remote artifacts, nor main-push runs have been verified; no remote runs were executed.
