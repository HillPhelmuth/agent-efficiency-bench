from agent_efficiency_bench.providers.openrouter import OpenRouterClient
from agent_efficiency_bench.schemas import ModelConfig


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, headers, json, timeout):
        self.calls.append(("POST", url, headers, json, timeout))
        return FakeResponse(
            {
                "id": "gen-1",
                "model": "openai/gpt-4o-mini",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 3,
                    "total_tokens": 14,
                    "cost": 0.00001,
                },
            }
        )


def test_openrouter_client_extracts_usage_and_cost():
    session = FakeSession()
    client = OpenRouterClient(api_key="test", session=session)
    result = client.chat(
        config=ModelConfig(model="openai/gpt-4o-mini"),
        messages=[{"role": "user", "content": "hi"}],
    )

    assert result.content == "hello"
    assert result.generation_id == "gen-1"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 3
    assert result.total_tokens == 14
    assert result.cost_usd == 0.00001
    assert session.calls[0][2]["Authorization"] == "Bearer test"
    assert session.calls[0][3]["model"] == "openai/gpt-4o-mini"
