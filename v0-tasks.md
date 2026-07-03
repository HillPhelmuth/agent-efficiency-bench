# Agent Efficiency Bench v0 Task List

This checklist tracks the remaining work required to make Agent Efficiency Bench a credible v0 benchmark harness rather than a scaffold/demo. It is formatted like `plan-state.md` so another agent can complete one task at a time and fill in `Implementation Details` only after each task is verified.

## Status Legend

- [ ] Not started
- [x] Completed

---

## [x] Task 1: Define v0 completion scope and benchmark tiers

### Acceptance Criteria

- [x] `README.md` has a clear "v0 scope" section describing what is included and excluded.
- [x] `docs/design.md` distinguishes smoke, dev, release, and external/full benchmark tiers.
- [x] The docs define what it means for a task/run to be evaluated, unevaluated, failed, budget-exceeded, and successful.
- [x] The docs explicitly state that v0 requires end-to-end scoring for every source included in the default dev subset.
- [x] Existing tests continue to pass.

### Detailed Technical Instructions

1. Inspect current docs:
   - `README.md`
   - `docs/design.md`
   - `docs/running-benchmarks.md`
   - `plan-state.md`
2. Add a `## v0 Scope` section to `README.md` after the `## Goals` section.
3. Document the following tiers:
   - `smoke`: 1 task per selected source, meant for fast local/fake-provider validation.
   - `dev`: the deterministic public subset under `configs/sources.yaml` / `data/tasks/public_efficiency_subset.jsonl`.
   - `release`: a larger pinned subset suitable for model/scaffold comparison.
   - `external/full`: official benchmark suites that require upstream harness setup and may spend real money.
4. In `docs/design.md`, add a section near `## Current public subset strategy` defining the v0 completion contract:
   - Each default source must have a source adapter.
   - Each default source must have an evaluator or official harness result parser.
   - Default reports must exclude or label unevaluated runs.
   - Benchmark provenance must be recorded in manifests.
5. In `docs/running-benchmarks.md`, add a short note explaining that v0 uses the dev subset by default and official full harnesses are separate from local scaffold smoke runs.
6. Run verification:
   - `PYTHONPATH= uv run python -m pytest -q`
7. Do not modify code in this task unless tests reveal a doc-linked issue.

### Implementation Details

Updated `README.md` with a new `## v0 Scope` section after `## Goals`. The section now defines what v0 includes, what it explicitly excludes, the four benchmark tiers (`smoke`, `dev`, `release`, and `external/full`), and the shared meanings of `evaluated`, `unevaluated`, `successful`, `failed`, and `budget-exceeded`.

Updated `docs/design.md` with a `## v0 completion contract` section and a `## Benchmark tiers` section. The design doc now states that v0 requires a source adapter plus either a real evaluator or official harness result parser for every source in the default dev subset, requires end-to-end scoring for that subset, requires reports to exclude or label unevaluated runs, and requires manifests to preserve provenance.

Updated `docs/running-benchmarks.md` to state that the default local v0 workflow uses the dev subset, while smoke runs are for local validation and official full harnesses remain separate from local scaffold runs.

Verified with `PYTHONPATH= uv run python -m pytest -q`.

---

## [x] Task 2: Fix stale documentation and current subset descriptions

### Acceptance Criteria

- [x] `docs/running-benchmarks.md` correctly states that the current default subset has 32 tasks: 8 each for `software_engineering`, `web_research`, `terminal_work`, and `tool_workflow`.
- [x] `README.md` and `docs/design.md` consistently mention `sierra-research/tau2-bench` as part of the scaffolded public sources.
- [x] Stale calibration limitations that have since been implemented are either removed or annotated as historical.
- [x] Docs do not claim `RunTelemetry.scaffold` or manifest `budget` / `environment` are missing in current code.
- [x] Existing tests continue to pass.

### Detailed Technical Instructions

1. Read:
   - `README.md`
   - `docs/design.md`
   - `docs/running-benchmarks.md`
   - `docs/calibration/assistantbench-web-search-calibration.md`
   - `docs/calibration/assistantbench-gpt-5.4-nano-calibration.md`
2. Search for stale statements:
   - `RunManifest.budget`
   - `RunManifest.environment`
   - `RunTelemetry.scaffold`
   - `still empty`
   - `currently omitted/null`
   - `24 tasks`
   - `8 SWE-bench Lite tasks, 8 AssistantBench tasks, and 8 Terminal-Bench`
3. Update `docs/running-benchmarks.md` section 2 so it matches the actual catalog:
   - `software_engineering`: 8
   - `web_research`: 8
   - `terminal_work`: 8
   - `tool_workflow`: 8
4. In calibration docs, keep historical facts about old raw runs, but label them clearly as historical calibration artifacts produced before later telemetry improvements.
5. Run:
   - `PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl`
   - `PYTHONPATH= uv run python -m pytest -q`
6. Confirm the catalog output supports the updated docs.

### Implementation Details

Updated `docs/running-benchmarks.md` so section 2 now reflects the actual default dev subset: 32 tasks total, with 8 each in `software_engineering`, `web_research`, `terminal_work`, and `tool_workflow`, matching the current catalog output.

Confirmed `README.md` and `docs/design.md` already consistently include `sierra-research/tau2-bench` in the scaffolded public sources and current subset strategy, so no content change was needed there.

Updated both calibration reports to clearly mark older missing manifest budget/environment fields and missing telemetry scaffold identity as historical artifacts of those raw runs, not current-code limitations. The remaining notes now describe only still-relevant telemetry/evaluation gaps.

Verified with `uv run aeb catalog data/tasks/public_efficiency_subset.jsonl`, which reported 8 tasks each for `software_engineering`, `web_research`, `terminal_work`, and `tool_workflow`, and `uv run python -m pytest -q`.

---

## [x] Task 3: Exclude placeholder/template tasks from Terminal-Bench sampling

### Acceptance Criteria

- [x] `aeb audit-tasks data/tasks/public_efficiency_subset.jsonl` reports no `placeholder_instruction` warnings.
- [x] `terminal_bench__template` is not present in regenerated `data/tasks/public_efficiency_subset.jsonl`.
- [x] Terminal-Bench sampling remains deterministic.
- [x] Tests cover the exclusion behavior.
- [x] Full test suite passes.

