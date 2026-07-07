# Agent Efficiency Bench Plan State

This checklist tracks remaining project work from the recommended next steps after enabling OpenRouter web search and adding run manifests/tool trace telemetry.

## Status Legend

- [ ] Not started
- [x] Completed

---

## [x] Task 1: Analyze the two-mode AssistantBench calibration outputs

### Acceptance Criteria

- [x] Compare `runs/calibration-closed-book/run_telemetry.jsonl` and `runs/calibration-web-search/run_telemetry.jsonl` for the same task ID.
- [x] Confirm both runs have matching task IDs and comparable model/scaffold identity.
- [x] Confirm the web-search run trace includes `tools_configured: ["openrouter:web_search"]` on `llm_call_start`.
- [x] Confirm whether OpenRouter returned `annotations` and/or `citations` on `llm_call_end`.
- [x] Document observed differences in tokens, cost, latency, returned answer, and success/quality outcome.
- [x] Capture any telemetry gaps or schema/reporting issues discovered during review.

### Detailed Technical Instructions

1. Read both manifests:
   - `runs/calibration-closed-book/manifest.json`
   - `runs/calibration-web-search/manifest.json`
2. Read both telemetry files:
   - `runs/calibration-closed-book/run_telemetry.jsonl`
   - `runs/calibration-web-search/run_telemetry.jsonl`
3. Read both result files:
   - `runs/calibration-closed-book/run_results.jsonl`
   - `runs/calibration-web-search/run_results.jsonl`
4. Read both task traces under each run directory:
   - `runs/calibration-closed-book/<task_id>/trace.jsonl`
   - `runs/calibration-web-search/<task_id>/trace.jsonl`
5. Create a short comparison table in a new markdown file, suggested path:
   - `docs/calibration/assistantbench-web-search-calibration.md`
6. Include at minimum:
   - task ID
   - mode
   - returned model
   - success
   - quality score
   - wall-clock seconds
   - input tokens
   - output tokens
   - total tokens
   - estimated USD
   - tools configured
   - citations/annotations count
   - answer summary
7. Run verification:
   - `PYTHONPATH= uv run python -m pytest -q`

### Implementation Details

Completed in `docs/calibration/assistantbench-web-search-calibration.md`.

Reviewed both one-task calibration runs for `assistantbench__8ad84bd6fe38481ba49e7ad1f6fbd43219a999074e5c6fc940003281f55ec65b`. Both runs used `openrouter-answer`, requested `openai/gpt-5.4-nano`, returned `openai/gpt-5.4-nano-20260317`, and were generated from git commit `c263e3eabbf1653c4503ce23065d653980b1f5de`. Closed-book correctly recorded no configured tools; web-search correctly recorded `openrouter:web_search` in the manifest and trace `llm_call_start` event.

The web-search trace returned two `url_citation` annotations and two extracted citation URLs. The web-search run increased wall-clock time from `2.213680` seconds to `9.510537` seconds, total tokens from `259` to `18,356`, and estimated cost from `$0.00024255` to `$0.0338095395`. Both runs failed exact-answer evaluation against expected answer `Potash Markets - Clark Street`.

Telemetry gaps captured: manifest `budget` and `environment` are empty; `RunTelemetry.scaffold` is not populated; OpenRouter server-side search is not counted in `num_tool_calls`; exact-match evaluation is too brittle for web-research tasks; grouped reporting is needed for easier cross-run comparison.

---

## [x] Task 2: Fill `RunManifest.budget` and `RunManifest.environment`

### Acceptance Criteria

- [x] `manifest.json` includes non-empty budget information for the executed run suite.
- [x] `manifest.json` includes environment information useful for reproducing runs.
- [x] Existing manifest tests assert budget and environment fields are populated.
- [x] Existing tests continue to pass.

### Detailed Technical Instructions

1. Update `src/agent_efficiency_bench/runner.py` so `BenchmarkRunner` records budget metadata from executed tasks.
   - For a single task, store that task budget directly.
   - For multiple tasks, store either the common budget if all budgets match or a summary containing min/max values per budget field.
2. Add an environment helper in `runner.py` or a small new module such as `src/agent_efficiency_bench/environment.py`.
3. Capture at least:
   - Python version
   - platform string
   - current working directory
   - git commit
   - package runner command if available or `None`
4. Update `RunManifest` tests in `tests/test_execution_schemas.py` if needed.
5. Update `tests/test_runner.py` to assert `budget` and `environment` are non-empty in `manifest.json`.
6. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_runner.py tests/test_execution_schemas.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
7. Update `docs/running-benchmarks.md` to mention the new manifest fields.

### Implementation Details

Implemented in `src/agent_efficiency_bench/runner.py`, `tests/test_runner.py`, `tests/test_execution_schemas.py`, and `docs/running-benchmarks.md`.

`BenchmarkRunner` now accumulates each executed task's budget metadata and writes it into `manifest.json`. When all executed tasks share the same budget, the manifest stores that budget directly. When budgets differ, the manifest writes a summary containing `task_count` and per-field min/max values for numeric budget fields.

The manifest environment now includes `python_version`, `platform`, `cwd`, `git_commit`, and the invoking `command` when available. `RunManifest` tests now cover non-empty budget/environment fields, and runner tests assert the generated manifest contains the default task budget plus environment reproduction fields.

Documentation in `docs/running-benchmarks.md` now states that `manifest.json` includes budget and environment metadata. Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_runner.py tests/test_execution_schemas.py -q` and `PYTHONPATH= uv run python -m pytest -q`; the full suite passed with `36 passed`.

---

## [x] Task 3: Add report grouping by model, scaffold, source, tools, and complexity

### Acceptance Criteria

- [x] Reports can summarize runs by category, source, model, scaffold, tools-enabled flag, and complexity horizon.
- [x] CLI exposes grouping options for report generation.
- [x] Report output clearly distinguishes closed-book and web-search runs.
- [x] Tests cover at least category, model, and tools-enabled grouping.
- [x] Existing report behavior remains backward compatible.

### Detailed Technical Instructions

1. Inspect current report generation in:
   - `src/agent_efficiency_bench/reporting.py`
   - `src/agent_efficiency_bench/cli.py`
   - `tests/test_reporting.py`
2. Add a generic grouping function, for example:
   - `summarize_by_dimensions(tasks, runs, dimensions)`
3. Supported dimensions should include:
   - `category`
   - `source`
   - `model`
   - `agent`
   - `scaffold`
   - `horizon`
   - `requires_external_search`
   - `tools_enabled`
4. Decide how to derive `tools_enabled`:
   - Prefer manifest/tool metadata if available.
   - Fall back to `False` when absent.
5. Extend the CLI command:
   - `aeb report --group-by category,model,tools_enabled ...`
6. Update Markdown output so each group key is human-readable.
7. Add tests in `tests/test_reporting.py` for grouped summaries.
8. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_reporting.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`

