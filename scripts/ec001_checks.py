"""Coordinator-owned offline checks; provider must not edit this runner."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(argv, cwd):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "evalcore"), str(ROOT / "ticketpilot")])
    for name in list(env):
        if any(part in name.upper() for part in ("API_KEY", "SECRET", "DATABASE_URL", "SUPABASE", "ACCESS_TOKEN")):
            env.pop(name)
    result = subprocess.run(argv, cwd=cwd, env=env, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def main():
    component, kind = sys.argv[1:]
    assert component in ("evalcore", "ticketpilot")
    cwd = ROOT / component
    if kind == "unit":
        run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd)
    elif kind == "lint":
        run([sys.executable, "-m", "ruff", "check", "--no-cache", "."], cwd)
        run([sys.executable, "-m", "ruff", "format", "--check", "--no-cache", "."], cwd)
    elif kind == "types":
        run([sys.executable, "-m", "mypy", "--no-incremental", "evalcore" if component == "evalcore" else "app"], cwd)
    elif kind == "gates":
        assert component == "evalcore"
        assert (cwd / "tests/test_ci_gate.py").is_file(), "New executed pass/fail CI gate tests are required"
        run([sys.executable, "-m", "pytest", "tests/test_gate.py", "tests/test_cli.py", "tests/test_ci_gate.py", "-q", "-p", "no:cacheprovider"], cwd)
        with tempfile.TemporaryDirectory(prefix="ec001-toy-") as folder:
            run([sys.executable, "-m", "evalcore.cli", "run", "--config", "examples/toy/evalcore.yaml", "--out-dir", folder], cwd)
            assert list(Path(folder).rglob("*.json")), "Toy run must produce a real JSON report"
    elif kind == "workflow":
        import yaml

        path = ROOT / ".github/workflows/offline-ci.yml"
        assert path.is_file(), "Expected bounded PR/main workflow"
        text = path.read_text(encoding="utf-8")
        data = yaml.load(text, Loader=yaml.BaseLoader)
        triggers = data["on"]
        assert "pull_request" in triggers and "push" in triggers
        assert "main" in triggers["push"]["branches"]
        assert "pull_request_target" not in triggers
        assert data.get("permissions", {}).get("contents") == "read"
        assert all(v in ("read", "none") for v in data["permissions"].values())
        assert "secrets." not in text and "secrets[" not in text
        artifacts = 0
        for job in data["jobs"].values():
            assert 0 < int(job.get("timeout-minutes", "0")) <= 20
            assert all(v in ("read", "none") for v in job.get("permissions", {}).values())
            for step in job["steps"]:
                if "uses" not in step:
                    continue
                assert re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}", step["uses"])
                if step["uses"].startswith("actions/upload-artifact@"):
                    artifacts += 1
                    assert 0 < int(step.get("with", {}).get("retention-days", "0")) <= 7
                    paths = step["with"].get("path", "").splitlines()
                    assert paths and all(p.strip().startswith("reports/") and ".." not in p for p in paths if p.strip())
        assert artifacts, "Bounded downloadable reports required"
        print("Workflow structure: PR/main triggers, bounded jobs/artifacts, read-only permissions and action SHA pins passed")
    else:
        raise SystemExit("Unknown check kind")


if __name__ == "__main__":
    main()
