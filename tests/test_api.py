import json

from fastapi.testclient import TestClient

from agent_efficiency_bench.schemas import RunTelemetry


def _write_task_file(path):
    path.write_text(
        '{"task_id":"t1","source":"AssistantBench","source_type":"huggingface","category":"web_research","instruction":"Question with enough chars","environment":{},"complexity":{"horizon":"short","requires_external_search":true},"success_criteria":{"type":"manual"}}\n'
        '{"task_id":"t2","source":"SWE-bench/SWE-bench_Lite","source_type":"huggingface","category":"software_engineering","instruction":"Fix bug","environment":{},"complexity":{"horizon":"long"},"success_criteria":{"type":"unit_tests"}}\n',
        encoding="utf-8",
    )


def _write_tau2_task_file(path):
    path.write_text(
        json.dumps(
            {
                "task_id": "tau2_bench_retail__55",
                "source": "sierra-research/tau2-bench",
                "source_type": "github",
                "category": "tool_workflow",
                "domain": "retail",
                "instruction": "Help the user complete the retail workflow.",
                "environment": {"type": "simulated_user_tools"},
                "complexity": {"horizon": "medium", "interaction_type": "conversational_tool_use"},
                "success_criteria": {"type": "tau2_actions", "checker": "tau2_harness"},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_api_catalog_and_options_expose_benchmark_metadata(tmp_path):
    from agent_efficiency_bench.api import create_app

    tasks = tmp_path / "tasks.jsonl"
    _write_task_file(tasks)

    client = TestClient(create_app(run_async=False))

    catalog = client.get("/api/catalog", params={"tasks_path": str(tasks)})
    options = client.get("/api/options")

    assert catalog.status_code == 200
    assert catalog.json()["total_tasks"] == 2
    assert catalog.json()["categories"] == {"software_engineering": 1, "web_research": 1}
    assert catalog.json()["sources"] == {"AssistantBench": 1, "SWE-bench/SWE-bench_Lite": 1}
    assert options.status_code == 200
    assert "answer-only" in options.json()["scaffolds"]
    assert "react-tool-loop" in options.json()["scaffolds"]
    assert "category" in options.json()["group_by_dimensions"]


def test_api_dry_run_expands_requested_benchmark_combinations(tmp_path):
    from agent_efficiency_bench.api import create_app

    tasks = tmp_path / "tasks.jsonl"
    _write_task_file(tasks)

    client = TestClient(create_app(run_async=False))
    response = client.post(
        "/api/runs",
        json={
            "tasks_path": str(tasks),
            "output_root": str(tmp_path / "runs"),
            "models": ["model-a", "model-b"],
            "scaffolds": ["answer-only", "react-tool-loop"],
            "categories": ["web_research"],
            "web_search": [False, True],
            "limit": 1,
            "n_trials": 2,
            "dry_run": True,
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "dry_run"
    assert payload["total_combinations"] == 8
    assert {combo["model"] for combo in payload["combinations"]} == {"model-a", "model-b"}
    assert {combo["scaffold"] for combo in payload["combinations"]} == {"answer-only", "react-tool-loop"}
    assert {combo["enable_web_search"] for combo in payload["combinations"]} == {False, True}


def test_api_dry_run_expands_tau2_official_web_combination(tmp_path):
    from agent_efficiency_bench.api import create_app

    tasks = tmp_path / "tasks.jsonl"
    _write_tau2_task_file(tasks)

    client = TestClient(create_app(run_async=False))
    response = client.post(
        "/api/runs",
        json={
            "tasks_path": str(tasks),
            "output_root": str(tmp_path / "runs"),
            "models": ["openai/gpt-5.4-nano"],
            "scaffolds": ["tau2-official"],
            "categories": ["tool_workflow"],
            "web_search": [False],
            "limit": 1,
            "dry_run": True,
            "tau2_user_model": "openai/gpt-5.4-mini",
            "tau2_num_trials": 2,
            "tau2_max_steps": 25,
            "tau2_seed": 123,
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "dry_run"
    [combo] = payload["combinations"]
    assert combo["scaffold"] == "tau2-official"
    assert combo["category"] == "tool_workflow"
    assert combo["tau2_user_model"] == "openai/gpt-5.4-mini"
    assert combo["tau2_num_trials"] == 2
    assert combo["tau2_max_steps"] == 25
    assert combo["tau2_seed"] == 123


def test_api_treats_legacy_trials_field_as_task_count_for_ui_requests(tmp_path):
    from agent_efficiency_bench.api import RunRequest, expand_run_request

    tasks = tmp_path / "tasks.jsonl"
    _write_task_file(tasks)
    request = RunRequest(
        tasks_path=str(tasks),
        output_root=str(tmp_path / "runs"),
        models=["model-a"],
        categories=["web_research"],
        limit=1,
        n_trials=2,
    )

    [combo] = expand_run_request(request, job_id="job-test")

    assert combo.limit == 2
    assert combo.n_trials == 1


def test_api_run_status_and_results_use_existing_runner_path(tmp_path, monkeypatch):
    from agent_efficiency_bench import api

    tasks = tmp_path / "tasks.jsonl"
    _write_task_file(tasks)
    calls = []

    def fake_execute_combination(combination):
        calls.append(combination)
        return [
            RunTelemetry(
                run_id=f"{combination.run_id_prefix}-r1",
                task_id="t1",
                agent="openrouter-answer",
                model=combination.model,
                scaffold="web-search-answer" if combination.enable_web_search else combination.scaffold,
                server_tools_configured=["openrouter:web_search"] if combination.enable_web_search else [],
                success=True,
                quality_score=5.0,
                wall_clock_seconds=2.0,
                input_tokens=10,
                output_tokens=5,
                estimated_usd=0.01,
            )
        ]

    monkeypatch.setattr(api, "execute_benchmark_combination", fake_execute_combination)
    client = TestClient(api.create_app(run_async=False))

    created = client.post(
        "/api/runs",
        json={
            "tasks_path": str(tasks),
            "output_root": str(tmp_path / "runs"),
            "models": ["model-a"],
            "scaffolds": ["answer-only"],
            "categories": ["web_research"],
            "web_search": [True],
            "limit": 1,
            "n_trials": 1,
            "dry_run": False,
        },
    )

    assert created.status_code == 200
    job_id = created.json()["job_id"]
    status = client.get(f"/api/runs/{job_id}")
    results = client.get(f"/api/runs/{job_id}/results")

    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert status.json()["completed_combinations"] == 1
    assert len(calls) == 1
    assert calls[0].enable_web_search is True
    assert results.status_code == 200
    assert results.json()["summary"]["category=web_research | model=model-a | scaffold=web-search-answer"]["total_runs"] == 1
    assert results.json()["chart_rows"][0]["success_rate"] == 1.0


def test_api_tau2_official_combination_writes_results_for_dashboard(tmp_path, monkeypatch):
    from agent_efficiency_bench import api

    tasks = tmp_path / "tasks.jsonl"
    _write_tau2_task_file(tasks)
    calls = []

    def fake_run_tau2_task(**kwargs):
        calls.append(kwargs)
        return {
            "parsed_result": {
                "success": True,
                "quality_score": 5.0,
                "passed_actions": 2,
                "total_actions": 2,
                "details": {"harness": "tau2-bench", "agent_cost": 0.03},
                "raw": {"reward": 1.0},
            }
        }

    monkeypatch.setattr(api, "run_tau2_task", fake_run_tau2_task)
    client = TestClient(api.create_app(run_async=False))

    created = client.post(
        "/api/runs",
        json={
            "tasks_path": str(tasks),
            "output_root": str(tmp_path / "runs"),
            "models": ["openai/gpt-5.4-nano"],
            "scaffolds": ["tau2-official"],
            "categories": ["tool_workflow"],
            "web_search": [False],
            "limit": 1,
            "dry_run": False,
            "tau2_user_model": "openai/gpt-5.4-mini",
            "tau2_num_trials": 2,
            "tau2_max_steps": 25,
        },
    )

    assert created.status_code == 200
    job_id = created.json()["job_id"]
    results = client.get(f"/api/runs/{job_id}/results")

    assert len(calls) == 1
    assert calls[0]["task_id"] == "tau2_bench_retail__55"
    assert calls[0]["user_model"] == "openai/gpt-5.4-mini"
    assert calls[0]["num_trials"] == 2
    assert calls[0]["max_steps"] == 25
    assert created.json()["status"] == "completed"
    assert created.json()["telemetry_paths"]
    row = results.json()["summary"]["category=tool_workflow | model=openai/gpt-5.4-nano | scaffold=tau2-official"]
    assert row["total_runs"] == 1
    assert row["success_rate"] == 1.0
    assert row["total_cost"] == 0.03


def test_api_results_can_read_existing_telemetry_file_for_charts(tmp_path):
    from agent_efficiency_bench.api import chart_summary_for_runs

    tasks = tmp_path / "tasks.jsonl"
    telemetry = tmp_path / "run_telemetry.jsonl"
    _write_task_file(tasks)
    telemetry.write_text(
        json.dumps(
            {
                "run_id": "r1",
                "task_id": "t1",
                "agent": "openrouter-answer",
                "model": "model-a",
                "scaffold": "answer-only",
                "success": True,
                "quality_score": 1.0,
                "wall_clock_seconds": 2.0,
                "input_tokens": 10,
                "output_tokens": 5,
                "estimated_usd": 0.01,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = chart_summary_for_runs(tasks_path=str(tasks), telemetry_paths=[str(telemetry)], group_by=["category", "model"])

    assert payload["summary"]["category=web_research | model=model-a"]["total_runs"] == 1
    assert payload["chart_rows"] == [
        {
            "group": "category=web_research | model=model-a",
            "total_runs": 1,
            "success_rate": 1.0,
            "mean_quality": 5.0,
            "total_cost": 0.01,
            "p50_latency_seconds": 2.0,
            "total_tokens": 15,
            "cost_per_success": 0.01,
        }
    ]


def test_api_chart_summary_reevaluates_run_results_when_available(tmp_path):
    from agent_efficiency_bench.api import chart_summary_for_runs

    tasks = tmp_path / "tasks.jsonl"
    telemetry = tmp_path / "run_telemetry.jsonl"
    results = tmp_path / "run_results.jsonl"
    task_row = {
        "task_id": "custom__url",
        "source": "custom-web-research",
        "source_type": "huggingface",
        "category": "web_research",
        "instruction": "Find the URL.",
        "environment": {"type": "web"},
        "complexity": {"horizon": "short", "requires_external_search": True},
        "success_criteria": {"type": "structured_answer", "checker": "assistantbench_exact_or_rubric"},
        "raw": {"expected": {"text_contains": ["https://example.com/data.gff3.gz"], "requires_citation": True}},
    }
    stale_telemetry = {
        "run_id": "r1",
        "task_id": "custom__url",
        "agent": "openrouter-answer",
        "model": "model-a",
        "scaffold": "answer-only",
        "success": False,
        "quality_score": 0.5,
        "wall_clock_seconds": 2.0,
        "input_tokens": 10,
        "output_tokens": 5,
        "estimated_usd": 0.01,
        "terminated_by": "evaluated",
    }
    tasks.write_text(json.dumps(task_row) + "\n", encoding="utf-8")
    telemetry.write_text(json.dumps(stale_telemetry) + "\n", encoding="utf-8")
    results.write_text(
        json.dumps(
            {
                "telemetry": stale_telemetry,
                "output": {"answer": "The file is https://example.com/data.gff3.gz."},
                "trace_path": "trace.jsonl",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = chart_summary_for_runs(tasks_path=str(tasks), telemetry_paths=[str(telemetry)], group_by=["category", "model"])

    row = payload["summary"]["category=web_research | model=model-a"]
    assert row["successful_runs"] == 1
    assert row["success_rate"] == 1.0
    assert row["mean_quality"] == 5.0


def test_api_chart_summary_does_not_rejudge_stored_llm_evaluations(tmp_path):
    from agent_efficiency_bench.api import chart_summary_for_runs

    tasks = tmp_path / "tasks.jsonl"
    telemetry = tmp_path / "run_telemetry.jsonl"
    results = tmp_path / "run_results.jsonl"
    task_row = {
        "task_id": "assistantbench__judged",
        "source": "AssistantBench/AssistantBench",
        "source_type": "huggingface",
        "category": "web_research",
        "instruction": "Q?",
        "environment": {"type": "web"},
        "complexity": {"horizon": "short", "requires_external_search": True},
        "success_criteria": {"type": "structured_answer"},
        "raw": {"expected": {"text_contains": ["stale"], "requires_citation": True}},
    }
    judged_telemetry = {
        "run_id": "r1",
        "task_id": "assistantbench__judged",
        "agent": "openrouter-answer",
        "model": "model-a",
        "scaffold": "answer-only",
        "success": True,
        "quality_score": 0.8,
        "wall_clock_seconds": 2.0,
        "input_tokens": 10,
        "output_tokens": 5,
        "estimated_usd": 0.01,
        "terminated_by": "success",
    }
    tasks.write_text(json.dumps(task_row) + "\n", encoding="utf-8")
    telemetry.write_text(json.dumps(judged_telemetry) + "\n", encoding="utf-8")
    results.write_text(
        json.dumps(
            {
                "telemetry": judged_telemetry,
                "output": {
                    "answer": "A previously judged answer.",
                    "evaluation": {"reason": "fake judge", "details": {"judge": "llm"}},
                },
                "trace_path": "trace.jsonl",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = chart_summary_for_runs(tasks_path=str(tasks), telemetry_paths=[str(telemetry)], group_by=["category", "model"])

    row = payload["summary"]["category=web_research | model=model-a"]
    assert row["successful_runs"] == 1
    assert row["mean_quality"] == 4.2


def test_web_ui_is_served_from_root(tmp_path):
    from agent_efficiency_bench.api import create_app

    client = TestClient(create_app(run_async=False))
    response = client.get("/")

    assert response.status_code == 200
    assert "Agent Efficiency Bench" in response.text
    assert "Chart" in response.text
