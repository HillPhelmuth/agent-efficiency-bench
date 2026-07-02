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
    assert result.telemetry.input_tokens == 20
    assert result.telemetry.output_tokens == 5
    assert result.telemetry.estimated_usd == 0.01
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


def test_answer_agent_traces_configured_tools_and_response_annotations(tmp_path):
    tool = {"type": "openrouter:web_search", "parameters": {"engine": "native"}}
    agent = OpenRouterAnswerAgent(client=FakeClient(), config=ModelConfig(model="openai/gpt-5.4-nano", tools=[tool]))

    result = agent.run(make_task(requires_external_search=True), artifact_dir=tmp_path)

    import json

    trace_rows = [json.loads(line) for line in open(result.trace_path, encoding="utf-8")]
    start = next(row for row in trace_rows if row["event"] == "llm_call_start")
    end = next(row for row in trace_rows if row["event"] == "llm_call_end")
    assert start["data"]["tools_configured"] == ["openrouter:web_search"]
    assert end["data"]["annotations"] == [{"type": "url_citation", "url_citation": {"url": "https://example.com"}}]
    assert end["data"]["citations"] == ["https://example.com"]


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
