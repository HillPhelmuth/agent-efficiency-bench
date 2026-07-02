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

## [ ] Task 6: Enforce budgets during execution

### Acceptance Criteria

- [ ] Budget limits stop or mark runs consistently when exceeded.
- [ ] Termination reasons distinguish token, cost, time, tool-call, and LLM-call budget exits.
- [ ] Traces record budget checks and budget-exceeded events.
- [ ] Tests cover budget pass and budget exceeded cases.

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

<provide details when task is completed>

---

## [ ] Task 7: Publish a first baseline calibration report

### Acceptance Criteria

- [ ] A markdown baseline report compares closed-book and web-search calibration runs.
- [ ] Report includes task identity, model, agent, tools, success, quality, cost, latency, tokens, and citations.
- [ ] Report includes observed takeaways and known limitations.
- [ ] Report is saved under `docs/calibration/` or another documented non-ignored path.
- [ ] Raw `runs/` artifacts remain ignored by git unless explicitly requested otherwise.

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

<provide details when task is completed>

---

## [ ] Task 8: Add tau-bench/tau-style tool workflow source adapter

### Acceptance Criteria

- [ ] Add a small deterministic public subset for conversational tool/policy workflows.
- [ ] Normalize tasks into existing `BenchmarkTask` schema.
- [ ] Assign category such as `tool_workflow` or another consistent category.
- [ ] Add source config entry.
- [ ] Add tests for source normalization.
- [ ] `aeb build-subset` and `aeb catalog` include the new source.

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

<provide details when task is completed>

---

## [ ] Task 9: Add scaffold identity and scaffold comparison support

### Acceptance Criteria

- [ ] Run telemetry and manifests clearly distinguish model from scaffold.
- [ ] At least two scaffold modes can be compared in reports.
- [ ] Existing `openrouter-answer` behavior remains unchanged.
- [ ] Tests cover scaffold identity in telemetry, manifest, and reporting.

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

<provide details when task is completed>

---

## [ ] Task 10: Design and implement a minimal multi-step tool-loop agent

### Acceptance Criteria

- [ ] Add a minimal ReAct-style or tool-loop scaffold separate from answer-only mode.
- [ ] Agent records every LLM call and tool/server-tool configuration in traces.
- [ ] Agent respects budget checks from Task 6.
- [ ] Agent produces comparable `RunTelemetry` and `RunResult` artifacts.
- [ ] Tests use a fake provider/tool path and do not spend tokens.

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

<provide details when task is completed>
