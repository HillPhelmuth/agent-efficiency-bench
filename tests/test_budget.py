from agent_efficiency_bench.budget import BudgetTracker
from agent_efficiency_bench.schemas import Budget


def test_budget_tracker_accumulates_llm_usage():
    tracker = BudgetTracker(Budget(max_total_tokens=100, max_estimated_usd=1.0, max_llm_calls=2))
    tracker.add_llm_call(prompt_tokens=10, completion_tokens=5, cost_usd=0.2, latency_seconds=1.5)
    assert tracker.input_tokens == 10
    assert tracker.output_tokens == 5
    assert tracker.estimated_usd == 0.2
    assert tracker.num_llm_calls == 1
    assert tracker.llm_time_seconds == 1.5


def test_budget_tracker_detects_token_limit():
    tracker = BudgetTracker(Budget(max_total_tokens=10))
    tracker.add_llm_call(prompt_tokens=9, completion_tokens=2, cost_usd=0.0, latency_seconds=0.1)
    assert tracker.termination_reason() == "budget_tokens"


def test_budget_tracker_creates_run_telemetry():
    tracker = BudgetTracker(Budget())
    tracker.add_llm_call(prompt_tokens=10, completion_tokens=5, cost_usd=0.2, latency_seconds=1.5)
    telemetry = tracker.to_run_telemetry(
        run_id="r1",
        task_id="t1",
        agent="agent",
        model="model",
        success=False,
        quality_score=0.0,
        terminated_by="not_evaluated",
    )
    assert telemetry.input_tokens == 10
    assert telemetry.output_tokens == 5
    assert telemetry.estimated_usd == 0.2
    assert telemetry.terminated_by == "not_evaluated"