### Detailed Technical Instructions

1. Inspect current source adapter:
   - `src/agent_efficiency_bench/sources.py`
   - Focus on `load_terminal_bench_github_subset` and `normalize_terminal_bench_task`.
2. Add a helper in `sources.py`, for example `_is_terminal_bench_candidate_path(path: str) -> bool`, that excludes paths where:
   - the task id directory is `template`, or
   - the path includes obvious template/example directories that should not be benchmarked.
3. Apply the filter before deterministic sampling in `load_terminal_bench_github_subset`.
4. Add or update tests in the relevant test file. Search first:
   - `search_files("terminal_bench", path="tests", file_glob="*.py")`
5. Test cases should verify that candidate paths containing `/template/task.yaml` are excluded before `_stable_sample` is applied.
6. Regenerate the subset:
   - `PYTHONPATH= uv run aeb build-subset --config configs/sources.yaml --output data/tasks/public_efficiency_subset.jsonl`
7. Verify:
   - `PYTHONPATH= uv run aeb audit-tasks data/tasks/public_efficiency_subset.jsonl`
   - `PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl`
   - `PYTHONPATH= uv run python -m pytest -q`
8. Update docs if the regenerated Terminal-Bench task IDs are mentioned anywhere.

### Implementation Details

Updated `src/agent_efficiency_bench/sources.py` so `load_terminal_bench_github_subset` filters candidate GitHub task paths through a new `_is_terminal_bench_candidate_path(path)` helper before calling `_stable_sample`. The helper rejects obvious non-benchmark paths such as `template`, `templates`, `example`, and `examples`, which removes placeholder YAML tasks from the candidate pool without changing the deterministic SHA-256 sampling logic used on the remaining paths.

Added a regression test in `tests/test_normalizers.py` that monkeypatches the GitHub tree to include `tasks/template/task.yaml` alongside two real task paths and verifies that the sampled results only contain the real task IDs. This specifically checks that exclusion happens before deterministic sampling.

Regenerated `data/tasks/public_efficiency_subset.jsonl` with `uv run aeb build-subset --config configs/sources.yaml --output data/tasks/public_efficiency_subset.jsonl`. Verified `uv run aeb audit-tasks data/tasks/public_efficiency_subset.jsonl` reports `No warnings`, confirmed `terminal_bench__template` is absent from the regenerated subset, confirmed the catalog still reports 32 tasks across the four expected categories, and ran `uv run python -m pytest -q`, which passed with `57 passed`.

---

## [x] Task 4: Add suite-level budget controls and abort behavior

### Acceptance Criteria

- [x] CLI run commands support suite-level budget options for max total USD, max tasks, max wall-clock seconds, and max failures before abort.
- [x] Suite-level budget state is recorded in `manifest.json`.
- [x] Runs stop before starting the next task when a suite-level limit is exceeded.
- [x] Tests cover max failures and max suite cost/time/task limits without spending tokens.
- [x] Full test suite passes.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/runner.py`
   - `src/agent_efficiency_bench/budget.py`
   - `src/agent_efficiency_bench/cli.py`
   - `tests/test_runner.py`
   - `tests/test_cli.py`
2. Introduce a small suite budget config, either in `schemas.py` or `runner.py`, with fields:
   - `max_suite_estimated_usd: float | None`
   - `max_suite_wall_clock_seconds: float | None`
   - `max_suite_tasks: int | None`
   - `max_suite_failures: int | None`
3. Extend `BenchmarkRunner.__init__` to accept the suite budget config.
4. Track cumulative suite cost, task count, failures, and elapsed time in `BenchmarkRunner.run_tasks`.
5. Before each task starts, check whether starting another task would violate `max_suite_tasks` or existing abort conditions.
6. After each task completes, update suite counters and stop if a limit is reached.
7. Add suite status to the manifest under a new key such as `suite_budget` or `suite_limits`.
8. Extend CLI commands:
   - `run-answer`
   - `run-tool-loop`
   - `run-assistantbench`
   with options such as `--max-suite-usd`, `--max-suite-seconds`, `--max-suite-tasks`, `--max-suite-failures`.
9. Add tests using fake agents/evaluators so no OpenRouter calls occur.
10. Run:
    - `PYTHONPATH= uv run python -m pytest tests/test_runner.py tests/test_cli.py -q`
    - `PYTHONPATH= uv run python -m pytest -q`
11. Update `docs/running-benchmarks.md` with the new safety options.

### Implementation Details

Implemented suite-level budget controls in `src/agent_efficiency_bench/runner.py` with a new `SuiteBudgetConfig` dataclass. `BenchmarkRunner` now tracks cumulative suite cost, failures, completed task count, and suite wall-clock time, and it stops before starting the next task when `max_suite_estimated_usd`, `max_suite_wall_clock_seconds`, `max_suite_tasks`, or `max_suite_failures` has been reached.

Extended `RunManifest` in `src/agent_efficiency_bench/schemas.py` with a `suite_budget` field. The manifest now records configured suite limits, observed totals (`tasks_completed`, `failures`, `estimated_usd`, `wall_clock_seconds`), and whether the suite aborted with a specific reason such as `suite_budget_cost` or `suite_budget_failures`.

Extended the `run-answer`, `run-tool-loop`, and `run-assistantbench` CLI commands in `src/agent_efficiency_bench/cli.py` with `--max-suite-usd`, `--max-suite-seconds`, `--max-suite-tasks`, and `--max-suite-failures`, and documented those safety options in `docs/running-benchmarks.md`.

Added targeted tests in `tests/test_runner.py` for max suite tasks, failures, cost, and wall-clock time, and added CLI plumbing tests in `tests/test_cli.py` to verify the new options are passed into `BenchmarkRunner` without invoking real providers. Verified with `uv run python -m pytest tests/test_runner.py tests/test_cli.py -q` and `uv run python -m pytest -q`; the full suite passed with `64 passed`.

---

## [x] Task 5: Add provider-side server tool telemetry fields

### Acceptance Criteria

- [x] Telemetry and/or run output records OpenRouter server tools separately from local harness tool calls.
- [x] Reports can group or display whether server tools were configured.
- [x] OpenRouter annotations/citations counts can be summarized in reports or run outputs.
- [x] Existing `num_tool_calls` semantics remain local-tool-only and are documented.
- [x] Tests cover web-search traces and summary/report behavior.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/schemas.py`
   - `src/agent_efficiency_bench/agents/openrouter_answer.py`
   - `src/agent_efficiency_bench/agents/openrouter_tool_loop.py`
   - `src/agent_efficiency_bench/reporting.py`
   - `tests/test_answer_agent.py`
   - `tests/test_tool_loop_agent.py`
   - `tests/test_reporting.py`
