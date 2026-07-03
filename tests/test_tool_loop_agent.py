import json

from agent_efficiency_bench.agents.openrouter_tool_loop import OpenRouterToolLoopAgent
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, ModelConfig, SuccessCriteria


class FakeResponse:
    def __init__(self, content, prompt_tokens=10, completion_tokens=5, cost_usd=0.01, generation_id="gen"):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        self.cost_usd = cost_usd
        self.model = "fake/model"
        self.generation_id = generation_id
        self.finish_reason = "stop"
        self.raw = {"choices": [{"message": {"annotations": []}}]}


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, config, messages, tools=None, tool_choice=None):
        self.calls.append({"config": config, "messages": messages, "tools": tools, "tool_choice": tool_choice})
        return self.responses.pop(0)


def make_task(budget=None):
    return BenchmarkTask(
        task_id="t1",
        source="manual",
        source_type="custom",
        category="web_research",
        instruction="Find the answer with research.",
        environment={"type": "web"},
        complexity=Complexity(horizon="short", requires_external_search=True),
        budgets=budget or Budget(),
        success_criteria=SuccessCriteria(type="manual"),
    )


def test_tool_loop_agent_runs_research_and_final_llm_calls(tmp_path):
    tool = {"type": "openrouter:web_search", "parameters": {"engine": "native"}}
    client = FakeClient([
        FakeResponse("research notes", prompt_tokens=11, completion_tokens=7, cost_usd=0.02, generation_id="research"),
        FakeResponse("final answer", prompt_tokens=13, completion_tokens=3, cost_usd=0.01, generation_id="final"),
    ])
    client.responses[0].raw = {
        "choices": [
            {"message": {"annotations": [{"type": "url_citation", "url_citation": {"url": "https://example.com/research"}}]}}
        ]
    }
    client.responses[1].raw = {
        "choices": [
            {"message": {"annotations": [{"type": "url_citation", "url_citation": {"url": "https://example.com/final"}}]}}
        ]
    }
    agent = OpenRouterToolLoopAgent(client=client, config=ModelConfig(model="fake/model", tools=[tool]))

    result = agent.run(make_task(), artifact_dir=tmp_path)

    assert result.output["answer"] == "final answer"
    assert result.output["research"] == "research notes"
    assert result.telemetry.scaffold == "react-tool-loop"
    assert result.telemetry.num_llm_calls == 2
    assert result.telemetry.input_tokens == 24
    assert result.telemetry.output_tokens == 10
    assert result.telemetry.estimated_usd == 0.03
    assert result.telemetry.server_tools_configured == ["openrouter:web_search"]
    assert result.telemetry.num_annotations == 2
    assert result.telemetry.num_citations == 2
    assert result.telemetry.num_tool_calls == 0
    assert client.calls[0]["tools"] == [tool]
    assert client.calls[1]["tools"] is None

    trace_rows = [json.loads(line) for line in open(result.trace_path, encoding="utf-8")]
    assert [row["event"] for row in trace_rows] == [
        "task_start",
        "llm_call_start",
        "llm_call_end",
        "budget_check",
        "llm_call_start",
        "llm_call_end",
        "budget_check",
        "task_end",
    ]


def test_tool_loop_agent_stops_after_research_when_budget_exceeded(tmp_path):
    client = FakeClient([
        FakeResponse("research notes", prompt_tokens=20, completion_tokens=5, cost_usd=0.02, generation_id="research"),
        FakeResponse("should not be used", generation_id="final"),
    ])
    agent = OpenRouterToolLoopAgent(client=client, config=ModelConfig(model="fake/model"))

    result = agent.run(make_task(Budget(max_total_tokens=10)), artifact_dir=tmp_path)

    assert result.output["answer"] == "research notes"
    assert result.telemetry.num_llm_calls == 1
    assert result.telemetry.terminated_by == "budget_tokens"
    assert len(client.calls) == 1

    trace_rows = [json.loads(line) for line in open(result.trace_path, encoding="utf-8")]
    assert any(row["event"] == "budget_exceeded" for row in trace_rows)
