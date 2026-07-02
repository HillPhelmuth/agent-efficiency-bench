# OpenRouter Execution Harness Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build benchmark execution harnesses that run normalized agentic-efficiency tasks through OpenRouter-backed agents and collect accurate, auditable telemetry for tokens, cost, latency, tool calls, errors, retries, and success.

**Architecture:** Add a layered execution stack: OpenRouter provider client → trace recorder → agent loop → environment harnesses → evaluator → run summary. The first execution release should support three task families already present in `data/tasks/public_efficiency_subset.jsonl`: web research (`AssistantBench`), terminal/container work (`Terminal-Bench` metadata), and software engineering (`SWE-bench Lite` metadata). OpenRouter’s `/api/v1/chat/completions` response `usage` and optional `/api/v1/generation?id=...` audit endpoint are the source of truth for token/cost accounting.

**Tech Stack:** Python 3.11+, Typer CLI, Pydantic, Requests/httpx, pytest, JSONL traces, OpenRouter Chat Completions API, optional Docker/official benchmark harnesses for full Terminal-Bench and SWE-bench execution.

---

## Current repo context

Repository path:

```text
C:\Users\adamh\source\repos\agent-efficiency-bench
```

Current package files:

```text
src/agent_efficiency_bench/schemas.py
src/agent_efficiency_bench/metrics.py
src/agent_efficiency_bench/sources.py
src/agent_efficiency_bench/cli.py
src/agent_efficiency_bench/io.py
```

Current normalized subset:

```text
data/tasks/public_efficiency_subset.jsonl
```

Current tests:

```text
tests/test_schemas.py
tests/test_metrics.py
tests/test_normalizers.py
```

Important environment note: because this Hermes shell injects its own `PYTHONPATH`, run tests and CLI with:

```bash
PYTHONPATH= uv run python -m pytest -q
PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl
```

---

## Non-goals for the first execution release

- Do not build a polished leaderboard UI yet.
- Do not support every public benchmark in v1.
- Do not rely on local tokenizer estimates for cost accounting when OpenRouter usage/generation stats are available.
- Do not make failing runs look efficient; failed runs must still count toward aggregate spend and latency.
- Do not vendor large benchmark repositories or Docker images into this repo.

---

## Required environment variables

```bash
export OPENROUTER_API_KEY="..."
export OPENROUTER_APP_TITLE="Agent Efficiency Bench"          # optional but recommended
export OPENROUTER_HTTP_REFERER="https://github.com/local/aeb" # optional attribution
```

The code should fail fast with a helpful error if `OPENROUTER_API_KEY` is missing for commands that actually call models.

---

## Data contracts to add

### `ModelConfig`

Add to `src/agent_efficiency_bench/schemas.py`:

```python
class ModelConfig(BaseModel):
    provider: Literal["openrouter"] = "openrouter"
    model: str
    temperature: float = 0.0
    max_completion_tokens: int = 2048
    seed: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
```

### `TraceEvent`

```python
class TraceEvent(BaseModel):
    t_rel_seconds: float
    event: str
    task_id: str | None = None
    run_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
```

### `RunResult`

```python
class RunResult(BaseModel):
    telemetry: RunTelemetry
    output: dict[str, Any] = Field(default_factory=dict)
    trace_path: str
    artifact_dir: str | None = None
```

Extend `RunTelemetry` later only if needed. Prefer keeping raw request/response details in the trace and final answer/artifacts in `RunResult.output`.

---

## Accuracy rules for telemetry

1. **Wall-clock latency:** measured locally with `time.perf_counter()` around the full task attempt.
2. **LLM latency:** measured around each OpenRouter HTTP call.
3. **Tool latency:** measured around each environment/tool call.
4. **Input/output tokens:** use OpenRouter response `usage.prompt_tokens` and `usage.completion_tokens` for non-streaming calls.
5. **Cost:** use OpenRouter response `usage.cost` when present; otherwise query `/api/v1/generation?id=<completion_id>` and use the generation stats. Do not silently estimate unless both are unavailable; if estimating, mark `cost_source="estimated"` in the trace.
6. **Retries:** count both OpenRouter HTTP retries and agent-level retries separately in trace data; aggregate into `num_retries` for `RunTelemetry`.
7. **Errors:** every caught exception that affects execution gets a trace event and increments `num_errors`.
8. **Budget termination:** stop runs when task budgets are exceeded and set `terminated_by` to `budget_tokens`, `budget_time`, `budget_cost`, `budget_tool_calls`, or `budget_llm_calls`.

---

## Task 1: Add execution schemas

**Objective:** Add model/run/trace schemas without changing current behavior.

**Files:**
- Modify: `src/agent_efficiency_bench/schemas.py`
- Test: `tests/test_execution_schemas.py`