2. Decide where to store provider-side metadata. Preferred minimal v0 approach:
   - Add fields to `RunTelemetry`:
     - `server_tools_configured: list[str] = Field(default_factory=list)`
     - `num_citations: int = 0`
     - `num_annotations: int = 0`
   - Keep `num_tool_calls` unchanged for local harness tools.
3. Populate these fields in `OpenRouterAnswerAgent` from configured tools and response annotations/citations.
4. Populate aggregated values in `OpenRouterToolLoopAgent` across both calls.
5. Update report summaries to include citation/annotation totals or averages if useful.
6. Update report grouping so `tools_enabled` can use `RunTelemetry.server_tools_configured` when manifest metadata is unavailable.
7. Add tests that verify:
   - `openrouter:web_search` appears in `server_tools_configured`.
   - Citation and annotation counts are nonzero when fake raw response contains URL citations.
   - `num_tool_calls` remains `0` for provider-side server search.
8. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_answer_agent.py tests/test_tool_loop_agent.py tests/test_reporting.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
9. Update `docs/openrouter.md`, `docs/running-benchmarks.md`, and calibration docs to explain the distinction.

### Implementation Details

Extended `RunTelemetry` in `src/agent_efficiency_bench/schemas.py` with `server_tools_configured`, `num_citations`, and `num_annotations`, and updated `BudgetTracker.to_run_telemetry` in `src/agent_efficiency_bench/budget.py` so these fields can be populated without changing local budget accounting.

Updated `src/agent_efficiency_bench/agents/openrouter_answer.py` and `src/agent_efficiency_bench/agents/openrouter_tool_loop.py` to record configured OpenRouter server tools separately from local harness tools and to count returned annotations/citations from the raw OpenRouter response. `num_tool_calls` remains unchanged and still counts only local harness tool calls. For tool-loop runs, citation and annotation counts are aggregated across both the research and final calls while preserving the configured server-tool list from the research step.

Updated `src/agent_efficiency_bench/reporting.py` so `tools_enabled` can fall back to `RunTelemetry.server_tools_configured` when manifest metadata is absent, and added summary metrics for `total_citations`, `avg_citations`, `total_annotations`, and `avg_annotations`.

Added tests in `tests/test_answer_agent.py`, `tests/test_tool_loop_agent.py`, and `tests/test_reporting.py` verifying that `openrouter:web_search` appears in `server_tools_configured`, annotations/citations counts are surfaced in telemetry and summaries, and `num_tool_calls` stays `0` for provider-side search. Updated `docs/openrouter.md`, `docs/running-benchmarks.md`, and the calibration docs to document the new fields and the local-only meaning of `num_tool_calls`. Verified with `uv run python -m pytest tests/test_answer_agent.py tests/test_tool_loop_agent.py tests/test_reporting.py -q` and `uv run python -m pytest -q`; the full suite passed with `65 passed`.

---

## [x] Task 6: Ensure every default run path uses a real evaluator

### Acceptance Criteria

- [x] Default benchmark commands do not silently use `NoOpEvaluator` for task categories that have known success criteria.
- [x] `run-answer` and `run-tool-loop` select evaluators based on task category/source/success criteria.
- [x] Unevaluated runs are explicitly marked as unevaluated, not treated as benchmark results.
- [x] Tests cover evaluator selection for AssistantBench, SWE-bench, Terminal-Bench, tau2, and unknown/manual tasks.
- [x] Full test suite passes.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/cli.py`
   - `src/agent_efficiency_bench/harnesses/assistantbench.py`
   - `src/agent_efficiency_bench/evaluators/simple.py`
   - `src/agent_efficiency_bench/evaluators/structured.py`
   - `src/agent_efficiency_bench/evaluators/base.py`
   - `src/agent_efficiency_bench/schemas.py`
2. Create an evaluator-selection module, for example:
   - `src/agent_efficiency_bench/evaluators/registry.py`
3. Add a function such as `evaluator_for_task(task: BenchmarkTask) -> Evaluator`.
4. Implement selection rules:
   - AssistantBench / `web_research`: use `AssistantBenchEvaluator`.
   - `success_criteria.type == "structured_answer"`: use structured/exact fallback where possible.
   - SWE-bench, Terminal-Bench, tau2: return an explicit evaluator that marks outputs as unevaluated unless official harness result metadata is present. Do not use success=true without harness data.
   - Unknown/manual: return an explicit `UnevaluatedEvaluator` with reason.
5. Add `UnevaluatedEvaluator` if not already present. It should return `success=False`, `quality_score=0.0`, and details explaining why.
6. Update `run-answer` and `run-tool-loop` in `cli.py` to use the registry instead of a blanket `NoOpEvaluator`.
7. Preserve `run-assistantbench` behavior unless the registry can replace it cleanly.
8. Add tests for registry selection and CLI run behavior using fake results where possible.
9. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_cli.py tests/test_*evaluator*.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
10. Update docs to state which categories are fully scored and which are currently unevaluated until official harness execution is added.

### Implementation Details

Added `src/agent_efficiency_bench/evaluators/registry.py` with `evaluator_for_task(task)`, `RegistryEvaluator`, and `OfficialHarnessResultEvaluator`. The registry now dispatches AssistantBench tasks to the existing AssistantBench evaluator logic, uses structured or exact evaluators when deterministic metadata is available, routes SWE-bench, Terminal-Bench, and tau2 tasks to an official-harness evaluator that requires `result.output["harness_result"]`, and falls back to an explicit `UnevaluatedEvaluator` for unknown or manual tasks.

Extended `EvaluationScore` in `src/agent_efficiency_bench/evaluators/base.py` with an `evaluated` flag and added `UnevaluatedEvaluator` in `src/agent_efficiency_bench/evaluators/simple.py`. Updated `src/agent_efficiency_bench/runner.py` so unevaluated scores are normalized to `terminated_by="not_evaluated"` when appropriate, while truly evaluated failures become `terminated_by="evaluated"` and successes become `terminated_by="success"`.

Updated `src/agent_efficiency_bench/cli.py` so `run-answer`, `run-tool-loop`, and `run-assistantbench` all use `RegistryEvaluator()` instead of a blanket `NoOpEvaluator` or a one-off AssistantBench-only path. This keeps default run commands task-aware without pretending unsupported harness-backed categories are locally benchmark-scored.

Added coverage in `tests/test_evaluators.py`, `tests/test_runner.py`, and `tests/test_cli.py` for AssistantBench, SWE-bench, Terminal-Bench, tau2, and unknown/manual tasks, including explicit unevaluated handling and CLI registry wiring. Updated `README.md`, `docs/design.md`, and `docs/running-benchmarks.md` to state that AssistantBench-style web-research tasks can be locally scored, while SWE-bench, Terminal-Bench, and tau2 remain explicitly unevaluated in generic local runs until official harness result metadata is available. Verified with `uv run python -m pytest tests/test_cli.py tests/test_evaluators.py tests/test_structured_evaluator.py tests/test_assistantbench_harness.py tests/test_runner.py -q` and `uv run python -m pytest -q`; the full suite passed with `72 passed`.

---

## [x] Task 7: Add structured expected metadata for AssistantBench dev subset

### Acceptance Criteria

- [x] AssistantBench sampled tasks include `raw.expected` metadata when it can be derived deterministically.
- [x] Structured evaluator is used for AssistantBench tasks with `raw.expected`.
- [x] Exact-match fallback remains available when structured metadata cannot be derived.
- [x] Tests cover AssistantBench normalization with structured expected fields.
- [x] Full test suite passes.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/sources.py`, especially `normalize_assistantbench`.
   - `src/agent_efficiency_bench/harnesses/assistantbench.py`.
   - `src/agent_efficiency_bench/evaluators/structured.py`.
   - `tests/test_normalizers.py` and AssistantBench-related tests.
