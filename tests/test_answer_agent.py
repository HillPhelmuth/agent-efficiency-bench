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
    assert result.telemetry.success is False
    assert result.trace_path.endswith("trace.jsonl")