### Implementation Details

Implemented in `src/agent_efficiency_bench/reporting.py`, `src/agent_efficiency_bench/cli.py`, `tests/test_reporting.py`, `tests/test_cli.py`, and `docs/running-benchmarks.md`.

Added `summarize_by_dimensions(tasks, runs, dimensions, manifests=None)` with support for `category`, `source`, `model`, `agent`, `scaffold`, `horizon`, `requires_external_search`, and `tools_enabled`. Group keys are rendered as readable strings such as `category=web_research | model=openai/gpt-5.4-nano | tools_enabled=true`. `tools_enabled` uses manifest `tools_configured` metadata when a manifest is provided and falls back to `false` when absent.

The `aeb report` CLI now accepts `--group-by` and optional `--manifest`. The default remains backward-compatible category grouping when no manifest and default `--group-by category` are used. Markdown reports now label the first column as `group` instead of assuming category-only grouping.

Tests cover grouped summaries by category/model/tools-enabled, fallback tools-disabled behavior, and CLI invocation with `--group-by category,model,tools_enabled --manifest <manifest.json>`. Documentation now includes an example grouped report command. Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_reporting.py tests/test_cli.py -q` and full suite `PYTHONPATH= uv run python -m pytest -q`; the full suite passed with `39 passed`.

---

## [x] Task 4: Add a task-audit CLI command

### Acceptance Criteria

- [x] New CLI command audits normalized task JSONL files.
- [x] Audit reports counts by source, category, horizon, interaction type, and success criteria type.
- [x] Audit flags tasks with missing or weak evaluator paths.
- [x] Audit flags placeholder or suspiciously short instructions.
- [x] Tests cover the audit logic.

### Detailed Technical Instructions

1. Create a new module:
   - `src/agent_efficiency_bench/task_audit.py`
2. Add functions to compute:
   - count by source
   - count by category
   - count by `complexity.horizon`
   - count by `complexity.interaction_type`
   - count by `success_criteria.type`
   - count requiring external search
   - count requiring code execution
   - count requiring recovery
3. Add warning detection for:
   - empty instruction after stripping
   - instruction shorter than a configurable threshold
   - `success_criteria.type == "manual"`
   - missing `raw.answer` for structured-answer tasks when relevant
   - terminal tasks with placeholder instruction such as `|-`
4. Add CLI command in `src/agent_efficiency_bench/cli.py`:
   - `aeb audit-tasks data/tasks/public_efficiency_subset.jsonl`
5. Add tests:
   - `tests/test_task_audit.py`
6. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_task_audit.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
7. Document command in `README.md` or `docs/running-benchmarks.md`.

### Implementation Details

Implemented in `src/agent_efficiency_bench/task_audit.py`, `src/agent_efficiency_bench/cli.py`, `tests/test_task_audit.py`, `tests/test_cli.py`, and `docs/running-benchmarks.md`.

Added `audit_tasks(tasks, min_instruction_chars=20)` and `format_audit_markdown(audit)`. The audit reports counts by source, category, complexity horizon, interaction type, and success criteria type. It also reports requirement counts for `requires_external_search`, `requires_code_execution`, and `requires_recovery`.

Added warnings for short instructions, placeholder instructions such as `|-`, manual evaluator usage, and missing `raw.answer` metadata for exact/structured-answer tasks. The new CLI command is `aeb audit-tasks <tasks.jsonl> --output <audit.md>` and writes a markdown audit report when `--output` is provided, or prints markdown to the console otherwise.

Tests cover audit counts, warning generation, markdown formatting, and CLI output writing. Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_task_audit.py tests/test_cli.py -q` and full suite `PYTHONPATH= uv run python -m pytest -q`; the full suite passed with `42 passed`.

---

## [x] Task 5: Build a structured web-research evaluator

### Acceptance Criteria

- [x] Add a deterministic structured evaluator for web-research tasks.
- [x] Evaluator supports exact text fields, numeric tolerances, required domains/URLs, and citation checks.
- [x] Evaluator returns `EvaluationScore` with useful failure reasons and details.
- [x] AssistantBench or custom web tasks can opt into this evaluator via `success_criteria` and/or `raw` metadata.
- [x] Tests cover success, partial failure, numeric tolerance, and missing citation cases.

### Detailed Technical Instructions

1. Inspect current evaluator interfaces:
   - `src/agent_efficiency_bench/evaluators/base.py`
   - `src/agent_efficiency_bench/evaluators/simple.py`
2. Create:
   - `src/agent_efficiency_bench/evaluators/structured.py`
   - `tests/test_structured_evaluator.py`
3. Define an expected-answer shape in `task.raw`, for example:
   ```json
   {
     "expected": {
       "text_contains": ["Paris"],
       "numbers": [{"label": "price", "value": 15.0, "tolerance": 0.01}],
       "required_domains": ["example.com"],
       "requires_citation": true
     }
   }
   ```
