from typer.testing import CliRunner

from agent_efficiency_bench.cli import app


def test_openrouter_smoke_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = CliRunner().invoke(app, ["openrouter-smoke", "--model", "openai/gpt-4o-mini"])
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
