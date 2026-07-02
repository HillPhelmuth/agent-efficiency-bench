from agent_efficiency_bench.evaluators.structured import StructuredAnswerEvaluator
from agent_efficiency_bench.schemas import RunResult, RunTelemetry


def make_result(answer, citations=None):
    return RunResult(
        telemetry=RunTelemetry(
            run_id="r1",
            task_id="t1",
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


def test_structured_evaluator_passes_text_number_domain_and_citation_checks():
    evaluator = StructuredAnswerEvaluator(
        {
            "text_contains": ["Potash Markets"],
            "numbers": [{"label": "price", "value": 14.99, "tolerance": 0.01}],
            "required_domains": ["potashmarkets.com"],
            "requires_citation": True,
        }
    )

    score = evaluator.evaluate(None, make_result("Potash Markets salad costs $14.99", ["https://www.potashmarkets.com/salads"]))

    assert score.success is True
    assert score.quality_score == 1.0
    assert score.details["checks"]["text_contains"][0]["passed"] is True
    assert score.details["checks"]["numbers"][0]["passed"] is True
    assert score.details["checks"]["required_domains"][0]["passed"] is True
    assert score.details["checks"]["requires_citation"]["passed"] is True


def test_structured_evaluator_reports_partial_failure_details():
    evaluator = StructuredAnswerEvaluator({"text_contains": ["Potash Markets", "Clark Street"]})

    score = evaluator.evaluate(None, make_result("Potash Markets has salads."))

    assert score.success is False
    assert 0.0 < score.quality_score < 1.0
    assert score.reason == "structured checks failed"
    assert score.details["checks"]["text_contains"][1]["passed"] is False


def test_structured_evaluator_applies_numeric_tolerance():
    evaluator = StructuredAnswerEvaluator({"numbers": [{"label": "price", "value": 15.0, "tolerance": 0.25}]})

    score = evaluator.evaluate(None, make_result("The ready-to-eat salad costs $15.20."))

    assert score.success is True


def test_structured_evaluator_fails_missing_citation():
    evaluator = StructuredAnswerEvaluator({"requires_citation": True})

    score = evaluator.evaluate(None, make_result("Potash Markets is the answer."))

    assert score.success is False
    assert score.details["checks"]["requires_citation"]["passed"] is False