4. Implement deterministic checks first; do not add an LLM judge in this task.
5. Return details showing which checks passed/failed.
6. Wire evaluator selection into AssistantBench/custom web task evaluator logic where appropriate.
7. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_structured_evaluator.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`

### Implementation Details

Implemented in `src/agent_efficiency_bench/evaluators/structured.py`, `src/agent_efficiency_bench/harnesses/assistantbench.py`, `tests/test_structured_evaluator.py`, and `tests/test_assistantbench_harness.py`.

Added `StructuredAnswerEvaluator`, a deterministic evaluator for web-research answers. It supports `text_contains`, numeric checks with tolerances, required citation domains/URLs, and `requires_citation`. It returns an `EvaluationScore` with `checks`, `passed_checks`, and `total_checks` details, using partial quality scores when only some checks pass.

Structured evaluator inputs are read from `task.raw["expected"]`, for example `{"text_contains": ["Potash Markets"], "numbers": [{"label": "price", "value": 15.0, "tolerance": 0.25}], "required_domains": ["potashmarkets.com"], "requires_citation": true}`. AssistantBench evaluator selection now prefers this structured metadata when present, then falls back to exact `raw.answer`, then `NoOpEvaluator`.

Tests cover full success, partial text failure, numeric tolerance success, missing citation failure, and AssistantBench dispatch to the structured evaluator. Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_structured_evaluator.py tests/test_assistantbench_harness.py -q` and full suite `PYTHONPATH= uv run python -m pytest -q`; the full suite passed with `47 passed`.

---

## [x] Task 6: Enforce budgets during execution

### Acceptance Criteria

- [x] Budget limits stop or mark runs consistently when exceeded.
- [x] Termination reasons distinguish token, cost, time, tool-call, and LLM-call budget exits.
- [x] Traces record budget checks and budget-exceeded events.
- [x] Tests cover budget pass and budget exceeded cases.

### Detailed Technical Instructions

1. Inspect:
   - `src/agent_efficiency_bench/budget.py`
   - `src/agent_efficiency_bench/agents/openrouter_answer.py`
   - `src/agent_efficiency_bench/runner.py`
2. Add explicit budget check events after each LLM/tool call:
   - `budget_check`
   - `budget_exceeded`
3. For answer-only single-call agents, ensure the run telemetry `terminated_by` is set to the budget reason when exceeded.
4. For future multi-step agents, define an exception or control-flow result for stopping early.
5. Add tests in `tests/test_budget.py` and `tests/test_answer_agent.py`.
6. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_budget.py tests/test_answer_agent.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
7. Update docs to clarify that failed or budget-exceeded runs still count toward aggregate spend.

### Implementation Details

Implemented in `src/agent_efficiency_bench/agents/openrouter_answer.py`, `tests/test_answer_agent.py`, `tests/test_integration_fake_provider.py`, and `docs/running-benchmarks.md`.

The answer-only agent now emits a `budget_check` trace event after the LLM call with token, cost, elapsed-time, LLM-call, and tool-call counters plus configured maxima. When a budget limit is exceeded, it also emits `budget_exceeded` and preserves the specific termination reason such as `budget_tokens` in `RunTelemetry.terminated_by`.

Existing `BudgetTracker.termination_reason()` already distinguishes token, wall-clock time, estimated cost, tool-call, and LLM-call exits. The new tests verify both passing budget checks and budget-exceeded traces for the answer agent. Integration trace expectations were updated to include `budget_check`. Documentation now clarifies that budget-exceeded runs still count toward aggregate cost, tokens, and latency already consumed before detection.

Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_budget.py tests/test_answer_agent.py -q` and full suite `PYTHONPATH= uv run python -m pytest -q`; the full suite passed with `49 passed`.

---

## [x] Task 7: Publish a first baseline calibration report

### Acceptance Criteria

- [x] A markdown baseline report compares closed-book and web-search calibration runs.
- [x] Report includes task identity, model, agent, tools, success, quality, cost, latency, tokens, and citations.
- [x] Report includes observed takeaways and known limitations.
- [x] Report is saved under `docs/calibration/` or another documented non-ignored path.
- [x] Raw `runs/` artifacts remain ignored by git unless explicitly requested otherwise.

### Detailed Technical Instructions

1. Use the outputs from:
   - `runs/calibration-closed-book/`
   - `runs/calibration-web-search/`
2. Create directory:
   - `docs/calibration/`
3. Create report:
   - `docs/calibration/assistantbench-gpt-5.4-nano-calibration.md`
4. Include:
   - commands used
   - git commit from manifests
   - task ID and prompt summary
   - closed-book metrics
   - web-search metrics
   - tool/citation observations
   - whether outputs appear comparable
   - limitations and next recommended experiment
5. Run tests:
   - `PYTHONPATH= uv run python -m pytest -q`
6. Commit only the report and code/doc changes, not `runs/` artifacts.

### Implementation Details

Implemented in `docs/calibration/assistantbench-gpt-5.4-nano-calibration.md`.

Published a durable baseline report comparing the one-task closed-book and OpenRouter-native-web-search AssistantBench calibration runs. The report records the commands used, raw artifact locations, run suite IDs, git commit, task ID, expected answer, agent, requested/returned model, configured tools, success/quality outcomes, latency, token usage, estimated cost, and citation metadata.

The report captures the main finding: web search was configured and cited sources correctly, but for this task it increased total tokens from `259` to `18,356` and estimated cost from `$0.00024255` to `$0.0338095395` while still failing the exact-answer check. Known limitations include brittle exact-match evaluation, missing scaffold identity, and the fact that this is a one-task calibration rather than a stable model ranking.

Raw `runs/` artifacts remain gitignored. Verification completed with `PYTHONPATH= uv run python -m pytest -q`; the full suite passed with `49 passed`.

---

## [x] Task 8: Add tau-bench/tau-style tool workflow source adapter

### Acceptance Criteria

- [x] Add a small deterministic public subset for conversational tool/policy workflows.
- [x] Normalize tasks into existing `BenchmarkTask` schema.
- [x] Assign category such as `tool_workflow` or another consistent category.
- [x] Add source config entry.
- [x] Add tests for source normalization.
- [x] `aeb build-subset` and `aeb catalog` include the new source.

### Detailed Technical Instructions

1. Research the exact public dataset/source path and licensing before implementation.
2. Update:
   - `configs/sources.yaml`
   - `src/agent_efficiency_bench/sources.py` or a new source adapter module
   - tests for source loading/normalization
3. Normalize each selected row with:
   - stable task ID
   - source URL
   - user-facing instruction
   - environment/tool metadata
   - complexity labels
   - success criteria
4. Use deterministic SHA-256 ordering for sampling, matching the current subset strategy.
5. Run:
   - `PYTHONPATH= uv run python -m pytest -q`
   - `PYTHONPATH= uv run aeb build-subset --config configs/sources.yaml --output data/tasks/public_efficiency_subset.jsonl`
   - `PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl`
6. Document the new source in `README.md` and `docs/design.md`.

### Implementation Details

Implemented in `src/agent_efficiency_bench/sources.py`, `configs/sources.yaml`, `tests/test_normalizers.py`, `tests/test_tau2_source.py`, `README.md`, `docs/design.md`, and regenerated `data/tasks/public_efficiency_subset.jsonl`.

Research found that the original `sierra-research/tau-bench` repository is MIT licensed but its README marks the tasks as outdated and recommends `sierra-research/tau2-bench` / τ³-bench instead. The adapter therefore uses the newer MIT-licensed `sierra-research/tau2-bench` JSON task sources under `data/tau2/domains/<domain>/tasks.json`.

Added `normalize_tau2_bench(row, domain)` and `load_tau2_bench_github_subset(spec)`. The normalizer maps tau2 rows into `BenchmarkTask` with stable task IDs like `tau2_bench_retail__55`, source `sierra-research/tau2-bench`, category `tool_workflow`, domain `retail` or `airline`, environment metadata `{type: simulated_user_tools, source_repo: sierra-research/tau2-bench, license: MIT}`, complexity labels for simulated user/tool workflows, and `tau2_actions` success criteria checked by a future `tau2_harness`.

Updated `configs/sources.yaml` with two deterministic 4-task entries: `tau2_bench_retail` and `tau2_bench_airline`. Rebuilt the public subset; `aeb build-subset` wrote 32 tasks and `aeb catalog` now reports 8 tasks each for `software_engineering`, `web_research`, `terminal_work`, and `tool_workflow`, including source `sierra-research/tau2-bench` with count 8.

Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_tau2_source.py tests/test_normalizers.py -q`, `PYTHONPATH= uv run python -m pytest -q`, and `PYTHONPATH= uv run aeb build-subset --config configs/sources.yaml --output data/tasks/public_efficiency_subset.jsonl && PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl`; the full suite passed with `51 passed`.