2. Determine the fields available in AssistantBench rows. Use a safe sample if needed:
   - `PYTHONPATH= uv run python - <<'PY'
from agent_efficiency_bench.sources import load_sources_from_config
for task in load_sources_from_config('configs/sources.yaml'):
    if task.source == 'AssistantBench/AssistantBench':
        print(task.raw)
        break
PY`
3. In `normalize_assistantbench`, derive `raw["expected"]` from known row fields when possible:
   - `text_contains`: include answer string or normalized answer aliases when deterministic.
   - `required_domains`: include domains from source URLs if provided and relevant.
   - `requires_citation`: true when source URLs are provided or the task requires web research.
4. Avoid inventing expected numbers or domains if the source row does not provide evidence.
5. Update tests to validate the normalized expected shape.
6. Regenerate the subset:
   - `PYTHONPATH= uv run aeb build-subset --config configs/sources.yaml --output data/tasks/public_efficiency_subset.jsonl`
7. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_normalizers.py tests/test_assistantbench_harness.py tests/test_structured_evaluator.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
8. Update docs/calibration notes if this changes expected scoring behavior.

### Implementation Details

Updated `src/agent_efficiency_bench/sources.py` so `normalize_assistantbench` now derives deterministic `raw.expected` metadata through a new helper before constructing the normalized task. When an AssistantBench row contains an answer, the normalizer now adds `expected.text_contains` with that exact answer string. When source URLs are present, it extracts normalized domains into `expected.required_domains`. When either answer text or URL-derived domains are present, it also sets `expected.requires_citation = true`.

This keeps the derivation evidence-based: it does not invent numeric expectations or domains that are not present in the source row. AssistantBench tasks that still lack deterministic expected metadata continue to fall back to the existing exact-answer path when `raw.answer` is present, and otherwise remain unevaluated through the existing evaluator registry behavior.

Added tests in `tests/test_normalizers.py` to validate the normalized expected shape and the no-expected case, and added an AssistantBench harness test in `tests/test_assistantbench_harness.py` to confirm the exact-match fallback remains available when `raw.expected` is absent. Regenerated `data/tasks/public_efficiency_subset.jsonl` with `uv run aeb build-subset --config configs/sources.yaml --output data/tasks/public_efficiency_subset.jsonl`; the regenerated AssistantBench rows now include `raw.expected`, for example `{"text_contains": ["Potash Markets - Clark Street"], "requires_citation": true}` on the first sampled task.

Updated the calibration notes in `docs/calibration/assistantbench-web-search-calibration.md` and `docs/calibration/assistantbench-gpt-5.4-nano-calibration.md` to note that current-code regenerated AssistantBench subsets now carry deterministic structured expected metadata. Verified with `uv run python -m pytest tests/test_normalizers.py tests/test_assistantbench_harness.py tests/test_structured_evaluator.py -q` and `uv run python -m pytest -q`; the full suite passed with `74 passed`.

---

## [x] Task 8: Implement Terminal-Bench official execution adapter

### Acceptance Criteria

