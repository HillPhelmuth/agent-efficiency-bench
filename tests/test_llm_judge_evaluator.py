from agent_efficiency_bench.evaluators.llm_judge import LLMAnswerJudgeEvaluator, LLMJudgeScore
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, RunResult, RunTelemetry, SuccessCriteria


class FakeJudge:
    def __init__(self, score):
        self.score = score
        self.calls = []

    def judge(self, *, instruction, answer, citations):
        self.calls.append({"instruction": instruction, "answer": answer, "citations": citations})
        return self.score


def make_task(raw=None):
    return BenchmarkTask(
        task_id="assistantbench__stale",
        source="AssistantBench/AssistantBench",
        source_type="huggingface",
        category="web_research",
        instruction="Which supermarkets near Lincoln Park sell ready-to-eat salads under $15?",
        environment={"type": "web"},
        complexity=Complexity(horizon="short", requires_external_search=True),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="structured_answer"),
        raw=raw or {},
    )


def make_result(answer, citations=None):
    return RunResult(
        telemetry=RunTelemetry(
            run_id="r1",
            task_id="assistantbench__stale",
            agent="a",
            model="m",
            success=False,
            quality_score=0.0,
            wall_clock_seconds=1.0,
            input_tokens=1,
            output_tokens=1,
            estimated_usd=0.0,
        ),
        output={"answer": answer, "citations": citations or []},
        trace_path="trace.jsonl",
    )


def test_llm_judge_does_not_require_stale_assistantbench_expected_string():
    task = make_task(raw={"expected": {"text_contains": ["Potash Markets - Clark Street"], "requires_citation": True}})
    judge = FakeJudge(
        LLMJudgeScore(
            success=True,
            quality_score=4.6,
            reason="Answer directly addresses the current task and explains the stale condition.",
        )
    )
    evaluator = LLMAnswerJudgeEvaluator(judge=judge)

    score = evaluator.evaluate(
        task,
        make_result(
            "Current sources indicate Potash Markets no longer lists ready-to-eat salads under $15 near Lincoln Park.",
            ["https://www.potashmarkets.com/"],
        ),
    )

    assert score.success is True
    assert score.quality_score == 4.6
    assert judge.calls[0]["instruction"] == task.instruction
    assert "Potash Markets - Clark Street" not in judge.calls[0]["answer"]


def test_llm_judge_enforces_citation_requirement_before_calling_judge():
    evaluator = LLMAnswerJudgeEvaluator(judge=FakeJudge(LLMJudgeScore(success=True, quality_score=5.0)))

    score = evaluator.evaluate(make_task(raw={"expected": {"requires_citation": True}}), make_result("A claim without sources."))

    assert score.success is False
    assert score.quality_score == 1.0
    assert score.reason == "missing citation"
