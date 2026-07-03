import json

import pytest

from agent_efficiency_bench.harnesses import swe_bench
from agent_efficiency_bench.harnesses.swe_bench import (
    build_prediction_row,
    build_swe_bench_eval_command,
    parse_swe_bench_report,
    patch_path_for_task,
    run_swe_bench_evaluation,
    write_prediction,
)


def test_patch_path_for_task_is_stable(tmp_path):
    path = patch_path_for_task(tmp_path, "django__django-123")
    assert path.name == "django__django-123.patch"


def test_swe_bench_command_mentions_predictions_file():
    cmd = build_swe_bench_eval_command(predictions_path="runs/swe/predictions.jsonl", run_id="smoke")
    joined = " ".join(cmd)
    assert "predictions.jsonl" in joined
    assert "smoke" in joined


def test_build_prediction_row_contains_required_fields():
    row = build_prediction_row("django__django-123", "diff --git a b", "openai/gpt-5.4-nano")

    assert row == {
        "instance_id": "django__django-123",
        "model_name_or_path": "openai/gpt-5.4-nano",
        "model_patch": "diff --git a b",
    }


def test_write_prediction_overwrite_is_explicit(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    write_prediction(predictions, "one", "patch-1", "model-a", append=False)
    write_prediction(predictions, "two", "patch-2", "model-b", append=False)

    lines = predictions.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["instance_id"] == "two"


def test_run_swe_bench_evaluation_dry_run_reports_prerequisites(monkeypatch, tmp_path):
    monkeypatch.setattr(swe_bench, "check_swe_bench_prerequisites", lambda require_package=True: {"python": True, "swebench": False})

    result = run_swe_bench_evaluation(predictions_path=str(tmp_path / "predictions.jsonl"), run_id="smoke")

    assert result["dry_run"] is True
    assert result["execute"] is False
    assert result["ready"] is False
    assert result["prerequisites"]["swebench"] is False


def test_run_swe_bench_evaluation_execute_requires_prerequisites(monkeypatch, tmp_path):
    monkeypatch.setattr(swe_bench, "check_swe_bench_prerequisites", lambda require_package=True: {"python": True, "swebench": False})

    with pytest.raises(RuntimeError, match="Missing SWE-bench prerequisites: swebench"):
        run_swe_bench_evaluation(
            predictions_path=str(tmp_path / "predictions.jsonl"),
            run_id="smoke",
            dry_run=False,
            execute=True,
        )


def test_run_swe_bench_evaluation_execute_runs_command_and_parses_report(monkeypatch, tmp_path):
    report_path = tmp_path / "smoke-report.json"
    report_path.write_text(json.dumps({"resolved_ids": ["django__django-123"], "unresolved_ids": ["sympy__sympy-1"]}), encoding="utf-8")
    monkeypatch.setattr(swe_bench, "check_swe_bench_prerequisites", lambda require_package=True: {"python": True, "swebench": True})

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    result = run_swe_bench_evaluation(
        predictions_path=str(tmp_path / "predictions.jsonl"),
        run_id="smoke",
        dry_run=False,
        execute=True,
        report_path=report_path,
        subprocess_run=lambda *args, **kwargs: Completed(),
    )

    assert result["exit_code"] == 0
    assert result["parsed_report"]["resolved_count"] == 1
    assert result["parsed_report"]["unresolved_count"] == 1


def test_parse_swe_bench_report_reads_nested_summary(tmp_path):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"summary": {"resolved": ["django__django-123"], "unresolved": ["sympy__sympy-1"]}}), encoding="utf-8")

    parsed = parse_swe_bench_report(report_path)

    assert parsed["resolved_instances"] == ["django__django-123"]
    assert parsed["unresolved_instances"] == ["sympy__sympy-1"]