---

## [x] Task 9: Add scaffold identity and scaffold comparison support

### Acceptance Criteria

- [x] Run telemetry and manifests clearly distinguish model from scaffold.
- [x] At least two scaffold modes can be compared in reports.
- [x] Existing `openrouter-answer` behavior remains unchanged.
- [x] Tests cover scaffold identity in telemetry, manifest, and reporting.

### Detailed Technical Instructions

1. Define scaffold naming conventions:
   - `answer-only`
   - `web-search-answer`
   - future `react-tool-loop`
   - future `planner-executor`
2. Update `OpenRouterAnswerAgent` or config plumbing to set `scaffold` on `RunTelemetry`.
3. Update `RunManifest` to include scaffold consistently.
4. Update report grouping to support scaffold if not already implemented in Task 3.
5. Add tests in:
   - `tests/test_answer_agent.py`
   - `tests/test_runner.py`
   - `tests/test_reporting.py`
6. Run:
   - `PYTHONPATH= uv run python -m pytest -q`

### Implementation Details

Implemented in `src/agent_efficiency_bench/agents/openrouter_answer.py`, `src/agent_efficiency_bench/runner.py`, `tests/test_answer_agent.py`, `tests/test_runner.py`, `tests/test_reporting.py`, and `docs/running-benchmarks.md`.

`OpenRouterAnswerAgent` now sets a scaffold identity independent of the model name: `answer-only` for the plain answer baseline and `web-search-answer` when the OpenRouter native `openrouter:web_search` server tool is configured. The scaffold value is written into `RunTelemetry.scaffold` for every answer-agent run.

`BenchmarkRunner` now writes `scaffold` into `manifest.json`, so run identity includes agent, model, scaffold, and configured tools. Reporting already supported `scaffold` grouping from Task 3; a regression test now verifies `summarize_by_dimensions(..., ["scaffold"])` groups by scaffold value.

Tests cover default answer-only telemetry, web-search scaffold telemetry, manifest scaffold serialization, and reporting group-by-scaffold behavior. Documentation now notes that manifests include scaffold metadata. Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_answer_agent.py tests/test_runner.py tests/test_reporting.py -q` and full suite `PYTHONPATH= uv run python -m pytest -q`; the full suite passed with `53 passed`.

---

## [x] Task 10: Design and implement a minimal multi-step tool-loop agent

### Acceptance Criteria

- [x] Add a minimal ReAct-style or tool-loop scaffold separate from answer-only mode.
- [x] Agent records every LLM call and tool/server-tool configuration in traces.
- [x] Agent respects budget checks from Task 6.
- [x] Agent produces comparable `RunTelemetry` and `RunResult` artifacts.
- [x] Tests use a fake provider/tool path and do not spend tokens.

### Detailed Technical Instructions

1. Create a new agent module, suggested path:
   - `src/agent_efficiency_bench/agents/openrouter_tool_loop.py`
2. Keep v1 narrow:
   - one or more LLM calls
   - server web-search tool config support
   - no local browser automation yet
3. Add tests:
   - `tests/test_tool_loop_agent.py`
4. Ensure traces include:
   - `llm_call_start`
   - `llm_call_end`
   - `budget_check`
   - `task_end`
5. Add CLI entry only after fake-provider tests pass.
6. Run:
   - `PYTHONPATH= uv run python -m pytest tests/test_tool_loop_agent.py -q`
   - `PYTHONPATH= uv run python -m pytest -q`
7. Document when to use answer-only vs tool-loop scaffold.

### Implementation Details

Implemented in `src/agent_efficiency_bench/agents/openrouter_tool_loop.py`, `src/agent_efficiency_bench/cli.py`, `tests/test_tool_loop_agent.py`, `tests/test_cli.py`, `README.md`, `docs/running-benchmarks.md`, and `plan-state.md`.

Added `OpenRouterToolLoopAgent`, a minimal two-step scaffold with scaffold identity `react-tool-loop`. The agent makes a research LLM call first, optionally passing configured OpenRouter server tools such as `openrouter:web_search`, emits `llm_call_start`, `llm_call_end`, and `budget_check`, and stops early with `budget_exceeded` if the research call exceeds task budgets. If budget remains, it makes a second final synthesis LLM call without tools, records the same trace events, and returns a comparable `RunResult` with `output.answer`, `output.research`, `RunTelemetry`, trace path, and artifact directory.

Added CLI command `run-tool-loop` with the same task/model/category/limit/output/max-token shape as `run-answer`, plus `--enable-web-search` for the research step. Documentation now explains when to use answer-only versus the tool-loop scaffold: answer-only is the cheapest single-call baseline, while tool-loop is for measuring scaffold overhead and research/synthesis quality gains.

Tests use fake provider responses only: one test verifies the two-call research/final flow, token/cost aggregation, scaffold identity, tool passing only on the research call, and exact trace event sequence; another verifies early budget termination after the research step. CLI registration is also tested. Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_tool_loop_agent.py -q`, `PYTHONPATH= uv run python -m pytest tests/test_tool_loop_agent.py tests/test_cli.py -q`, and full suite `PYTHONPATH= uv run python -m pytest -q`; the full suite passed with `56 passed`.

