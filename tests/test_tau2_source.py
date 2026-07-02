from agent_efficiency_bench.sources import load_source


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_load_tau2_bench_github_subset(monkeypatch):
    payload = [
        {
            "id": "0",
            "user_scenario": {"instructions": {"domain": "retail", "reason_for_call": "Need help with an order."}},
            "evaluation_criteria": {"actions": [{"name": "get_order_details"}], "reward_basis": ["DB"]},
        },
        {
            "id": "1",
            "user_scenario": {"instructions": {"domain": "retail", "reason_for_call": "Need help with a return."}},
            "evaluation_criteria": {"actions": [{"name": "return_delivered_order_items"}], "reward_basis": ["DB"]},
        },
    ]

    def fake_get(url, timeout=30, headers=None):
        assert "data/tau2/domains/retail/tasks.json" in url
        return FakeResponse(payload)

    monkeypatch.setattr("agent_efficiency_bench.sources.requests.get", fake_get)

    tasks = load_source({"type": "github_tau2_bench", "domain": "retail", "sample_size": 1})

    assert len(tasks) == 1
    assert tasks[0].source == "sierra-research/tau2-bench"
    assert tasks[0].category == "tool_workflow"
