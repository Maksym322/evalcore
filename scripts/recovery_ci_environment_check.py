import json,os,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="ci-env-repro-") as directory:
 for name,ref,payload in [("pull_request","refs/pull/7/merge",{"pull_request":{"number":7,"head":{"sha":"a"*40},"base":{"sha":"b"*40}}}),("push","refs/heads/main",{"ref":"refs/heads/main"})]:
  path=Path(directory)/(name+".json");path.write_text(json.dumps(payload),encoding="utf-8")
  env=dict(os.environ,GITHUB_REPOSITORY="synthetic/evalcore",GITHUB_EVENT_NAME=name,GITHUB_REF=ref,GITHUB_SHA="c"*40,GITHUB_WORKFLOW="Offline CI",GITHUB_RUN_ID="123",GITHUB_RUN_ATTEMPT="1",GITHUB_EVENT_PATH=str(path),PYTHONPATH=str(root/"evalcore"))
  for key in ["PR_HEAD_SHA","PR_BASE_SHA","PR_NUMBER"]:env.pop(key,None)
  result=subprocess.run([sys.executable,"-m","pytest","tests/test_ci_provenance.py","-q","-p","no:cacheprovider"],cwd=root/"evalcore",env=env,check=False)
  if result.returncode:raise SystemExit(result.returncode)
print("Provenance tests passed under actual synthetic PR and main-push environments")