---

## [x] Task 11: Convert CLI-first benchmark workflow into REST API with charting web UI

### Acceptance Criteria

- [x] Add a REST API that exposes task catalog metadata, benchmark option discovery, benchmark run creation, run status, run listings, and chart-ready result summaries.
- [x] Support requesting combinations of models, scaffolds, categories, web-search modes, trials, and suite budgets from one request.
- [x] Execute requested combinations through the existing benchmark runner without duplicating runner logic.
- [x] Add a browser UI for selecting combinations, launching runs, polling status, and viewing easy-to-read charts/tables.
- [x] Keep tests token-free by monkeypatching runner execution and reading fixture telemetry.
- [x] Document how to launch the REST API/web UI.

### Detailed Technical Instructions

1. Inspect current CLI paths in `src/agent_efficiency_bench/cli.py`, runner behavior in `src/agent_efficiency_bench/runner.py`, and reporting helpers in `src/agent_efficiency_bench/reporting.py`.
2. Add FastAPI/uvicorn dependencies and expose an app factory in `src/agent_efficiency_bench/api.py`.
3. Add API schemas for benchmark requests, expanded run combinations, job status, catalog summaries, and chart summary rows.
4. Implement a small in-memory job registry that runs combinations in a background thread and writes normal `runs/<job-id>/<combination>/` artifacts.
5. Reuse `OpenRouterAnswerAgent`, `OpenRouterToolLoopAgent`, `BenchmarkRunner`, `RegistryEvaluator`, and existing reporting helpers.
6. Add static web UI assets under `src/agent_efficiency_bench/web/` served from the API root.
7. Add tests in `tests/test_api.py` covering catalog/options, dry-run combination expansion, monkeypatched run execution, status/results, and HTML UI serving.
8. Add `aeb serve` and an `aeb-api` script entry point.
9. Run targeted API tests, CLI smoke tests, and the full suite.

### Implementation Details

Implemented in `src/agent_efficiency_bench/api.py`, `src/agent_efficiency_bench/web/index.html`, `src/agent_efficiency_bench/web/app.js`, `src/agent_efficiency_bench/web/styles.css`, `src/agent_efficiency_bench/cli.py`, `pyproject.toml`, `tests/test_api.py`, `tests/test_cli.py`, and `README.md`.

Added a FastAPI application with REST endpoints for `GET /api/options`, `GET /api/catalog`, `POST /api/runs`, `GET /api/runs`, `GET /api/runs/{job_id}`, and `GET /api/runs/{job_id}/results`. `POST /api/runs` expands all requested model/scaffold/category/web-search combinations, supports dry-run previews, and uses a small in-memory job registry for background execution. Real execution reuses `OpenRouterAnswerAgent`, `OpenRouterToolLoopAgent`, `BenchmarkRunner`, `RegistryEvaluator`, `SuiteBudgetConfig`, and existing JSONL/reporting helpers rather than duplicating CLI execution logic.

Added chart-ready summaries through `chart_summary_for_runs()` / `chart_summary_for_telemetry()`, returning both the full grouped reporting summary and compact chart rows for success rate, quality, cost, p50 latency, token totals, and cost per success. Added a static browser dashboard served at `/` with controls for tasks path, output root, models, categories, scaffolds, web-search modes, limits, trials, token cap, dry-run mode, and chart grouping. The UI polls job status and renders Chart.js charts plus a summary table.