- [x] Terminal-Bench adapter can perform a dry run that validates prerequisites and task mapping without executing containers.
- [x] Terminal-Bench adapter can optionally execute the official harness behind an explicit flag.
- [x] Official result output is parsed into common result/telemetry fields.
- [x] CLI exposes guarded execution separate from command preview.
- [x] Tests cover command construction, prerequisite failure, dry-run behavior, and result parsing without running Docker.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/harnesses/terminal_bench.py`
   - `src/agent_efficiency_bench/cli.py`
   - `tests/test_terminal_bench_harness.py`
   - `docs/running-benchmarks.md`
2. Keep `terminal-bench-command` as a safe preview command.
3. Add a new adapter function in `terminal_bench.py`, for example `run_terminal_bench_task(...)`, that:
   - checks prerequisites using `check_terminal_bench_prerequisites`;
   - builds the command using `build_terminal_bench_command`;
   - supports `dry_run=True` to return planned command and prerequisite status;
   - supports `execute=True` only when explicitly requested;
   - captures stdout/stderr/exit code when executed.
4. Add a parser function for the actual result JSON shape expected from Harbor/Terminal-Bench. If the exact shape is not guaranteed, parse defensively and include raw result metadata.
5. Add a CLI command such as `aeb run-terminal-bench-official` with options:
   - `--task-id`
   - `--model`
   - `--output-dir`
   - `--agent`
   - `--dataset`
   - `--dry-run / --execute`
   - budget/safety options from Task 4 if available.
6. Make `--execute` required for any command that can run Docker or spend model tokens.
7. Add tests using monkeypatch/fake subprocess calls. Do not require Docker/Harbor in tests.
8. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_terminal_bench_harness.py tests/test_cli.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
9. Update docs with dry-run and execute examples plus safety warnings.

### Implementation Details

Extended `src/agent_efficiency_bench/harnesses/terminal_bench.py` with `run_terminal_bench_task(...)`, which now performs prerequisite checks, builds the Harbor command with the existing `build_terminal_bench_command(...)`, supports a default dry-run path, and only executes Harbor when `execute=True` is passed explicitly. The dry-run payload includes the planned command, prerequisite status, result path, and suite-budget metadata. The execute path captures `stdout`, `stderr`, `exit_code`, and parsed result data when a result JSON file is present.

Updated `parse_terminal_bench_result(...)` to parse Terminal-Bench/Harbor results defensively. It now looks for `success`/`passed`/`resolved`, `quality_score`/`score`, and status fields at either the top level or under a nested `summary` object, and always returns a normalized structure with `success`, `quality_score`, `status`, `details`, and `raw`.

Added a new CLI command, `aeb run-terminal-bench-official`, in `src/agent_efficiency_bench/cli.py`. This command is separate from the safe preview-only `terminal-bench-command`. It defaults to dry-run mode and requires `--execute` before Harbor can be invoked. It also accepts the suite-budget safety options introduced earlier so planned official runs can carry the same budget metadata.

Added focused tests in `tests/test_terminal_bench_harness.py` and `tests/test_cli.py` for dry-run behavior, prerequisite failure, execute-path subprocess capture, defensive result parsing, and CLI dry-run/execute plumbing without requiring Docker or Harbor in test environments. Updated `docs/running-benchmarks.md` with dry-run and execute examples plus an explicit safety warning. Verified with `uv run python -m pytest tests/test_terminal_bench_harness.py tests/test_cli.py -q` and `uv run python -m pytest -q`; the full suite passed with `80 passed`.

---

## [x] Task 9: Implement SWE-bench official execution adapter

### Acceptance Criteria

- [x] SWE-bench adapter can write predictions from model patches and run a dry-run validation path.
- [x] Optional official evaluation execution is guarded behind an explicit flag.
- [x] SWE-bench result files are parsed into common success/quality metadata.
- [x] CLI exposes guarded official SWE-bench execution separate from command preview.
- [x] Tests cover prediction writing, command construction, dry-run behavior, and result parsing without running official SWE-bench.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/harnesses/swe_bench.py`
   - `src/agent_efficiency_bench/cli.py`
   - SWE-bench-related tests under `tests/`.
2. Keep `swe-bench-command` as a safe preview command.
3. Extend `swe_bench.py` with functions such as:
   - `build_prediction_row(instance_id, model_patch, model_name_or_path) -> dict`
   - `run_swe_bench_evaluation(..., dry_run: bool, execute: bool) -> dict`
   - `parse_swe_bench_report(path) -> dict`
4. Ensure prediction JSONL appends or overwrites are explicit. Avoid accidental duplicate rows unless requested.
5. Add a CLI command such as `aeb run-swe-bench-official` with options:
   - `--predictions-path`
   - `--run-id`
   - `--dataset-name`
   - `--dry-run / --execute`
6. Require explicit `--execute` for subprocess invocation.
7. Parse official results defensively. At minimum identify per-instance resolved/unresolved status when present.
8. Add tests using temporary files and monkeypatched subprocess calls.
9. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_swe_bench_harness.py tests/test_cli.py -q`
   - If `tests/test_swe_bench_harness.py` does not exist, create it.
   - `PYTHONPATH= uv run python -m pytest -q`
10. Update docs with safe preview, dry-run, and execute examples.

### Implementation Details

Extended `src/agent_efficiency_bench/harnesses/swe_bench.py` with `build_prediction_row(...)`, an explicit overwrite/append-aware `write_prediction(...)`, `check_swe_bench_prerequisites(...)`, `run_swe_bench_evaluation(...)`, and `parse_swe_bench_report(...)`. The adapter now supports a default dry-run validation path, requires `execute=True` for actual subprocess invocation, and parses resolved/unresolved instance IDs plus success-rate metadata from common official SWE-bench report shapes.

Kept `swe-bench-command` as the safe preview-only path and added a separate `aeb run-swe-bench-official` command in `src/agent_efficiency_bench/cli.py`. Like the Terminal-Bench official command, it defaults to dry-run mode and only runs the official harness when `--execute` is passed explicitly. It also accepts the suite-budget metadata options so planned official runs can carry the same safety metadata.

Added focused tests in `tests/test_swe_bench_harness.py` for prediction-row construction, explicit overwrite behavior, dry-run prerequisite reporting, execute-path subprocess capture, and defensive report parsing. Added CLI tests in `tests/test_cli.py` for dry-run default behavior and explicit `--execute` plumbing without invoking the real SWE-bench package. Updated `docs/running-benchmarks.md` with preview, dry-run, execute, and safety examples. Verified with `uv run python -m pytest tests/test_swe_bench_harness.py tests/test_cli.py -q` and `uv run python -m pytest -q`; the full suite passed with `88 passed`.

---

## [x] Task 10: Implement tau2-bench tool-workflow harness integration

### Acceptance Criteria

- [x] tau2 tasks can be mapped from normalized task IDs back to domain/source task metadata.
- [x] A dry-run path validates tau2 prerequisites and planned execution.
- [x] A guarded execute path can run tau2-style workflows when dependencies are installed.
- [x] tau2 evaluation criteria are parsed into common success/quality metadata.
- [x] Tests cover mapping, dry-run, and result parsing without running the real tau2 environment.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/sources.py`, especially `normalize_tau2_bench`.
   - `data/tasks/public_efficiency_subset.jsonl` for raw tau2 metadata.
   - `configs/sources.yaml` tau2 entries.
