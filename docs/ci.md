# Continuous Integration (CI) Documentation

## Overview

EvalCore and TicketPilot utilize bounded offline CI for pull requests and pushes to `main`. CI runs deterministic unit tests, formatting/style checks, strict type validation, and deterministic regression gates without external network calls, live databases, or paid LLM provider credentials.

## Workflow Configuration

The primary workflow is located at `.github/workflows/offline-ci.yml`.

- **Triggers**:
  - `pull_request` (evaluates branch head against base)
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
- **Job Boundaries**:
  - `timeout-minutes: 15` per job
  - Short-lived test/evaluation artifacts saved under `reports/` with `retention-days: 7`

## Supported & Tested Python Versions

- **Supported Versions**: Python `>=3.11` (Python 3.11, 3.12, 3.13, 3.14) as specified in `evalcore/pyproject.toml` and `ticketpilot/pyproject.toml`.
- **Tested Versions**:
  - **Python 3.12**: Verified locally in the night environment (Python 3.12, pytest 9.1.1, Ruff 0.17.2, mypy 2.4.0).
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

### TicketPilot (`ticketpilot/`)
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
  mypy --no-incremental app
  ```

## Provenance and Status

- **Base Revision SHA**: `88e4402baa8046e0a0fbbccb2eaff0cf1fcbe7e8`
- **Fleet Verification Run ID**: `9fcc8009-330f-4037-8863-b0084e6ca28f`
- **Local Verification Status**: All 8 local checks passed (146 EvalCore tests, 34 TicketPilot tests, Ruff lint/format, strict Mypy, offline gates, and workflow structure).
- **Limitations**: Remote CI execution on GitHub and remote artifact downloads remain pending coordinator review, branch push, PR creation, and account billing allowance checks. No remote runs were executed overnight.