Added `aeb serve` and `aeb-api` entry points. `README.md` now documents launching the API/dashboard and the core REST endpoints. Tests cover metadata/catalog endpoints, dry-run combination expansion, monkeypatched token-free execution/status/results, chart summaries from existing telemetry files, root UI serving, and CLI command registration.

Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_api.py tests/test_cli.py -q` (`20 passed`), `PYTHONPATH= uv run aeb serve --help`, full suite `PYTHONPATH= uv run python -m pytest -q` (`113 passed`), and a live uvicorn smoke test on `127.0.0.1:8765` that returned HTTP 200 for `/`, `/api/options`, `/api/catalog?tasks_path=data/tasks/public_efficiency_subset.jsonl`, and a dry-run `POST /api/runs` expanding to 8 combinations.

---

## [x] Task 12: Fix structured evaluation citation propagation

### Acceptance Criteria

- [x] Provider citations and annotations returned by OpenRouter are available to structured evaluators.
- [x] Answer-only and tool-loop run outputs expose citation metadata consistently with telemetry counts.
- [x] A regression test proves a correct AssistantBench answer with a provider citation evaluates successfully.
- [x] The full test suite passes.

### Detailed Technical Instructions

1. Reproduce a correct AssistantBench structured answer with provider `url_citation` annotations failing citation checks.
2. Inspect citation extraction in `OpenRouterAnswerAgent`, `OpenRouterToolLoopAgent`, and `StructuredAnswerEvaluator`.
3. Propagate extracted `annotations` and `citations` into each `RunResult.output`, not just traces and telemetry counters.
4. Add tests covering output citation fields and structured evaluator visibility.
5. Run targeted tests and the full suite.

### Implementation Details

Implemented in `src/agent_efficiency_bench/agents/openrouter_answer.py`, `src/agent_efficiency_bench/agents/openrouter_tool_loop.py`, `tests/test_answer_agent.py`, `tests/test_tool_loop_agent.py`, and `src/agent_efficiency_bench/web/index.html`.

Root cause: OpenRouter response citations were extracted for trace events and telemetry counters but were not copied into `RunResult.output`. `StructuredAnswerEvaluator` reads citations from `result.output`, so AssistantBench tasks with `requires_citation: true` failed citation checks even when the provider returned valid `url_citation` annotations. This could make model results look like universal 0% success for citation-gated web-research benchmarks.

Both answer-only and tool-loop agents now include `annotations` and `citations` in `RunResult.output`. The tool-loop agent accumulates citations from research and final calls while avoiding duplicate citation URLs. Added a regression test that runs an AssistantBench-shaped task through `BenchmarkRunner` with a fake provider response containing the correct answer plus a provider citation and verifies `success=True`, `quality_score=1.0`, and the citation check passing.

Verification completed with the red/green repro command, targeted tests `PYTHONPATH= uv run python -m pytest tests/test_answer_agent.py tests/test_tool_loop_agent.py tests/test_structured_evaluator.py tests/test_assistantbench_harness.py -q` (`18 passed`), and full suite `PYTHONPATH= uv run python -m pytest -q` (`114 passed`, one FastAPI/httpx deprecation warning).

---

## [x] Task 13: Handle non-JSON OpenRouter API responses clearly

### Acceptance Criteria

- [x] OpenRouter client no longer surfaces raw `requests.exceptions.JSONDecodeError` when the API returns non-JSON content.
- [x] Error messages include enough response context to diagnose upstream HTML/text responses without dumping huge bodies.
- [x] OpenRouter requests explicitly ask for JSON responses.
- [x] Regression tests cover non-JSON chat-completion responses.
- [x] The full test suite passes.

### Detailed Technical Instructions

1. Inspect `src/agent_efficiency_bench/providers/openrouter.py` at the `response.json()` call from the API traceback.
2. Add a small JSON parsing helper that catches decode failures after `raise_for_status()`.
3. Send an `Accept: application/json` request header.
4. Include status code, content type, and a truncated normalized body preview in the raised error.
5. Reuse the helper for both chat completions and generation stats.
6. Add a fake-session regression test for a 200 `text/html` response.
7. Run targeted and full tests.

### Implementation Details

Implemented in `src/agent_efficiency_bench/providers/openrouter.py` and `tests/test_openrouter_client.py`.

Root cause: OpenRouter returned an HTTP-success response body that was not JSON, so `requests.Response.json()` raised a raw `JSONDecodeError`. In API background jobs this became a long traceback pointing at JSON internals rather than the upstream response shape.

Added `Accept: application/json` to OpenRouter requests, plus `OpenRouterResponseError` and `_json_payload(response, context=...)`. The helper catches non-JSON responses and raises a concise diagnostic such as `OpenRouter chat completion returned non-JSON response (status=200, content_type='text/html', body_preview='...')`. It also guards against top-level JSON arrays/strings where an object is required. Both `chat()` and `generation_stats()` now use this helper.

Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_openrouter_client.py -q` (`3 passed`), `PYTHONPATH= uv run python -m pytest tests/test_api.py tests/test_openrouter_client.py -q` (`8 passed`), and full suite `PYTHONPATH= uv run python -m pytest -q` (`115 passed`, one FastAPI/httpx deprecation warning).

---

## [x] Task 14: Fix web-research evaluation false negatives in API results

### Acceptance Criteria

- [x] Review actual `runs/api` artifacts to identify why web-research tasks report 100% failure.
- [x] Structured citation checks accept explicit source URLs in the answer text, not only provider-native citation arrays.
- [x] Multiline expected answers are evaluated as required answer parts rather than one brittle exact newline substring.
- [x] API chart summaries can re-evaluate existing `run_results.jsonl` artifacts with the current evaluator instead of trusting stale telemetry-only success flags.
- [x] Regression tests cover the evaluator and API summary behavior.
- [x] The full test suite passes.

### Detailed Technical Instructions

1. Parse all `runs/api/**/run_results.jsonl` files and compare answer text, expected metadata, citations, and evaluation details.
2. Confirm whether any failed web-research rows contain the expected answer plus source URLs.
3. Update `StructuredAnswerEvaluator` so `requires_citation` can be satisfied by URLs embedded in the answer text after URL cleanup.
4. Update text containment checks for newline-delimited expected answers such as `CrossFit East River\nAvea Pilates`.
5. Update API summary generation so existing run artifact summaries use `run_results.jsonl` when available and re-run the current evaluator.
6. Add regression tests for answer-URL citations, multiline expected answers, and API re-evaluation of stale run telemetry.
7. Run targeted and full tests.

### Implementation Details

Implemented in `src/agent_efficiency_bench/evaluators/structured.py`, `src/agent_efficiency_bench/api.py`, `tests/test_structured_evaluator.py`, and `tests/test_api.py`.

Actual `runs/api` review found 23 web-research result rows, all marked failed. Six rows for `assistantbench__291b53e665b4dd4365cde995042db4a6f6fecef3fe3a6f4482f23d61bd673918` contained the exact expected Ensembl GFF3 URL in the answer but had `requires_citation` failing because the evaluator only looked at `output.citations` / `output.annotations`, not URLs embedded in the model's answer. Several other rows had correct source links but wrong final answers, so they now receive partial citation credit rather than a total false-negative citation failure.

`StructuredAnswerEvaluator` now extracts and cleans `http(s)` URLs from answer text and treats them as citations for both `requires_citation` and required-domain checks. It also splits newline-delimited expected text into required parts, avoiding false negatives when a model returns expected multi-answer items in a different order or with bullets instead of the original newline formatting.

