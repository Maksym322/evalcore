# EC-001 owner-authorized offline CI implementation

Implement the offline EC-001 CI foundation for the existing EvalCore and TicketPilot monorepo only. Use component pyprojects/Makefiles, document supported Python versions and actual tested versions, and retain existing API/schema behavior. Owner explicitly approved this planned CI task; do not expand unfinished TicketPilot features or deployment.

Add .github/workflows/offline-ci.yml on pull_request and push to main, with read-only contents permission, bounded job timeouts and short-lived artifacts under reports/. Pin every external action to a verified full commit. No pull_request_target, provider credentials, paid services or automatic baseline promotion.

Run pytest, Ruff check/format and strict mypy from each correct component directory. Establish current baseline before code changes; fix only CI compatibility issues needed for these declared checks, preserving existing assertions and behavior.

Add evalcore/tests/test_ci_gate.py with real executed synthetic gate pass and deliberate regression fail cases and exact expected exit codes. Use a genuine gate config; the toy config has no gate section. Keep datasets/baselines reviewed in source; never silently update expected answers. Run toy deterministic CLI evaluation with a real bounded JSON report and no provider keys.

Update MEMORY.md and CI documentation with actual local results, fixture commands, report/tested-SHA provenance and limitations. The coordinator will later review/push/create PR after allowance checks; remote PR artifacts and a future main-push run remain pending, never claim that they ran overnight.

All declared local component tests/lint/types, offline gates and workflow-structure checks pass. No real Gemini/judge/Supabase/database call, no read of .env/OAuth keys, no commit/push/PR/main merge/deployment by provider.

Coordinator baseline on source88e4402: existing Python3.14 environments passed140EvalCore+34TicketPilot tests,16gate/CLI tests, Ruff check/format; mypy was not run in that baseline. The night worker uses a separate Python3.12 environment with declared dev dependencies; establish its actual baseline before changes. scripts/ec001_checks.py is a trusted coordinator runner outside your editable scope. Do not modify it or frozen .fleet metadata.

Verified full action commits available: checkout d23441a48e516b6c34aea4fa41551a30e30af803; setup-python ece7cb06caefa5fff74198d8649806c4678c61a1; upload-artifact v6 b7c566a772e6b6bfb58ed0dc250532a479d7789f (official git tag checked). Keep artifact paths under reports/ and retention <=7days.

Included gemini-3.8-flash-medium only; one attempt and no recursive delegation. Do not commit/push/create PR/merge/deploy; coordinator commits and records local evidence. Remote CI verification and billing allowance are later coordinator steps, not passing offline evidence. No real environment files, judge calls, database services or baseline promotion.