**Step 1: Write failing tests**

Create `tests/test_execution_schemas.py`:

```python
from agent_efficiency_bench.schemas import ModelConfig, RunResult, RunTelemetry, TraceEvent


def test_model_config_defaults_to_openrouter():
    cfg = ModelConfig(model="openai/gpt-5.4-nano")
    assert cfg.provider == "openrouter"
    assert cfg.temperature == 0.0
    assert cfg.max_completion_tokens == 2048


def test_trace_event_carries_structured_data():
    event = TraceEvent(t_rel_seconds=0.1, event="llm_call_end", data={"cost": 0.01})
    assert event.data["cost"] == 0.01


def test_run_result_wraps_existing_telemetry():
    telemetry = RunTelemetry(
        run_id="r1",
        task_id="t1",
        agent="a",
        model="m",
        success=True,
        quality_score=1.0,
        wall_clock_seconds=1.0,
        input_tokens=10,
        output_tokens=5,
        estimated_usd=0.001,
    )
    result = RunResult(telemetry=telemetry, trace_path="traces/r1.jsonl")
    assert result.telemetry.total_tokens == 15
```

**Step 2: Run test to verify failure**

```bash
PYTHONPATH= uv run python -m pytest tests/test_execution_schemas.py -q
```

Expected: import failure for missing schema classes.

**Step 3: Implement minimal schemas**

Add the `ModelConfig`, `TraceEvent`, and `RunResult` classes described above.

**Step 4: Run tests**

```bash
PYTHONPATH= uv run python -m pytest tests/test_execution_schemas.py -q
PYTHONPATH= uv run python -m pytest -q
```

**Step 5: Commit**

```bash
git add src/agent_efficiency_bench/schemas.py tests/test_execution_schemas.py
git commit -m "feat: add execution schemas"
```

---

## Task 2: Add JSONL trace recorder

**Objective:** Provide a deterministic trace writer for accurate audit trails.

**Files:**
- Create: `src/agent_efficiency_bench/tracing.py`
- Test: `tests/test_tracing.py`

**Step 1: Write failing test**

```python
import json

from agent_efficiency_bench.tracing import TraceRecorder


def test_trace_recorder_writes_jsonl_events(tmp_path):
    path = tmp_path / "trace.jsonl"
    recorder = TraceRecorder(path=path, run_id="r1", task_id="t1")

    recorder.emit("task_start", data={"x": 1})
    recorder.emit("task_end", data={"success": True})

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["event"] for row in rows] == ["task_start", "task_end"]
    assert rows[0]["run_id"] == "r1"
    assert rows[0]["task_id"] == "t1"
    assert rows[1]["t_rel_seconds"] >= rows[0]["t_rel_seconds"]
```

**Step 2: Run test to verify failure**

```bash
PYTHONPATH= uv run python -m pytest tests/test_tracing.py -q
```

**Step 3: Implement recorder**

Implement:

```python
class TraceRecorder:
    def __init__(self, path: str | Path, run_id: str, task_id: str): ...
    def emit(self, event: str, data: dict | None = None, span_id: str | None = None, parent_span_id: str | None = None) -> TraceEvent: ...
```

Behavior:

- Create parent directories.
- Use `time.perf_counter()` for relative time.
- Append one JSON object per line using `TraceEvent.model_dump_json(exclude_none=True)`.
- Flush immediately after each event.

**Step 4: Run tests**

```bash
PYTHONPATH= uv run python -m pytest tests/test_tracing.py -q
PYTHONPATH= uv run python -m pytest -q
```

**Step 5: Commit**

```bash
git add src/agent_efficiency_bench/tracing.py tests/test_tracing.py
git commit -m "feat: add jsonl trace recorder"
```

---

## Task 3: Add OpenRouter client with accurate usage extraction

**Objective:** Make a small OpenRouter client that records usage and cost from actual provider responses.

**Files:**
- Create: `src/agent_efficiency_bench/providers/openrouter.py`
- Create: `src/agent_efficiency_bench/providers/__init__.py`
- Test: `tests/test_openrouter_client.py`
- Modify: `pyproject.toml` if switching from `requests` to `httpx`; otherwise keep `requests`.

**Step 1: Write failing tests using a fake HTTP transport**

Use monkeypatch with a fake session object; do not call real OpenRouter in unit tests.