`chart_summary_for_runs()` now prefers sibling `run_results.jsonl` files when available, re-evaluates each `RunResult` against the current task metadata, and summarizes the updated telemetry. This lets the API/dashboard reflect evaluator fixes for existing `runs/api` artifacts instead of staying pinned to stale success flags in `run_telemetry.jsonl`. Re-evaluating the current `runs/api` web-research artifacts now shows non-zero success: `minimax/minimax-m3-20260531` at `3/12` successes (`25%`) and `openai/gpt-5.4-nano-20260317` at `3/11` successes (`27.27%`).

Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_structured_evaluator.py tests/test_api.py -q` (`12 passed`), direct re-evaluation of `runs/api` artifacts via `chart_summary_for_runs()`, and full suite `PYTHONPATH= uv run python -m pytest -q` (`118 passed`, one FastAPI/httpx deprecation warning).

---

## [x] Task 15: Fix dashboard task-count semantics and replace AssistantBench stale string matching

### Acceptance Criteria

- [x] Entering `n` in the dashboard's former `Trials` field no longer repeats the first selected task `n` times.
- [x] API requests from the legacy dashboard payload are normalized to run the first `n` tasks with one trial each.
- [x] The dashboard no longer exposes a misleading visible `Trials` field.
- [x] AssistantBench evaluation no longer relies on the two-year-old `expected.text_contains` string values from `AssistantBench/AssistantBench`.
- [x] AssistantBench web-research tasks use a cheap OpenRouter LLM judge that evaluates answer correctness semantically instead of exact substring matching.
- [x] Dashboard summaries reuse stored LLM-judge evaluations instead of re-judging already judged runs on every refresh.
- [x] Regression tests cover legacy trials normalization, stale expected metadata, and LLM judge behavior.
- [x] The full test suite passes.

### Detailed Technical Instructions

1. Trace the dashboard payload from `src/agent_efficiency_bench/web/index.html` / `app.js` through `RunRequest`, `expand_run_request()`, `execute_benchmark_combination()`, and `BenchmarkRunner.run_tasks()`.
2. Add a regression proving old UI-shaped payloads with `limit=1, n_trials=n` become `limit=n, n_trials=1`.
3. Remove the visible dashboard `Trials` input and present the existing limit as `Tasks per combination`.
4. Add a cheap LLM judge evaluator for AssistantBench answers that receives the task instruction, submitted answer, and citations, and does not consume stale expected strings as ground truth.
5. Route `AssistantBench/AssistantBench` tasks through the LLM judge evaluator.
6. Keep deterministic `StructuredAnswerEvaluator` behavior for non-AssistantBench/custom structured tasks.
7. Run targeted tests and the full suite.

### Implementation Details

Implemented in `src/agent_efficiency_bench/api.py`, `src/agent_efficiency_bench/web/index.html`, `src/agent_efficiency_bench/evaluators/llm_judge.py`, `src/agent_efficiency_bench/harnesses/assistantbench.py`, and related tests.

Root cause for repeated tasks: the dashboard had both `limit` defaulting to `1` and a visible `n_trials` field labeled `Trials`. The backend passed `n_trials` straight to `BenchmarkRunner.run_tasks()`, whose documented behavior is to repeat each selected task. With the dashboard default `limit=1`, entering `n` in `Trials` therefore ran task 1 exactly `n` times. The API now normalizes legacy UI requests: if `n_trials > 1`, it is treated as the intended task count for API/dashboard runs, producing `limit=n` and `n_trials=1`. The visible UI field is now `Tasks per combination`; `n_trials` remains hidden at `1` for wire compatibility.

Root cause for AssistantBench false confidence: the public AssistantBench files are stale, and exact `text_contains` expected strings like `Potash Markets - Clark Street` can now be factually wrong. AssistantBench is now evaluated by `LLMAnswerJudgeEvaluator`, which sends the task instruction, submitted answer, and citations to a cheap OpenRouter judge model (`AEB_LLM_JUDGE_MODEL`, default `openai/gpt-4.1-nano`). The judge prompt explicitly prefers current cited evidence over stale benchmark answer keys and returns JSON with `success`, `quality_score`, and `reason`. If citations are required and absent, evaluation fails before calling the judge. If `OPENROUTER_API_KEY` is unavailable, the score is marked unevaluated rather than falling back to stale deterministic strings. API summary re-evaluation also preserves stored LLM-judge evaluations so refreshing the dashboard does not repeatedly spend judge calls for already judged runs.

Existing deterministic structured evaluation remains available for custom/non-AssistantBench structured tasks, including numeric checks, required domains, and exact citation extraction. Tests that specifically validate provider citation propagation were moved to a custom structured source so they continue testing that deterministic path without reintroducing stale AssistantBench string matching.

Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_api.py::test_api_treats_legacy_trials_field_as_task_count_for_ui_requests tests/test_llm_judge_evaluator.py tests/test_assistantbench_harness.py -q` (`7 passed`), `PYTHONPATH= uv run python -m pytest tests/test_api.py::test_api_chart_summary_does_not_rejudge_stored_llm_evaluations -q` (`1 passed`), and full suite `PYTHONPATH= uv run python -m pytest -q` (`121 passed`, one FastAPI/httpx deprecation warning).

---

## [x] Task 16: Create the tau2-bench agent and evaluator harnesses

### Acceptance Criteria

- [x] tau2 normalized task ids map to upstream tau2 domain/task ids.
- [x] The tau2 harness builds an official `tau2 run` command for the agent and user simulator.
- [x] The dry-run path validates whether the `tau2` CLI is installed and prints the planned command without executing it.
- [x] The execute path remains guarded behind `--execute` and can parse tau2 `results.json` reward metadata when available.
- [x] The evaluator path converts official tau2 reward/action metadata into common AEB `harness_result` fields.
- [x] CLI options expose agent, user, user model, trial, step, seed, save, and result parsing controls.
- [x] Regression tests and the full suite pass.

### Detailed Technical Instructions

1. Inspect the existing partial tau2 adapter in `src/agent_efficiency_bench/harnesses/tau2_bench.py` and its tests.
2. Confirm the current upstream tau2 command surface from the tau2-bench docs.
3. Replace the placeholder runner-module command with a guarded `tau2 run` command builder.
4. Keep dry-run behavior safe and non-spending.
5. Extend result parsing so tau2 monolithic `results.json` simulation reward metadata can be converted to AEB quality/success metadata.
6. Expose the relevant command options through `aeb run-tau2-official`.
7. Update README/running docs and verify targeted plus full tests.

