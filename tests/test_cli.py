from typer.testing import CliRunner

from agent_efficiency_bench import cli
from agent_efficiency_bench.cli import app
from agent_efficiency_bench.evaluators.registry import RegistryEvaluator


def test_openrouter_smoke_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = CliRunner().invoke(app, ["openrouter-smoke", "--model", "openai/gpt-5.4-nano"])
    assert result.exit_code != 0
    assert "OPENROUTER_API_KEY" in result.output


def test_report_cli_accepts_group_by_dimensions(tmp_path):
    tasks = tmp_path / "tasks.jsonl"
    runs = tmp_path / "run_telemetry.jsonl"
    manifest = tmp_path / "manifest.json"
    report = tmp_path / "report.md"
    tasks.write_text(
        '{"task_id":"t1","source":"AssistantBench","source_type":"huggingface","category":"web_research","instruction":"Q?","environment":{},"complexity":{"horizon":"short"},"success_criteria":{"type":"manual"}}\n',
        encoding="utf-8",
    )
    runs.write_text(
        '{"run_id":"r1","task_id":"t1","agent":"openrouter-answer","model":"openai/gpt-5.4-nano","success":true,"quality_score":1.0,"wall_clock_seconds":1.0,"input_tokens":1,"output_tokens":1,"estimated_usd":0.01}\n',
        encoding="utf-8",
    )
    manifest.write_text('{"tools_configured":["openrouter:web_search"]}', encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "report",
            "--tasks",
            str(tasks),
            "--runs",
            str(runs),
            "--output",
            str(report),
            "--group-by",
            "category,model,tools_enabled",
            "--manifest",
            str(manifest),
        ],
    )

    assert result.exit_code == 0
    assert "tools_enabled=true" in report.read_text(encoding="utf-8")


def test_report_cli_writes_json_and_csv_formats(tmp_path):
    tasks = tmp_path / "tasks.jsonl"
    runs = tmp_path / "run_telemetry.jsonl"
    report_json = tmp_path / "report.json"
    report_csv = tmp_path / "report.csv"
    tasks.write_text(
        '{"task_id":"t1","source":"AssistantBench","source_type":"huggingface","category":"web_research","instruction":"Q?","environment":{},"complexity":{"horizon":"short"},"success_criteria":{"type":"manual"}}\n',
        encoding="utf-8",
    )
    runs.write_text(
        '{"run_id":"r1","task_id":"t1","agent":"openrouter-answer","model":"openai/gpt-5.4-nano","success":false,"quality_score":0.0,"wall_clock_seconds":1.0,"input_tokens":1,"output_tokens":1,"estimated_usd":0.01,"terminated_by":"not_evaluated"}\n',
        encoding="utf-8",
    )

    json_result = CliRunner().invoke(
        app,
        [
            "report",
            "--tasks",
            str(tasks),
            "--runs",
            str(runs),
            "--output",
            str(report_json),
            "--format",
            "json",
        ],
    )
    csv_result = CliRunner().invoke(
        app,
        [
            "report",
            "--tasks",
            str(tasks),
            "--runs",
            str(runs),
            "--output",
            str(report_csv),
            "--format",
            "csv",
        ],
    )

    assert json_result.exit_code == 0
    assert csv_result.exit_code == 0
    assert '"unevaluated_runs": 1' in report_json.read_text(encoding="utf-8")
    assert "unevaluated_runs" in report_csv.read_text(encoding="utf-8")