```python
from agent_efficiency_bench.providers.openrouter import OpenRouterClient
from agent_efficiency_bench.schemas import ModelConfig


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []
    def post(self, url, headers, json, timeout):
        self.calls.append((url, headers, json, timeout))
        return FakeResponse({
            "id": "gen-1",
            "model": "openai/gpt-5.4-nano",
            "choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14, "cost": 0.00001},
        })


def test_openrouter_client_extracts_usage_and_cost():
    session = FakeSession()
    client = OpenRouterClient(api_key="test", session=session)
    result = client.chat(
        config=ModelConfig(model="openai/gpt-5.4-nano"),
        messages=[{"role": "user", "content": "hi"}],
    )

    assert result.content == "hello"
    assert result.generation_id == "gen-1"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 3
    assert result.cost_usd == 0.00001
    assert session.calls[0][1]["Authorization"] == "Bearer test"
```

**Step 2: Run test to verify failure**

```bash
PYTHONPATH= uv run python -m pytest tests/test_openrouter_client.py -q
```

**Step 3: Implement client**

Implement:

```python
class OpenRouterResponse(BaseModel):
    generation_id: str
    model: str
    content: str
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    raw: dict[str, Any]

class OpenRouterClient:
    def __init__(self, api_key: str | None = None, session: Any | None = None, base_url: str = "https://openrouter.ai/api/v1")
    def chat(self, config: ModelConfig, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> OpenRouterResponse
    def generation_stats(self, generation_id: str) -> dict[str, Any]
```

Headers:

```python
{
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", ""),
    "X-OpenRouter-Title": os.getenv("OPENROUTER_APP_TITLE", "Agent Efficiency Bench"),
}
```

Request body:

```python
{
    "model": config.model,
    "messages": messages,
    "temperature": config.temperature,
    "max_completion_tokens": config.max_completion_tokens,
    **config.extra,
}
```

Include `seed` only when not `None`.

Usage extraction priority:

1. `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`, `usage.cost` from chat completion.
2. If `cost` missing and `id` present, call `generation_stats(id)` and extract cost from response.
3. If cost still missing, return `0.0` but include `cost_source="missing"` in raw/trace later.

**Step 4: Run tests**

```bash
PYTHONPATH= uv run python -m pytest tests/test_openrouter_client.py -q
PYTHONPATH= uv run python -m pytest -q
```

**Step 5: Optional live smoke test**

Only run if `OPENROUTER_API_KEY` is set:

```bash
PYTHONPATH= uv run python - <<'PY'
import os
from agent_efficiency_bench.providers.openrouter import OpenRouterClient
from agent_efficiency_bench.schemas import ModelConfig

if not os.getenv("OPENROUTER_API_KEY"):
    raise SystemExit("OPENROUTER_API_KEY not set; skipping live smoke")

client = OpenRouterClient()
resp = client.chat(
    ModelConfig(model="openai/gpt-5.4-nano", max_completion_tokens=16),
    [{"role": "user", "content": "Reply with exactly: ok"}],
)
print(resp.model_dump())
PY
```

**Step 6: Commit**

```bash
git add src/agent_efficiency_bench/providers tests/test_openrouter_client.py pyproject.toml
git commit -m "feat: add openrouter provider client"
```

---

## Task 4: Add budget accounting

**Objective:** Track resources during a run and terminate accurately when a task budget is exceeded.

**Files:**
- Create: `src/agent_efficiency_bench/budget.py`
- Test: `tests/test_budget.py`

**Step 1: Write failing tests**

```python
from agent_efficiency_bench.budget import BudgetTracker
from agent_efficiency_bench.schemas import Budget


def test_budget_tracker_accumulates_llm_usage():
    tracker = BudgetTracker(Budget(max_total_tokens=100, max_estimated_usd=1.0, max_llm_calls=2))
    tracker.add_llm_call(prompt_tokens=10, completion_tokens=5, cost_usd=0.2, latency_seconds=1.5)
    assert tracker.input_tokens == 10
    assert tracker.output_tokens == 5
    assert tracker.estimated_usd == 0.2
    assert tracker.num_llm_calls == 1


def test_budget_tracker_detects_token_limit():
    tracker = BudgetTracker(Budget(max_total_tokens=10))
    tracker.add_llm_call(prompt_tokens=9, completion_tokens=2, cost_usd=0.0, latency_seconds=0.1)
    assert tracker.termination_reason() == "budget_tokens"
```

**Step 2: Run test to verify failure**

```bash
PYTHONPATH= uv run python -m pytest tests/test_budget.py -q
```

**Step 3: Implement tracker**

Track:

- `input_tokens`
- `output_tokens`
- `estimated_usd`
- `llm_time_seconds`
- `tool_time_seconds`
- `num_llm_calls`
- `num_tool_calls`
- `num_retries`
- `num_errors`
- `started_at`

Methods:

```python
def add_llm_call(...): ...
def add_tool_call(...): ...
def add_retry(...): ...
def add_error(...): ...
def elapsed_seconds(...): ...
def termination_reason(...): ...
def to_run_telemetry(...): RunTelemetry
```