### Implementation Details

Implemented in `src/agent_efficiency_bench/harnesses/tau2_bench.py`, `src/agent_efficiency_bench/cli.py`, `tests/test_tau2_bench_harness.py`, `tests/test_cli.py`, `README.md`, and `docs/running-benchmarks.md`.

The tau2 adapter now builds official upstream CLI invocations with `tau2 run --domain <domain> --agent <agent> --user <user> --agent-llm <model> --user-llm <model> --task-ids <id> --num-trials <n> --save-to <name>`. It accepts optional agent/user LLM args, max steps/errors/concurrency, seed, task split/set, verbose logs, and auto-resume controls. Dry runs check for the `tau2` CLI and return the full planned command; execution is still guarded by `--execute`.

The evaluator harness now parses both the legacy flat test shape and official tau2 monolithic `results.json` files. For official results it selects the requested simulation, reads `reward_info.reward` for success and Likert quality conversion, extracts partial action counts from `partial_action_reward`, and preserves reward breakdown, cost, duration, termination reason, and harness identity in `details` so `OfficialHarnessResultEvaluator` can score tau2 tasks from attached harness metadata.

The CLI `run-tau2-official` now exposes agent/user/user-model/trial/step/seed/save/result-path options instead of requiring a placeholder runner module. Documentation now states that tau2 execution uses the upstream `tau2 run` command and may spend real model tokens through both the agent LLM and user simulator.

Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_tau2_bench_harness.py tests/test_cli.py tests/test_evaluators.py -q` (`32 passed`), full suite `PYTHONPATH= uv run python -m pytest -q` (`124 passed`, one FastAPI/httpx deprecation warning), and a dry-run smoke command `PYTHONPATH= uv run aeb run-tau2-official --task-id tau2_bench_retail__55 --model openai/gpt-5.4-nano --output-dir runs/tau2-official-smoke`, which printed a `tau2 run` command and `ready: false` because the `tau2` CLI is not installed in this environment.

---

## [x] Task 17: Wire tau2-official harness runs into the Web interface

### Acceptance Criteria

- [x] `/api/options` advertises `tau2-official` as a scaffold.
- [x] The dashboard can submit a `tau2-official` run request with `tool_workflow` category.
- [x] The API passes tau2 agent/user/user-model/trial/step/seed options through to the official tau2 harness adapter.
- [x] Successful tau2 harness results write `run_results.jsonl` and `run_telemetry.jsonl` so the dashboard results endpoint can render charts/tables.
- [x] The UI exposes tau2-specific options and warns that execution requires the `tau2` CLI and may spend tokens.
- [x] Regression tests and browser/API smoke checks pass.

### Detailed Technical Instructions

1. Trace dashboard request payloads through `src/agent_efficiency_bench/web/app.js`, `RunRequest`, `expand_run_request()`, and `execute_benchmark_combination()`.
2. Add `tau2-official` as a supported scaffold without changing the existing answer-only/tool-loop paths.
3. Add API request/combination fields for tau2-specific agent/evaluator options.
4. When a tau2-official combination executes, select normalized tau2 tasks, call `run_tau2_task(...)`, attach parsed output as `harness_result`, evaluate via `RegistryEvaluator`, and persist standard run result/telemetry JSONL files.
5. Add dashboard controls for tau2 agent/user options and include them in the JSON payload only when the tau2 scaffold is selected.
6. Verify through API tests, full tests, and a live dashboard/API dry-run smoke.

### Implementation Details

Implemented in `src/agent_efficiency_bench/api.py`, `src/agent_efficiency_bench/web/index.html`, `src/agent_efficiency_bench/web/app.js`, `src/agent_efficiency_bench/web/styles.css`, `tests/test_api.py`, and `README.md`.

The API now accepts `tau2-official` in scaffold combinations and routes those combinations to a new `execute_tau2_official_combination(...)` path. That path filters for normalized tau2 tasks, runs the guarded tau2 harness adapter, stores parsed tau2 reward metadata as `output.harness_result`, evaluates it through the existing official-harness evaluator, writes a simple trace, and persists `run_results.jsonl` plus `run_telemetry.jsonl` for dashboard summaries.

The dashboard now includes a `tau2-official` scaffold checkbox and a collapsible tau2 options panel for `tau2_agent`, `tau2_user`, `tau2_user_model`, `tau2_num_trials`, `tau2_max_steps`, and `tau2_seed`. The request payload includes these fields only when `tau2-official` is selected. The options sidebar now lists `tau2-official` because `/api/options` advertises it.

Verification completed with `PYTHONPATH= uv run python -m pytest tests/test_api.py tests/test_cli.py tests/test_tau2_bench_harness.py -q` (`34 passed`, one FastAPI/httpx warning), full suite `PYTHONPATH= uv run python -m pytest -q` (`126 passed`, one FastAPI/httpx warning), a live browser dry-run submission for category `tool_workflow` + scaffold `tau2-official`, and a direct API dry-run smoke against `POST /api/runs` that returned a `tau2-official` combination carrying the requested tau2 user model/trial/step options.

Follow-up: the tau2 subprocess environment now force-overrides Windows-unfriendly parent values (`PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, `NO_COLOR=1`, `TERM=dumb`, and related flags) instead of using `setdefault`, because a parent shell/API server can otherwise preserve `cp1252` output settings and let Rich/colorama crash on Unicode glyphs like `→`. The trace payload also records safe `subprocess_env_overrides` values so future Web runs can confirm the child process received the UTF-8/no-color configuration.

Follow-up: tau2 writes CLI results to its own `DATA_DIR/simulations/<save-to>/results.json`, not to AEB's requested artifact directory. The harness now resolves that upstream location from `TAU2_DATA_DIR`, tau2 stderr, or the tau2 executable checkout, copies the resolved `results.json` back into the AEB artifact directory, and parses all trials for the requested task. Parsed tau2 metadata now includes mean reward, pass rate, simulation count, aggregate action counts, aggregate cost, and aggregate duration so the Web dashboard no longer treats successful tau2 CLI exits as unparsed failures.
