from agent_efficiency_bench.agents.openrouter_answer import OpenRouterAnswerAgent
from agent_efficiency_bench.evaluators.registry import RegistryEvaluator
from agent_efficiency_bench.runner import BenchmarkRunner
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
    raw = {
        "choices": [
            {
                "message": {
                    "annotations": [{"type": "url_citation", "url_citation": {"url": "https://example.com"}}],
                }
            }
        ]
    }


class FakeClient:
    def __init__(self):
        self.calls = []

    def chat(self, config, messages, tools=None, tool_choice=None):
        self.calls.append({"config": config, "messages": messages, "tools": tools, "tool_choice": tool_choice})
        return FakeResponse()


def make_task(requires_external_search=False):
    return BenchmarkTask(
        task_id="t1",
        source="manual",
        source_type="custom",
        category="web_research",
        instruction="Answer with search." if requires_external_search else "Answer the question.",
        environment={"type": "web"},
        complexity=Complexity(horizon="short", requires_external_search=requires_external_search),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="manual"),
    )


def test_answer_agent_returns_output_and_usage(tmp_path):
    agent = OpenRouterAnswerAgent(client=FakeClient(), config=ModelConfig(model="fake/model"))
    result = agent.run(make_task(), artifact_dir=tmp_path)

    assert result.output["answer"] == "final answer"
    assert result.output["annotations"] == [{"type": "url_citation", "url_citation": {"url": "https://example.com"}}]
    assert result.output["citations"] == ["https://example.com"]
    assert result.telemetry.input_tokens == 20
    assert result.telemetry.output_tokens == 5
    assert result.telemetry.estimated_usd == 0.01
    assert result.telemetry.scaffold == "answer-only"
    assert result.telemetry.server_tools_configured == []
    assert result.telemetry.num_annotations == 1
    assert result.telemetry.num_citations == 1
    assert result.telemetry.num_tool_calls == 0
    assert result.telemetry.success is False
    assert result.trace_path.endswith("trace.jsonl")


def test_answer_agent_passes_configured_tools_to_openrouter(tmp_path):
    tool = {"type": "function", "function": {"name": "web_search", "parameters": {"type": "object"}}}
    client = FakeClient()
    agent = OpenRouterAnswerAgent(
        client=client,
        config=ModelConfig(model="openai/gpt-5.4-nano", tools=[tool], tool_choice="auto"),
    )

    agent.run(make_task(requires_external_search=True), artifact_dir=tmp_path)

    assert client.calls[0]["tools"] == [tool]
    assert client.calls[0]["tool_choice"] == "auto"


def test_answer_agent_uses_web_search_scaffold_when_openrouter_web_search_configured(tmp_path):
    tool = {"type": "openrouter:web_search", "parameters": {"engine": "auto"}}
    agent = OpenRouterAnswerAgent(client=FakeClient(), config=ModelConfig(model="openai/gpt-5.4-nano", tools=[tool]))

    result = agent.run(make_task(requires_external_search=True), artifact_dir=tmp_path)

    assert result.telemetry.scaffold == "web-search-answer"
    assert result.telemetry.server_tools_configured == ["openrouter:web_search"]


def test_answer_agent_traces_configured_tools_and_response_annotations(tmp_path):
    tool = {"type": "openrouter:web_search", "parameters": {"engine": "auto"}}
    agent = OpenRouterAnswerAgent(client=FakeClient(), config=ModelConfig(model="openai/gpt-5.4-nano", tools=[tool]))

    result = agent.run(make_task(requires_external_search=True), artifact_dir=tmp_path)

    import json

    trace_rows = [json.loads(line) for line in open(result.trace_path, encoding="utf-8")]
    start = next(row for row in trace_rows if row["event"] == "llm_call_start")
    end = next(row for row in trace_rows if row["event"] == "llm_call_end")
    assert start["data"]["tools_configured"] == ["openrouter:web_search"]
    assert end["data"]["annotations"] == [{"type": "url_citation", "url_citation": {"url": "https://example.com"}}]
    assert end["data"]["citations"] == ["https://example.com"]
    assert result.telemetry.num_annotations == 1
    assert result.telemetry.num_citations == 1
    assert result.telemetry.num_tool_calls == 0


def test_answer_agent_traces_budget_checks_when_budget_passes(tmp_path):
    agent = OpenRouterAnswerAgent(client=FakeClient(), config=ModelConfig(model="fake/model"))

    result = agent.run(make_task(), artifact_dir=tmp_path)

    import json

    trace_rows = [json.loads(line) for line in open(result.trace_path, encoding="utf-8")]
    budget_check = next(row for row in trace_rows if row["event"] == "budget_check")
    assert budget_check["data"]["termination_reason"] is None


def test_answer_agent_marks_budget_exceeded_and_traces_event(tmp_path):
    task = make_task()
    task.budgets = Budget(max_total_tokens=10)
    agent = OpenRouterAnswerAgent(client=FakeClient(), config=ModelConfig(model="fake/model"))

    result = agent.run(task, artifact_dir=tmp_path)

    import json

    trace_rows = [json.loads(line) for line in open(result.trace_path, encoding="utf-8")]
    exceeded = next(row for row in trace_rows if row["event"] == "budget_exceeded")
    assert result.telemetry.terminated_by == "budget_tokens"
    assert exceeded["data"]["termination_reason"] == "budget_tokens"


def test_answer_agent_provider_citations_are_visible_to_structured_evaluator(tmp_path):
    class CorrectAnswerResponse(FakeResponse):
        content = "Potash Markets - Clark Street"

    class CorrectAnswerClient(FakeClient):
        def chat(self, config, messages, tools=None, tool_choice=None):
            self.calls.append({"config": config, "messages": messages, "tools": tools, "tool_choice": tool_choice})
            return CorrectAnswerResponse()

    task = BenchmarkTask(
        task_id="assistantbench__citation_regression",
        source="AssistantBench/AssistantBench",
        source_type="huggingface",
        category="web_research",
        instruction="Which store has the salad?",
        environment={"type": "web"},
        complexity=Complexity(horizon="short", requires_external_search=True),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="structured_answer", checker="assistantbench_exact_or_rubric"),
        raw={"expected": {"text_contains": ["Potash Markets - Clark Street"], "requires_citation": True}},
    )
    agent = OpenRouterAnswerAgent(client=CorrectAnswerClient(), config=ModelConfig(model="fake/model"))
    runner = BenchmarkRunner(agent=agent, evaluator=RegistryEvaluator(), output_dir=tmp_path)

    result = runner.run_task(task)

    assert result.telemetry.success is True
    assert result.telemetry.quality_score == 1.0
    assert result.output["evaluation"]["details"]["checks"]["requires_citation"]["passed"] is True