2. Create a new harness module:
   - `src/agent_efficiency_bench/harnesses/tau2_bench.py`
3. Implement helpers:
   - `parse_tau2_task_id(task_id: str) -> tuple[str, str]` for domain/id extraction.
   - `build_tau2_command(domain, task_id, model, output_dir, ...) -> list[str]` once the official command shape is confirmed.
   - `parse_tau2_result(path) -> dict` for evaluation output.
4. If the official command shape is not known, document the unresolved dependency and implement dry-run/prerequisite structure without pretending execution is complete.
5. Add a CLI command such as `aeb tau2-bench-command` or `aeb run-tau2-official`.
6. Tests should not require the tau2 package or external services.
7. Add result-to-score logic so `success_criteria.type == "tau2_actions"` can be evaluated from parsed result metadata.
8. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_tau2_source.py tests/test_tau2_bench_harness.py tests/test_cli.py -q`
   - Create `tests/test_tau2_bench_harness.py` if needed.
   - `PYTHONPATH= uv run python -m pytest -q`
9. Update `README.md` and `docs/running-benchmarks.md` with tau2 workflow status and command examples.

### Implementation Details

Added `src/agent_efficiency_bench/harnesses/tau2_bench.py` with `parse_tau2_task_id(...)`, `build_tau2_command(...)`, `check_tau2_prerequisites(...)`, `run_tau2_task(...)`, and `parse_tau2_result(...)`. Normalized tau2 task IDs such as `tau2_bench_retail__55` can now be mapped back to `(domain="retail", task_id="55")`, and the adapter can produce a dry-run plan for tau2 execution.

Because this repository does not yet pin a single official upstream tau2 runner command, the adapter is explicit about that unresolved dependency. Dry runs report `unresolved_dependency=true` unless a concrete `runner_module` is supplied. The execute path is guarded behind `execute=True` and additionally requires a configured/importable runner module before it will attempt subprocess execution. This avoids pretending tau2 execution is fully standardized here while still giving the repository a real harness surface for planning, mapping, and result parsing.

`parse_tau2_result(...)` now converts tau2-style action outcomes into common success/quality metadata. It reads `success`/`passed`, `quality_score`/`score`, and action counts such as `passed_actions` and `total_actions`, computing a quality ratio from action counts when an explicit score is absent. That shape is compatible with the existing official-harness evaluator flow that expects `success` and `quality_score` metadata in harness results.

Added a new `aeb run-tau2-official` command in `src/agent_efficiency_bench/cli.py` and tests in `tests/test_tau2_bench_harness.py` plus `tests/test_cli.py` for task-id parsing, unresolved-runner dry runs, guarded execute behavior, result parsing, and CLI plumbing without requiring a real tau2 environment. Updated `README.md` and `docs/running-benchmarks.md` to describe current tau2 status and command examples. Verified with `uv run python -m pytest tests/test_tau2_source.py tests/test_tau2_bench_harness.py tests/test_cli.py -q` and `uv run python -m pytest -q`; the full suite passed with `96 passed`.

---

## [x] Task 11: Add repeated-trial support for benchmark runs

### Acceptance Criteria

- [x] CLI run commands support an `--n-trials` option.
- [x] Repeated runs produce distinct stable run IDs and artifacts per trial.
- [x] Reports aggregate across trials and expose variance where possible.
- [x] Manifests record trial count and trial indexing.
- [x] Tests cover repeated runs without provider calls.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/runner.py`
   - `src/agent_efficiency_bench/reporting.py`
   - `src/agent_efficiency_bench/metrics.py`
   - `src/agent_efficiency_bench/schemas.py`
   - `tests/test_runner.py`
   - `tests/test_reporting.py`
2. Add a `trial_index` field to `RunTelemetry` or store it in run output/manifest if changing telemetry is too invasive. Preferred: `trial_index: int | None = None`.
3. Update `BenchmarkRunner.run_tasks` to support repeated trials, either via a new `n_trials` argument or wrapper method.
4. Ensure artifact directories do not collide. Suggested path shape:
   - `<output_dir>/<task_id>/trial-000/trace.jsonl`
   - `<output_dir>/<task_id>/trial-001/trace.jsonl`
5. Update agent `run_id` generation if needed so `run_id` includes trial identity or runner wraps it consistently.
6. Add `--n-trials` to relevant CLI commands.
7. Update reporting to include mean/stddev for cost, latency, tokens, and quality when repeated trials exist.
8. Add tests with a fake deterministic agent to verify repeated artifact generation and telemetry count.
9. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_runner.py tests/test_reporting.py tests/test_cli.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
10. Update docs with guidance that release comparisons should use repeated trials where budget allows.

### Implementation Details

Extended `RunTelemetry` in `src/agent_efficiency_bench/schemas.py` with `trial_index` and `RunManifest` with `trial_count` plus `trial_indices`. This keeps repeated-trial metadata attached to both per-run telemetry and suite-level manifests without changing existing single-trial behavior.

Updated `BenchmarkRunner` in `src/agent_efficiency_bench/runner.py` so `run_tasks(..., n_trials=...)` repeats each selected task deterministically, creates trial-specific artifact directories like `.../<task_id>/trial-000/`, stamps `trial_index` into telemetry, and disambiguates runner-produced `run_id` values as `...__trial_000`. The runner also creates the artifact directory itself before invoking the agent so repeated trials do not depend on agent-side directory creation.

Extended `run-answer`, `run-tool-loop`, and `run-assistantbench` in `src/agent_efficiency_bench/cli.py` with `--n-trials`, and updated `src/agent_efficiency_bench/reporting.py` so reports can group by `trial_index` and include standard deviation fields for cost, latency, total tokens, and quality alongside the existing mean-style summary metrics.