**Step 4: Run tests and commit**

```bash
PYTHONPATH= uv run python -m pytest tests/test_budget.py -q
PYTHONPATH= uv run python -m pytest -q
git add src/agent_efficiency_bench/budget.py tests/test_budget.py
git commit -m "feat: add benchmark budget accounting"
```

---

## Task 5: Add a minimal answer-only OpenRouter agent

**Objective:** Provide a baseline agent that can answer a task instruction without tools, useful for smoke tests and AssistantBench-style closed-book baselines.

**Files:**
- Create: `src/agent_efficiency_bench/agents/base.py`
- Create: `src/agent_efficiency_bench/agents/openrouter_answer.py`
- Create: `src/agent_efficiency_bench/agents/__init__.py`
- Test: `tests/test_answer_agent.py`

**Step 1: Write failing test with fake client**

```python
from agent_efficiency_bench.agents.openrouter_answer import OpenRouterAnswerAgent
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, ModelConfig, SuccessCriteria


class FakeResponse:
    content = "final answer"
    prompt_tokens = 20
    completion_tokens = 5
    total_tokens = 25
    cost_usd = 0.01
    model = "fake/model"
    generation_id = "gen-1"
    finish_reason = "stop"
    raw = {}


class FakeClient:
    def chat(self, config, messages, tools=None):
        return FakeResponse()


def test_answer_agent_returns_output_and_usage(tmp_path):
    task = BenchmarkTask(
        task_id="t1",
        source="manual",
        source_type="custom",
        category="web_research",
        instruction="Answer the question.",
        environment={"type": "web"},
        complexity=Complexity(horizon="short"),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="manual"),
    )
    agent = OpenRouterAnswerAgent(client=FakeClient(), config=ModelConfig(model="fake/model"))
    result = agent.run(task, artifact_dir=tmp_path)

    assert result.output["answer"] == "final answer"
    assert result.telemetry.input_tokens == 20
    assert result.telemetry.output_tokens == 5
    assert result.telemetry.estimated_usd == 0.01
```

**Step 2: Run test to verify failure**

```bash
PYTHONPATH= uv run python -m pytest tests/test_answer_agent.py -q
```

**Step 3: Implement agent**

System prompt:

```text
You are executing a benchmark task. Produce the final answer only. Do not claim to use tools you were not given. If the task cannot be answered from the provided instruction, make the best attempt and state uncertainty.
```

Messages:

```python
[
  {"role": "system", "content": system_prompt},
  {"role": "user", "content": task.instruction},
]
```

The agent should:

- Create `artifact_dir`.
- Create a trace file.
- Emit `task_start`, `llm_call_start`, `llm_call_end`, `task_end`.
- Fill `RunTelemetry` with `success=False` and `quality_score=0.0` initially; evaluation will update outcome later.
- Return `RunResult(output={"answer": response.content}, ...)`.

**Step 4: Run tests and commit**

```bash
PYTHONPATH= uv run python -m pytest tests/test_answer_agent.py -q
PYTHONPATH= uv run python -m pytest -q
git add src/agent_efficiency_bench/agents tests/test_answer_agent.py
git commit -m "feat: add openrouter answer baseline agent"
```

---

## Task 6: Add evaluator interfaces and simple evaluators

**Objective:** Separate execution from scoring so the same telemetry can be evaluated by different harnesses.

**Files:**
- Create: `src/agent_efficiency_bench/evaluators/base.py`
- Create: `src/agent_efficiency_bench/evaluators/simple.py`
- Create: `src/agent_efficiency_bench/evaluators/__init__.py`
- Test: `tests/test_evaluators.py`

**Step 1: Write failing tests**

```python
from agent_efficiency_bench.evaluators.simple import ExactAnswerEvaluator, NoOpEvaluator


def test_noop_evaluator_leaves_run_unsuccessful():
    score = NoOpEvaluator().evaluate(task=None, result=None)
    assert score.success is False
    assert score.quality_score == 0.0


def test_exact_answer_evaluator_normalizes_case_and_space():
    evaluator = ExactAnswerEvaluator(expected="New York City")
    score = evaluator.evaluate_output({"answer": " new   york city "})
    assert score.success is True
    assert score.quality_score == 1.0
```

**Step 2: Implement**

Add:

```python
class EvaluationScore(BaseModel):
    success: bool
    quality_score: float
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
```

Evaluator interface:

```python
class Evaluator(Protocol):
    def evaluate(self, task: BenchmarkTask, result: RunResult) -> EvaluationScore: ...
```

Simple evaluators:

- `NoOpEvaluator`: always unsuccessful; used for execution smoke tests.
- `ExactAnswerEvaluator`: tests normalized string equality when expected answer is available.

