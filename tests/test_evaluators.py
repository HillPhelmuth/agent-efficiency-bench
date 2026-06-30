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
