from agent_efficiency_bench.sources import normalize_assistantbench, normalize_swe_bench, normalize_terminal_bench_task


def test_normalize_swe_bench_row():
    row = {
        "instance_id": "django__django-12345",
        "repo": "django/django",
        "problem_statement": "Broken behavior in forms",
        "FAIL_TO_PASS": '["tests.test_forms"]',
        "PASS_TO_PASS": '["tests.test_existing"]',
    }

    task = normalize_swe_bench(row)

    assert task.task_id == "swe_bench_lite__django__django-12345"
    assert task.category == "software_engineering"
    assert task.success_criteria.type == "unit_tests"
    assert task.environment["repo"] == "django/django"


def test_normalize_assistantbench_row():
    row = {"id": "dev-1", "question": "Find the cheapest option", "answer": "A"}

    task = normalize_assistantbench(row, split="dev")

    assert task.task_id == "assistantbench__dev-1"
    assert task.category == "web_research"
    assert task.environment["type"] == "web"


def test_normalize_terminal_bench_task_yaml():
    yaml_text = """
instruction: Configure the app and make tests pass.
difficulty: medium
tags: [devops, tests]
max_agent_timeout_sec: 1200
"""

    task = normalize_terminal_bench_task("configure-app", yaml_text, source_url="https://github.com/example/repo")

    assert task.task_id == "terminal_bench__configure-app"
    assert task.category == "terminal_work"
    assert task.budgets.max_wall_clock_seconds == 1200