**Step 3: Run and commit**

```bash
PYTHONPATH= uv run python -m pytest tests/test_evaluators.py -q
PYTHONPATH= uv run python -m pytest -q
git add src/agent_efficiency_bench/evaluators tests/test_evaluators.py
git commit -m "feat: add evaluator interfaces"
```

---

## Task 7: Add benchmark runner orchestration

**Objective:** Run one or many normalized tasks with an agent, evaluator, traces, and JSONL outputs.

**Files:**
- Create: `src/agent_efficiency_bench/runner.py`
- Test: `tests/test_runner.py`
- Modify: `src/agent_efficiency_bench/cli.py`

**Step 1: Write failing test with fake agent/evaluator**

```python
from agent_efficiency_bench.runner import BenchmarkRunner
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, RunResult, RunTelemetry, SuccessCriteria
from agent_efficiency_bench.evaluators.simple import EvaluationScore


class FakeAgent:
    name = "fake-agent"
    model = "fake-model"
    def run(self, task, artifact_dir):
        telemetry = RunTelemetry(
            run_id="r1",
            task_id=task.task_id,
            agent=self.name,
            model=self.model,
            success=False,
            quality_score=0.0,
            wall_clock_seconds=1.0,
            input_tokens=10,
            output_tokens=5,
            estimated_usd=0.01,
        )
        return RunResult(telemetry=telemetry, output={"answer": "ok"}, trace_path=str(artifact_dir / "trace.jsonl"))


class FakeEvaluator:
    def evaluate(self, task, result):
        return EvaluationScore(success=True, quality_score=1.0, reason="ok")


def make_task():
    return BenchmarkTask(
        task_id="t1", source="manual", source_type="custom", category="web_research",
        instruction="Say ok", environment={"type": "web"}, complexity=Complexity(horizon="short"),
        budgets=Budget(), success_criteria=SuccessCriteria(type="exact")
    )


def test_runner_updates_telemetry_with_evaluation(tmp_path):
    runner = BenchmarkRunner(agent=FakeAgent(), evaluator=FakeEvaluator(), output_dir=tmp_path)
    result = runner.run_task(make_task())
    assert result.telemetry.success is True
    assert result.telemetry.quality_score == 1.0
```

**Step 2: Implement runner**

`BenchmarkRunner` responsibilities:

- Create per-run `run_id` deterministically or UUID-based.
- Create artifact dir: `runs/<timestamp>/<task_id>/<run_id>/`.
- Call agent.
- Call evaluator.
- Update telemetry success and quality.
- Append `RunResult` to result JSONL and telemetry JSONL.
- Never swallow exceptions silently; convert exceptions into failed `RunTelemetry` with `terminated_by="error"` and trace event.

**Step 3: Add CLI command**

Add to `src/agent_efficiency_bench/cli.py`:

```bash
aeb run-answer \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --model openai/gpt-5.4-nano \
  --limit 1 \
  --output-dir runs/smoke
```

Initial behavior:

- Uses `OpenRouterAnswerAgent`.
- Uses `NoOpEvaluator` unless task has simple raw answer field and `--exact-answers` is set.
- Writes:
  - `runs/smoke/run_results.jsonl`
  - `runs/smoke/run_telemetry.jsonl`
  - per-task traces under artifact dirs.

**Step 4: Run and commit**

```bash
PYTHONPATH= uv run python -m pytest tests/test_runner.py -q
PYTHONPATH= uv run python -m pytest -q
git add src/agent_efficiency_bench/runner.py src/agent_efficiency_bench/cli.py tests/test_runner.py
git commit -m "feat: add benchmark runner orchestration"
```

---

## Task 8: Add live OpenRouter smoke command with strict guardrails

**Objective:** Verify real OpenRouter connectivity and telemetry on one cheap task without accidentally running the whole benchmark.

**Files:**
- Modify: `src/agent_efficiency_bench/cli.py`
- Test: `tests/test_cli.py` if CLI tests are already practical; otherwise verify manually.

**Step 1: Add command**

```bash
aeb openrouter-smoke --model openai/gpt-5.4-nano
```

Behavior:

- Requires `OPENROUTER_API_KEY`.
- Sends one tiny request with `max_completion_tokens=16`.
- Prints model, generation id, prompt tokens, completion tokens, cost, latency.
- Exits nonzero if usage fields are missing.

**Step 2: Manual verification**

Without API key:

```bash
PYTHONPATH= uv run aeb openrouter-smoke --model openai/gpt-5.4-nano
```

Expected: clear missing key error.

With API key:

```bash
OPENROUTER_API_KEY=... PYTHONPATH= uv run aeb openrouter-smoke --model openai/gpt-5.4-nano
```