Added focused regression coverage in `tests/test_runner.py`, `tests/test_reporting.py`, and `tests/test_cli.py` for repeated artifact layout, trial-index/run-id propagation, variance summaries, and CLI plumbing without provider calls. Updated `README.md` and `docs/running-benchmarks.md` to document when to use repeated trials and how the artifact/manifests/reporting outputs change. Verified with `uv run python -m pytest tests/test_runner.py tests/test_reporting.py tests/test_cli.py -q` and `uv run python -m pytest -q`; the full suite passed with `98 passed`.

---

## [ ] Task 12: Add benchmark provenance metadata to manifests

### Acceptance Criteria

- [ ] `manifest.json` records dataset/source revision metadata when available.
- [ ] `manifest.json` records evaluator identity/version or checker identity.
- [ ] `manifest.json` records harness identity/version for official harness paths.
- [ ] OpenRouter returned model/provider metadata is preserved where available.
- [ ] Tests verify new manifest fields are populated or explicitly null/unknown.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/schemas.py`, `RunManifest`.
   - `src/agent_efficiency_bench/runner.py`, `_write_manifest`.
   - `src/agent_efficiency_bench/providers/openrouter.py`.
   - `tests/test_execution_schemas.py`
   - `tests/test_runner.py`
2. Extend `RunManifest` with provenance fields. Suggested structure:
   - `source_revisions: dict[str, Any] = Field(default_factory=dict)`
   - `evaluator: dict[str, Any] = Field(default_factory=dict)`
   - `harness: dict[str, Any] = Field(default_factory=dict)`
   - `provider: dict[str, Any] = Field(default_factory=dict)`
3. Populate evaluator identity from `self.evaluator.__class__.__name__` and optional attributes.
4. For source revisions, start with config-level metadata and known URLs. If exact upstream revisions are not available, record `unknown` explicitly rather than fabricating.
5. For OpenRouter, preserve requested model in manifest and returned model in run telemetry. If raw response contains provider/routing metadata, record it in result output or provider provenance.
6. Add tests for manifest schema and runner serialization.
7. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_execution_schemas.py tests/test_runner.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
8. Update `docs/openrouter.md` and `docs/running-benchmarks.md` to describe provenance fields.

### Implementation Details

_To be filled in after completion._

---

## [ ] Task 13: Add release/dev subset configuration support

### Acceptance Criteria

- [ ] The project supports separate source configs for smoke, dev, and release subsets.
- [ ] The default quick-start remains cheap and fast.
- [ ] Documentation explains when to use each config.
- [ ] Tests or smoke commands verify all configs can be parsed.
- [ ] Full test suite passes.

### Detailed Technical Instructions

1. Inspect:
   - `configs/sources.yaml`
   - `src/agent_efficiency_bench/sources.py`
   - `README.md`
   - `docs/running-benchmarks.md`
2. Create additional configs:
   - `configs/sources-smoke.yaml` with 1 task per source.
   - `configs/sources-dev.yaml` equivalent to the current 32-task config.
   - Optionally make `configs/sources.yaml` point to or duplicate dev behavior for backward compatibility.
   - `configs/sources-release.yaml` with larger sample sizes, but keep values conservative unless the user specifies exact release counts.
3. Update docs examples to use smoke for first-time validation and dev for normal local comparison.
4. Add tests that parse each config and validate expected source names/types without necessarily downloading all upstream data if that would be slow. If network access is required, keep it as a documented manual verification instead of a unit test.
5. Run:
   - `PYTHONPATH= uv run aeb build-subset --config configs/sources-smoke.yaml --output data/tasks/public_efficiency_smoke.jsonl`
   - `PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_smoke.jsonl`
   - `PYTHONPATH= uv run python -m pytest -q`
6. Decide whether generated smoke JSONL should be committed. If committed, update `data/tasks/README.md`.

### Implementation Details

_To be filled in after completion._

---

## [ ] Task 14: Improve reporting for leaderboard-style comparisons

### Acceptance Criteria

- [ ] Reports include success rate, mean quality, median/p95 latency, median/p95 cost, cost per success, tokens per success, retry/error rates, and tool/server-tool metadata.
- [ ] Reports can be written as Markdown and machine-readable JSON or CSV.
- [ ] Reports clearly label unevaluated and budget-exceeded runs.
- [ ] Reports support grouping by category, source, model, scaffold, tools, horizon, and trial index where applicable.
- [ ] Tests cover Markdown and JSON/CSV output.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/reporting.py`
   - `src/agent_efficiency_bench/metrics.py`
   - `src/agent_efficiency_bench/cli.py`, `report` command.
   - `tests/test_reporting.py`
   - `tests/test_cli.py`
2. Add output format support to `aeb report`:
   - `--format markdown` default
   - `--format json`
   - Optional `--format csv`
3. Expand summary metrics to include the recommended leaderboard columns in `docs/design.md`:
   - `success_rate`
   - `mean_quality`
   - `median_cost_usd`
   - `cost_per_success`
   - `median_latency_seconds`
   - `p95_latency_seconds`
   - `tokens_per_success`
   - `tool_calls_per_success`
   - `retry_rate`
4. Ensure failed and budget-exceeded runs count toward spend/tokens/latency but not success-gated quality.
5. Add explicit unevaluated counts based on `terminated_by` or evaluation reason if available.
6. Add tests for grouped output and JSON serialization.
7. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_reporting.py tests/test_cli.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
8. Update `README.md` and `docs/running-benchmarks.md` with examples for Markdown and JSON reports.

### Implementation Details

_To be filled in after completion._

---

## [ ] Task 15: Add non-token-spending end-to-end CLI smoke tests

### Acceptance Criteria

- [ ] A single test or script verifies build-subset, audit, fake-provider run, manifest generation, and report generation without real OpenRouter calls.
- [ ] CI/local tests do not require `OPENROUTER_API_KEY`.
- [ ] The smoke path creates and cleans temporary outputs.
- [ ] Documentation tells contributors how to run the smoke verification.
- [ ] Full test suite passes.

### Detailed Technical Instructions