def test_audit_tasks_cli_writes_task_audit(tmp_path):
    tasks = tmp_path / "tasks.jsonl"
    output = tmp_path / "audit.md"
    tasks.write_text(
        '{"task_id":"t1","source":"AssistantBench","source_type":"huggingface","category":"web_research","instruction":"Q?","environment":{},"complexity":{"horizon":"short"},"success_criteria":{"type":"manual"}}\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["audit-tasks", str(tasks), "--output", str(output)])

    assert result.exit_code == 0
    assert "# Task Audit" in output.read_text(encoding="utf-8")


def test_run_tool_loop_cli_is_registered():
    result = CliRunner().invoke(app, ["run-tool-loop", "--help"])

    assert result.exit_code == 0
    assert "Run a minimal multi-step OpenRouter tool-loop scaffold" in result.output


def test_serve_cli_is_registered():
    result = CliRunner().invoke(app, ["serve", "--help"])

    assert result.exit_code == 0
    assert "Start the REST API and benchmark dashboard web UI" in result.output


def test_run_answer_cli_passes_suite_budget_options(tmp_path, monkeypatch):
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(
        '{"task_id":"t1","source":"AssistantBench","source_type":"huggingface","category":"web_research","instruction":"Question with enough chars","environment":{},"complexity":{"horizon":"short"},"success_criteria":{"type":"manual"}}\n',
        encoding="utf-8",
    )

    captured = {}

    class FakeRunner:
        def __init__(self, *, suite_budget, evaluator, **kwargs):
            captured["suite_budget"] = suite_budget
            captured["evaluator"] = evaluator

        def run_tasks(self, selected, n_trials=1):
            captured["selected_count"] = len(selected)
            captured["n_trials"] = n_trials
            return []

    class FakeAgent:
        def __init__(self, config):
            self.config = config

    monkeypatch.setattr(cli, "BenchmarkRunner", FakeRunner)
    monkeypatch.setattr(cli, "OpenRouterAnswerAgent", FakeAgent)

    result = CliRunner().invoke(
        app,
        [
            "run-answer",
            "--tasks",
            str(tasks),
            "--model",
            "openai/gpt-5.4-nano",
            "--output-dir",
            str(tmp_path / "runs"),
            "--n-trials",
            "2",
            "--max-suite-usd",
            "1.5",
            "--max-suite-seconds",
            "30",
            "--max-suite-tasks",
            "2",
            "--max-suite-failures",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert captured["selected_count"] == 1
    assert captured["n_trials"] == 2
    assert isinstance(captured["evaluator"], RegistryEvaluator)
    assert captured["suite_budget"].max_suite_estimated_usd == 1.5
    assert captured["suite_budget"].max_suite_wall_clock_seconds == 30.0
    assert captured["suite_budget"].max_suite_tasks == 2
    assert captured["suite_budget"].max_suite_failures == 1


def test_run_tool_loop_cli_passes_suite_budget_options(tmp_path, monkeypatch):
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(
        '{"task_id":"t1","source":"AssistantBench","source_type":"huggingface","category":"web_research","instruction":"Question with enough chars","environment":{},"complexity":{"horizon":"short"},"success_criteria":{"type":"manual"}}\n',
        encoding="utf-8",
    )

    captured = {}

    class FakeRunner:
        def __init__(self, *, suite_budget, evaluator, **kwargs):
            captured["suite_budget"] = suite_budget
            captured["evaluator"] = evaluator

        def run_tasks(self, selected, n_trials=1):
            captured["selected_count"] = len(selected)
            captured["n_trials"] = n_trials
            return []

    class FakeAgent:
        def __init__(self, config):
            self.config = config

    monkeypatch.setattr(cli, "BenchmarkRunner", FakeRunner)
    monkeypatch.setattr(cli, "OpenRouterToolLoopAgent", FakeAgent)

    result = CliRunner().invoke(
        app,
        [
            "run-tool-loop",
            "--tasks",
            str(tasks),
            "--model",
            "openai/gpt-5.4-nano",
            "--output-dir",
            str(tmp_path / "runs"),
            "--n-trials",
            "2",
            "--max-suite-usd",
            "1.5",
            "--max-suite-seconds",
            "30",
            "--max-suite-tasks",
            "2",
            "--max-suite-failures",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert captured["selected_count"] == 1
    assert captured["n_trials"] == 2
    assert isinstance(captured["evaluator"], RegistryEvaluator)
    assert captured["suite_budget"].max_suite_estimated_usd == 1.5
    assert captured["suite_budget"].max_suite_wall_clock_seconds == 30.0
    assert captured["suite_budget"].max_suite_tasks == 2
    assert captured["suite_budget"].max_suite_failures == 1


def test_run_assistantbench_cli_passes_suite_budget_options(tmp_path, monkeypatch):
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(
        '{"task_id":"t1","source":"AssistantBench","source_type":"huggingface","category":"web_research","instruction":"Question with enough chars","environment":{},"complexity":{"horizon":"short"},"success_criteria":{"type":"manual"}}\n',
        encoding="utf-8",
    )

    captured = {}

    class FakeRunner:
        def __init__(self, *, suite_budget, evaluator, **kwargs):
            captured["suite_budget"] = suite_budget
            captured["evaluator"] = evaluator

        def run_tasks(self, selected, n_trials=1):
            captured["selected_count"] = len(selected)
            captured["n_trials"] = n_trials
            return []

    class FakeAgent:
        def __init__(self, config):
            self.config = config

    monkeypatch.setattr(cli, "BenchmarkRunner", FakeRunner)
    monkeypatch.setattr(cli, "OpenRouterAnswerAgent", FakeAgent)

    result = CliRunner().invoke(
        app,
        [
            "run-assistantbench",
            "--tasks",
            str(tasks),
            "--model",
            "openai/gpt-5.4-nano",
            "--output-dir",
            str(tmp_path / "runs"),
            "--n-trials",
            "2",
            "--max-suite-usd",
            "1.5",
            "--max-suite-seconds",
            "30",
            "--max-suite-tasks",
            "2",
            "--max-suite-failures",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert captured["selected_count"] == 1
    assert captured["n_trials"] == 2
    assert isinstance(captured["evaluator"], RegistryEvaluator)
    assert captured["suite_budget"].max_suite_estimated_usd == 1.5
    assert captured["suite_budget"].max_suite_wall_clock_seconds == 30.0
    assert captured["suite_budget"].max_suite_tasks == 2
    assert captured["suite_budget"].max_suite_failures == 1


def test_run_terminal_bench_official_cli_uses_dry_run_by_default(tmp_path, monkeypatch):
    captured = {}

    def fake_run_terminal_bench_task(**kwargs):
        captured.update(kwargs)
        return {"dry_run": kwargs["dry_run"], "execute": kwargs["execute"], "command": ["harbor", "run"]}

    monkeypatch.setattr(cli, "run_terminal_bench_task", fake_run_terminal_bench_task)

    result = CliRunner().invoke(
        app,
        [
            "run-terminal-bench-official",
            "--task-id",
            "count-dataset-tokens",
            "--model",
            "openai/gpt-5.4-nano",
            "--output-dir",
            str(tmp_path / "tb"),
        ],
    )

    assert result.exit_code == 0
    assert captured["dry_run"] is True
    assert captured["execute"] is False


def test_run_terminal_bench_official_cli_execute_flag_is_explicit(tmp_path, monkeypatch):
    captured = {}

    def fake_run_terminal_bench_task(**kwargs):
        captured.update(kwargs)
        return {"dry_run": kwargs["dry_run"], "execute": kwargs["execute"], "command": ["harbor", "run"]}

    monkeypatch.setattr(cli, "run_terminal_bench_task", fake_run_terminal_bench_task)

    result = CliRunner().invoke(
        app,
        [
            "run-terminal-bench-official",
            "--task-id",
            "count-dataset-tokens",
            "--model",
            "openai/gpt-5.4-nano",
            "--output-dir",
            str(tmp_path / "tb"),
            "--execute",
            "--max-suite-usd",
            "1.5",
        ],
    )

    assert result.exit_code == 0
    assert captured["dry_run"] is False
    assert captured["execute"] is True
    assert captured["suite_budget"]["max_suite_estimated_usd"] == 1.5


def test_run_swe_bench_official_cli_uses_dry_run_by_default(tmp_path, monkeypatch):
    captured = {}

    def fake_run_swe_bench_evaluation(**kwargs):
        captured.update(kwargs)
        return {"dry_run": kwargs["dry_run"], "execute": kwargs["execute"], "command": ["python", "-m", "swebench.harness.run_evaluation"]}

    monkeypatch.setattr(cli, "run_swe_bench_evaluation", fake_run_swe_bench_evaluation)

    result = CliRunner().invoke(
        app,
        [
            "run-swe-bench-official",
            "--predictions-path",
            str(tmp_path / "predictions.jsonl"),
            "--run-id",
            "smoke",
        ],
    )

    assert result.exit_code == 0
    assert captured["dry_run"] is True
    assert captured["execute"] is False


def test_run_swe_bench_official_cli_execute_flag_is_explicit(tmp_path, monkeypatch):
    captured = {}

    def fake_run_swe_bench_evaluation(**kwargs):
        captured.update(kwargs)
        return {"dry_run": kwargs["dry_run"], "execute": kwargs["execute"], "command": ["python", "-m", "swebench.harness.run_evaluation"]}

    monkeypatch.setattr(cli, "run_swe_bench_evaluation", fake_run_swe_bench_evaluation)

    result = CliRunner().invoke(
        app,
        [
            "run-swe-bench-official",
            "--predictions-path",
            str(tmp_path / "predictions.jsonl"),
            "--run-id",
            "smoke",
            "--execute",
            "--max-suite-failures",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert captured["dry_run"] is False
    assert captured["execute"] is True
    assert captured["suite_budget"]["max_suite_failures"] == 1


def test_run_tau2_official_cli_uses_dry_run_by_default(tmp_path, monkeypatch):
    captured = {}

    def fake_run_tau2_task(**kwargs):
        captured.update(kwargs)
        return {"dry_run": kwargs["dry_run"], "execute": kwargs["execute"], "unresolved_dependency": True}

    monkeypatch.setattr(cli, "run_tau2_task", fake_run_tau2_task)

    result = CliRunner().invoke(
        app,
        [
            "run-tau2-official",
            "--task-id",
            "tau2_bench_retail__55",
            "--model",
            "openai/gpt-5.4-nano",
            "--output-dir",
            str(tmp_path / "tau2"),
        ],
    )

    assert result.exit_code == 0
    assert captured["dry_run"] is True
    assert captured["execute"] is False


def test_run_tau2_official_cli_execute_flag_passes_runner_module(tmp_path, monkeypatch):
    captured = {}

    def fake_run_tau2_task(**kwargs):
        captured.update(kwargs)
        return {"dry_run": kwargs["dry_run"], "execute": kwargs["execute"], "unresolved_dependency": False}

    monkeypatch.setattr(cli, "run_tau2_task", fake_run_tau2_task)

    result = CliRunner().invoke(
        app,
        [
            "run-tau2-official",
            "--task-id",
            "tau2_bench_retail__55",
            "--model",
            "openai/gpt-5.4-nano",
            "--output-dir",
            str(tmp_path / "tau2"),
            "--runner-module",
            "tau2.runner",
            "--execute",
        ],
    )

    assert result.exit_code == 0
    assert captured["dry_run"] is False
    assert captured["execute"] is True
    assert captured["runner_module"] == "tau2.runner"


def test_run_tau2_official_cli_passes_agent_and_evaluator_options(tmp_path, monkeypatch):
    captured = {}

    def fake_run_tau2_task(**kwargs):
        captured.update(kwargs)
        return {"dry_run": kwargs["dry_run"], "execute": kwargs["execute"], "command": ["tau2", "run"]}

    monkeypatch.setattr(cli, "run_tau2_task", fake_run_tau2_task)

    result = CliRunner().invoke(
        app,
        [
            "run-tau2-official",
            "--task-id",
            "tau2_bench_retail__55",
            "--model",
            "openai/gpt-5.4-nano",
            "--output-dir",
            str(tmp_path / "tau2"),
            "--agent",
            "custom_agent",
            "--user",
            "custom_user",
            "--user-model",
            "openai/gpt-5.4-mini",
            "--num-trials",
            "2",
            "--max-steps",
            "25",
            "--seed",
            "123",
            "--tau2-save-to",
            "aeb-tau2-smoke",
            "--result-path",
            str(tmp_path / "tau2" / "results.json"),
        ],
    )

    assert result.exit_code == 0
    assert captured["agent"] == "custom_agent"
    assert captured["user"] == "custom_user"
    assert captured["user_model"] == "openai/gpt-5.4-mini"
    assert captured["num_trials"] == 2
    assert captured["max_steps"] == 25
    assert captured["seed"] == 123
    assert captured["tau2_save_to"] == "aeb-tau2-smoke"
    assert captured["result_path"].endswith("results.json")