Expected: response includes nonzero token counts and cost or generation-stats-audited cost.

**Step 3: Commit**

```bash
git add src/agent_efficiency_bench/cli.py tests/test_cli.py
git commit -m "feat: add openrouter smoke command"
```

---

## Task 9: Add AssistantBench answer harness

**Objective:** Execute web research tasks in an initial controlled baseline mode and evaluate dev-set tasks that have visible answers.

**Files:**
- Create: `src/agent_efficiency_bench/harnesses/assistantbench.py`
- Create: `src/agent_efficiency_bench/harnesses/__init__.py`
- Test: `tests/test_assistantbench_harness.py`
- Modify: `src/agent_efficiency_bench/cli.py`

**Design:**

Initial v1 should be two modes:

1. `closed_book`: answer-only OpenRouter agent; no web tools. This is cheap and gives a baseline.
2. `openrouter_web_plugin`: use OpenRouter `plugins=[{"id": "web"}]` if enabled for the model/account. This should be opt-in because it changes cost and provider behavior.

**Step 1: Write tests**

Test that a task with raw answer produces an `ExactAnswerEvaluator`.

```python
from agent_efficiency_bench.harnesses.assistantbench import evaluator_for_assistantbench_task
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, SuccessCriteria


def test_assistantbench_uses_raw_answer_when_available():
    task = BenchmarkTask(
        task_id="assistantbench__1", source="AssistantBench/AssistantBench", source_type="huggingface",
        category="web_research", instruction="Q?", environment={"type": "web"},
        complexity=Complexity(horizon="short"), budgets=Budget(),
        success_criteria=SuccessCriteria(type="structured_answer"), raw={"answer": "Paris"},
    )
    evaluator = evaluator_for_assistantbench_task(task)
    assert evaluator.evaluate_output({"answer": "paris"}).success is True
```

**Step 2: Implement harness helper**

- If `task.raw.answer` exists, use `ExactAnswerEvaluator` or structured answer evaluator.
- Otherwise use `NoOpEvaluator` and mark as execution-only.

**Step 3: Add CLI selector**

```bash
aeb run-assistantbench --model openai/gpt-5.4-nano --limit 3 --mode closed_book
```

**Step 4: Run and commit**

```bash
PYTHONPATH= uv run python -m pytest tests/test_assistantbench_harness.py -q
PYTHONPATH= uv run python -m pytest -q
git add src/agent_efficiency_bench/harnesses tests/test_assistantbench_harness.py src/agent_efficiency_bench/cli.py
git commit -m "feat: add assistantbench execution harness"
```

---

## Task 10: Add Terminal-Bench harness adapter

**Objective:** Support terminal tasks through the official Terminal-Bench/Harbor path when available, while keeping this repo’s metadata subset lightweight.

**Files:**
- Create: `src/agent_efficiency_bench/harnesses/terminal_bench.py`
- Test: `tests/test_terminal_bench_harness.py`
- Modify: `src/agent_efficiency_bench/cli.py`
- Modify: `README.md`

**Design:**

Do not reimplement Terminal-Bench. Add an adapter that can:

1. Check for required commands: `docker`, `uv`, and optionally `harbor`.
2. Resolve task IDs from normalized tasks.
3. Produce an execution plan command for official harness execution.
4. Parse a standardized result JSON if official harness produces one.
5. For v1, support a `--dry-run` command that verifies task mapping without spending model tokens.

**Step 1: Write tests for command generation**

```python
from agent_efficiency_bench.harnesses.terminal_bench import build_terminal_bench_command


def test_terminal_bench_command_includes_model_and_task():
    cmd = build_terminal_bench_command(task_id="count-dataset-tokens", model="openai/gpt-5.4-nano", output_dir="runs/tb")
    joined = " ".join(cmd)
    assert "count-dataset-tokens" in joined
    assert "openai/gpt-5.4-nano" in joined
```

**Step 2: Implement adapter**

Initial command pattern should be configurable because Terminal-Bench/Harbor versions differ:

```python
def build_terminal_bench_command(task_id: str, model: str, output_dir: str, agent: str = "terminus-2") -> list[str]:
    return [
        "harbor", "run",
        "--dataset", "terminal-bench/terminal-bench-2-1",
        "--agent", agent,
        "--model", model,
        "--task-id", task_id,
        "--output-dir", output_dir,
    ]
```

If Harbor CLI syntax differs, this is the first place to update. Keep it centralized.

**Step 3: CLI dry run**

```bash
aeb terminal-bench-command --task-id count-dataset-tokens --model openai/gpt-5.4-nano
```

**Step 4: Full execution later**

Actual Terminal-Bench execution should happen only when the official toolchain is installed and user explicitly passes `--execute`.

