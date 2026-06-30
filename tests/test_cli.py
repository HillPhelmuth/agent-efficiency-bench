from typer.testing import CliRunner

from agent_efficiency_bench.cli import app


def test_openrouter_smoke_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = CliRunner().invoke(app, ["openrouter-smoke", "--model", "openai/gpt-4o-mini"])
    assert result.exit_code != 0
    assert "OPENROUTER_API_KEY" in result.output