1. Inspect existing tests:
   - `tests/test_cli.py`
   - `tests/test_integration_fake_provider.py` if present.
   - `tests/test_runner.py`
2. Add a fake-provider or fake-agent CLI path if one already exists; otherwise keep this as a Python integration test that calls internal APIs rather than invoking OpenRouter.
3. The smoke test should verify:
   - Build/load a tiny set of tasks from static fixtures or generated `BenchmarkTask` objects.
   - Run through `BenchmarkRunner` with fake agent and evaluator.
   - Write `run_results.jsonl`, `run_telemetry.jsonl`, `manifest.json`, and trace files.
   - Generate a report from the telemetry.
   - Audit the task file.
4. If using Typer `CliRunner`, ensure output directories are temporary via `tmp_path`.
5. Do not depend on network access or API keys.
6. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_cli.py tests/test_integration_fake_provider.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
7. Update `README.md` quick-start or `docs/running-benchmarks.md` with the no-token smoke command/test.

### Implementation Details

_To be filled in after completion._

---

## [ ] Task 16: Rerun current-code AssistantBench calibration and replace stale reports

### Acceptance Criteria

- [ ] New calibration artifacts are generated with current manifest budget/environment/scaffold fields.
- [ ] A durable Markdown report under `docs/calibration/` summarizes the current-code calibration.
- [ ] The report includes closed-book versus web-search and answer-only versus tool-loop where budget allows.
- [ ] Raw `runs/` artifacts remain ignored unless explicitly requested.
- [ ] Full test suite passes after docs are updated.

### Detailed Technical Instructions

1. Confirm whether `OPENROUTER_API_KEY` is set before running live calls:
   - `test -n "$OPENROUTER_API_KEY" && echo set || echo missing`
2. If the key is missing, do not run live calibration. Instead, document this task as blocked in `Implementation Details` and ask the user whether to provide a key or skip live calibration.
3. If the key is available, start with one task:
   - `PYTHONPATH= uv run aeb run-assistantbench --model openai/gpt-5.4-nano --limit 1 --mode closed_book --output-dir runs/calibration-current-closed-book`
   - `PYTHONPATH= uv run aeb run-assistantbench --model openai/gpt-5.4-nano --limit 1 --mode openrouter_web_plugin --output-dir runs/calibration-current-web-search`
4. Optionally run tool-loop for the same task if suite/task budget allows:
   - `PYTHONPATH= uv run aeb run-tool-loop --tasks data/tasks/public_efficiency_subset.jsonl --model openai/gpt-5.4-nano --category web_research --limit 1 --output-dir runs/calibration-current-tool-loop --max-completion-tokens 256 --enable-web-search`
5. Inspect manifests, telemetry, results, and traces.
6. Create or update a report, for example:
   - `docs/calibration/assistantbench-current-calibration.md`
7. Include:
   - commands used
   - task ID
   - requested/returned model
   - scaffold
   - tools/server tools
   - success/quality
   - cost/tokens/latency
   - citations/annotations
   - manifest budget/environment/provenance fields
8. Run:
   - `PYTHONPATH= uv run python -m pytest -q`
9. Do not commit raw `runs/` artifacts unless the user explicitly asks.

### Implementation Details

_To be filled in after completion._

---

## [ ] Task 17: Decide and document next benchmark adapters for v0 versus post-v0

### Acceptance Criteria

- [ ] `docs/design.md` clearly labels WorkArena/BrowserGym, MCP-Bench/MCP-Universe, and OSWorld as v0 or post-v0.
- [ ] If any are v0, there is a task section in this file with concrete implementation steps.
- [ ] If they are post-v0, docs explain why they are excluded from v0 completion.
- [ ] README does not imply unsupported adapters are currently available.
- [ ] Existing tests continue to pass.

### Detailed Technical Instructions

1. Inspect `docs/design.md`, especially `## Next adapters to add`.
2. Decide whether each of these belongs in v0:
   - WorkArena / BrowserGym browser enterprise workflows.
   - MCP-Bench or MCP-Universe tool-server workflows.
   - OSWorld desktop/computer-use tasks.
3. Unless the user has explicitly requested them for v0, prefer marking them `post-v0` to keep v0 focused on the four current source categories.
4. Update `docs/design.md` with a small table:
   - adapter
   - status: `v0` or `post-v0`
   - reason
   - prerequisites
5. Update `README.md` if needed so `Public sources currently scaffolded` remains accurate.
6. Run:
   - `PYTHONPATH= uv run python -m pytest -q`

### Implementation Details

_To be filled in after completion._

---

## [ ] Task 18: Final v0 verification checklist

### Acceptance Criteria

- [ ] Full test suite passes.
- [ ] Default dev subset builds successfully.
- [ ] Task audit has no placeholder/template warnings.
- [ ] Catalog matches documented counts.
- [ ] Fake/no-token smoke path passes.
- [ ] At least one evaluated run/report exists for each v0-included category, or docs explicitly mark the category as official-harness-required and not locally scored.
- [ ] `README.md` quick start works as written.
- [ ] `v0-tasks.md` has completed Implementation Details for every finished task.

### Detailed Technical Instructions

1. Run the full unit test suite:
   - `PYTHONPATH= uv run python -m pytest -q`
2. Rebuild default subset:
   - `PYTHONPATH= uv run aeb build-subset --config configs/sources.yaml --output data/tasks/public_efficiency_subset.jsonl`
3. Audit tasks:
   - `PYTHONPATH= uv run aeb audit-tasks data/tasks/public_efficiency_subset.jsonl --output docs/calibration/task-audit.md`
4. Catalog tasks:
   - `PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl`
5. Run the no-token smoke verification created in Task 15.
6. Generate at least one report from available non-secret telemetry artifacts or fake smoke outputs:
   - `PYTHONPATH= uv run aeb report --tasks <tasks.jsonl> --runs <run_telemetry.jsonl> --output <report.md>`
7. Re-read:
   - `README.md`
   - `docs/design.md`
   - `docs/running-benchmarks.md`
   and ensure commands and claims match actual behavior.
8. Update this task's `Implementation Details` with exact command outputs and any remaining known limitations.

### Implementation Details

_To be filled in after completion._