**Step 5: Run and commit**

```bash
PYTHONPATH= uv run python -m pytest tests/test_terminal_bench_harness.py -q
PYTHONPATH= uv run python -m pytest -q
git add src/agent_efficiency_bench/harnesses/terminal_bench.py tests/test_terminal_bench_harness.py src/agent_efficiency_bench/cli.py README.md
git commit -m "feat: add terminal-bench harness adapter"
```

---

## Task 11: Add SWE-bench harness adapter

**Objective:** Add a path for software-engineering tasks using official SWE-bench-style evaluation, without treating generated patches as correct until tests pass.

**Files:**
- Create: `src/agent_efficiency_bench/harnesses/swe_bench.py`
- Test: `tests/test_swe_bench_harness.py`
- Modify: `src/agent_efficiency_bench/cli.py`
- Modify: `README.md`

**Design:**

Two phases:

1. Agent phase: OpenRouter coding agent produces a patch/diff for a SWE-bench task.
2. Evaluation phase: official SWE-bench harness runs tests and reports resolved/not resolved.

For v1, implement only:

- task ID extraction
- patch artifact path convention
- official harness command builder
- result parser interface

Do not claim SWE-bench task success until official test output says resolved.

**Step 1: Write command-builder tests**

```python
from agent_efficiency_bench.harnesses.swe_bench import patch_path_for_task, build_swe_bench_eval_command


def test_patch_path_for_task_is_stable(tmp_path):
    path = patch_path_for_task(tmp_path, "django__django-123")
    assert path.name == "django__django-123.patch"


def test_swe_bench_command_mentions_predictions_file():
    cmd = build_swe_bench_eval_command(predictions_path="runs/swe/predictions.jsonl", run_id="smoke")
    joined = " ".join(cmd)
    assert "predictions.jsonl" in joined
    assert "smoke" in joined
```

**Step 2: Implement adapter**

Centralize command generation. Example placeholder:

```python
def build_swe_bench_eval_command(predictions_path: str, run_id: str, dataset_name: str = "SWE-bench/SWE-bench_Lite") -> list[str]:
    return [
        "python", "-m", "swebench.harness.run_evaluation",
        "--dataset_name", dataset_name,
        "--predictions_path", predictions_path,
        "--run_id", run_id,
    ]
```

Document that exact command may need adjustment depending on installed SWE-bench version.

**Step 3: Run and commit**

```bash
PYTHONPATH= uv run python -m pytest tests/test_swe_bench_harness.py -q
PYTHONPATH= uv run python -m pytest -q
git add src/agent_efficiency_bench/harnesses/swe_bench.py tests/test_swe_bench_harness.py src/agent_efficiency_bench/cli.py README.md
git commit -m "feat: add swe-bench harness adapter"
```

---

## Task 12: Add run report generation

**Objective:** Convert run telemetry into benchmark reports with efficiency metrics suitable for comparison.

**Files:**
- Create: `src/agent_efficiency_bench/reporting.py`
- Test: `tests/test_reporting.py`
- Modify: `src/agent_efficiency_bench/cli.py`

**Step 1: Write failing test**

```python
from agent_efficiency_bench.reporting import summarize_by_category
from agent_efficiency_bench.schemas import RunTelemetry


def test_summarize_by_category_joins_tasks_and_runs():
    tasks = {"t1": {"category": "web_research"}}
    runs = [RunTelemetry(
        run_id="r1", task_id="t1", agent="a", model="m", success=True, quality_score=1.0,
        wall_clock_seconds=60, input_tokens=100, output_tokens=20, estimated_usd=0.10,
    )]
    summary = summarize_by_category(tasks, runs)
    assert summary["web_research"]["cost_per_success"] == 0.10
```

**Step 2: Implement report functions**

Output both JSON and Markdown.

Required fields:

- total runs
- success rate
- mean quality
- total cost
- cost per success
- tokens per success
- seconds per success
- p50/p95 latency
- p50/p95 cost
- retry rate
- error rate

**Step 3: CLI command**

```bash
aeb report \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --runs runs/smoke/run_telemetry.jsonl \
  --output runs/smoke/report.md
```

**Step 4: Run and commit**

```bash
PYTHONPATH= uv run python -m pytest tests/test_reporting.py -q
PYTHONPATH= uv run python -m pytest -q
git add src/agent_efficiency_bench/reporting.py tests/test_reporting.py src/agent_efficiency_bench/cli.py
git commit -m "feat: add efficiency report generation"
```

---

## Task 13: Add integration smoke tests that do not spend tokens

**Objective:** Verify the whole execution path with fake provider responses.

**Files:**
- Create: `tests/test_integration_fake_provider.py`

**Step 1: Write integration test**

Test flow:

1. Load one task from `data/tasks/public_efficiency_subset.jsonl`.
2. Run `OpenRouterAnswerAgent` with fake client.
3. Evaluate with `NoOpEvaluator` or exact evaluator if raw answer exists.
4. Write result JSONL.
5. Generate report.
6. Assert trace file exists and telemetry has expected tokens/cost.

**Step 2: Run**

```bash
PYTHONPATH= uv run python -m pytest tests/test_integration_fake_provider.py -q
PYTHONPATH= uv run python -m pytest -q
```

**Step 3: Commit**

```bash
git add tests/test_integration_fake_provider.py
git commit -m "test: add fake-provider execution integration test"
```

---

## Task 14: Add documentation for accurate OpenRouter runs

**Objective:** Make it hard to accidentally run expensive benchmarks or misinterpret results.

**Files:**
- Modify: `README.md`
- Create: `docs/openrouter.md`
- Create: `docs/running-benchmarks.md`

**Content requirements:**

`docs/openrouter.md`:

- Required env vars.
- Recommended cheap smoke model.
- How usage/cost is captured.
- Why `/api/v1/generation` is used for auditing when needed.
- Caution that model/provider routing can affect reproducibility.
- Recommend pinning exact model IDs and recording OpenRouter returned `model`.

`docs/running-benchmarks.md`:

- `build-subset` command.
- `openrouter-smoke` command.
- `run-answer --limit 1` command.
- How to inspect traces.
- How to generate reports.
- How to set budget caps.
- Warning that full Terminal-Bench/SWE-bench runs require external official harnesses and may cost real money.

**Verification:**

```bash
PYTHONPATH= uv run python -m pytest -q
```

**Commit:**

```bash
git add README.md docs/openrouter.md docs/running-benchmarks.md
git commit -m "docs: document openrouter benchmark execution"
```

---

## Task 15: End-to-end manual verification checklist

Run these in order after implementation.

### 1. Unit tests

```bash
PYTHONPATH= uv run python -m pytest -q
```

Expected: all tests pass.

### 2. Dataset catalog

```bash
PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl
```

Expected: 24 tasks across `software_engineering`, `terminal_work`, and `web_research` unless source config changed.

### 3. OpenRouter missing-key behavior

```bash
unset OPENROUTER_API_KEY
PYTHONPATH= uv run aeb openrouter-smoke --model openai/gpt-5.4-nano
```

Expected: clear error saying `OPENROUTER_API_KEY` is required.

### 4. OpenRouter live smoke

```bash
export OPENROUTER_API_KEY="..."
PYTHONPATH= uv run aeb openrouter-smoke --model openai/gpt-5.4-nano
```

Expected: prints response text, generation ID, prompt tokens, completion tokens, cost, and latency.

### 5. One-task execution smoke

```bash
PYTHONPATH= uv run aeb run-answer \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --model openai/gpt-5.4-nano \
  --category web_research \
  --limit 1 \
  --output-dir runs/smoke
```

Expected files:

```text
runs/smoke/run_results.jsonl
runs/smoke/run_telemetry.jsonl
runs/smoke/**/trace.jsonl
```

### 6. Score telemetry

```bash
PYTHONPATH= uv run aeb score-runs runs/smoke/run_telemetry.jsonl
```

Expected: JSON summary with total cost/tokens/latency.

### 7. Generate report

```bash
PYTHONPATH= uv run aeb report \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --runs runs/smoke/run_telemetry.jsonl \
  --output runs/smoke/report.md
```

Expected: Markdown report with efficiency metrics.

---

## Implementation order summary

1. Execution schemas.
2. Trace recorder.
3. OpenRouter client.
4. Budget accounting.
5. Answer-only OpenRouter baseline agent.
6. Evaluator interfaces.
7. Benchmark runner orchestration.
8. OpenRouter live smoke command.
9. AssistantBench harness.
10. Terminal-Bench adapter.
11. SWE-bench adapter.
12. Report generation.
13. Fake-provider integration test.
14. Documentation.
15. Manual verification.

---

## Open questions to resolve before full benchmark runs

1. Which OpenRouter model IDs should be in the first comparison set?
2. Should OpenRouter web plugin be allowed for web research tasks, or should the first pass be closed-book only?
3. What max cost per run should be enforced by default?
4. Should Terminal-Bench/SWE-bench official harness setup be automated or documented as a prerequisite?
5. Should we evaluate each task once initially, or use `n=3` repeated trials to capture stochastic variance?

Recommended defaults for first live run:

```text
model: openai/gpt-5.4-nano or another cheap OpenRouter model
categories: web_research only
limit: 1
max_cost_per_task: $0.05
max_wall_clock_seconds: 120
repeats: 1
```
