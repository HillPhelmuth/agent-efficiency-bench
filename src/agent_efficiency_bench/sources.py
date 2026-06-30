from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

import requests
import yaml
from datasets import load_dataset

from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, SuccessCriteria


GITHUB_API = "https://api.github.com"
RAW_GITHUB = "https://raw.githubusercontent.com"


def _stable_sample(rows: Iterable[Any], sample_size: int, key_fn) -> list[Any]:
    keyed = []
    for row in rows:
        key = str(key_fn(row))
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        keyed.append((digest, row))
    return [row for _, row in sorted(keyed)[:sample_size]]


def _horizon_from_tool_calls(calls: int | None) -> str:
    if calls is None:
        return "medium"
    if calls <= 3:
        return "atomic"
    if calls <= 10:
        return "short"
    if calls <= 30:
        return "medium"
    return "long"


def normalize_swe_bench(row: dict[str, Any]) -> BenchmarkTask:
    instance_id = str(row["instance_id"])
    fail_to_pass = row.get("FAIL_TO_PASS")
    pass_to_pass = row.get("PASS_TO_PASS")
    return BenchmarkTask(
        task_id=f"swe_bench_lite__{instance_id}",
        source="SWE-bench/SWE-bench_Lite",
        source_type="huggingface",
        source_url="https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite",
        category="software_engineering",
        domain="github_issue_resolution",
        instruction=str(row.get("problem_statement") or "Resolve the described GitHub issue."),
        environment={
            "type": "terminal",
            "repo": row.get("repo"),
            "base_commit": row.get("base_commit"),
            "version": row.get("version"),
        },
        complexity=Complexity(
            horizon="long",
            interaction_type="autonomous_terminal",
            expected_tool_calls_typical=40,
            expected_human_minutes=45,
            ambiguity="medium",
            requires_planning=True,
            requires_code_execution=True,
            requires_recovery=True,
        ),
        budgets=Budget(max_wall_clock_seconds=3600, max_total_tokens=600_000, max_estimated_usd=10.0, max_tool_calls=200, max_llm_calls=100),
        success_criteria=SuccessCriteria(type="unit_tests", checker="swebench_harness", notes="FAIL_TO_PASS/PASS_TO_PASS tests from SWE-bench."),
        tags=["coding", "terminal", "unit-tests", "public"],
        raw={"instance_id": instance_id, "FAIL_TO_PASS": fail_to_pass, "PASS_TO_PASS": pass_to_pass},
    )


def normalize_assistantbench(row: dict[str, Any], split: str = "dev") -> BenchmarkTask:
    task_id = str(row.get("id") or row.get("task_id") or hashlib.sha1(json.dumps(row, sort_keys=True).encode()).hexdigest()[:12])
    question = str(row.get("question") or row.get("instruction") or row.get("query") or row.get("task") or "")
    return BenchmarkTask(
        task_id=f"assistantbench__{task_id}",
        source="AssistantBench/AssistantBench",
        source_type="huggingface",
        source_url="https://huggingface.co/datasets/AssistantBench/AssistantBench",
        category="web_research",
        domain="open_web_qa",
        instruction=question,
        environment={"type": "web", "split": split},
        complexity=Complexity(
            horizon="medium",
            interaction_type="autonomous_web",
            expected_tool_calls_typical=12,
            expected_human_minutes=20,
            ambiguity="medium",
            requires_planning=True,
            requires_external_search=True,
        ),
        budgets=Budget(max_wall_clock_seconds=1200, max_total_tokens=250_000, max_estimated_usd=3.0, max_tool_calls=60, max_llm_calls=30),
        success_criteria=SuccessCriteria(type="structured_answer", checker="assistantbench_exact_or_rubric"),
        tags=["web", "research", "qa", "public", split],
        raw={k: row.get(k) for k in ("id", "answer", "answer_type", "urls", "explanation") if k in row},
    )


def _loose_yaml_field(yaml_text: str, field: str) -> str | None:
    prefix = f"{field}:"
    lines = yaml_text.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
            if value in {"|", ">"}:
                block: list[str] = []
                for follow in lines[idx + 1 :]:
                    if follow and not follow.startswith((" ", "\t")):
                        break
                    block.append(follow.strip())
                return "\n".join(block).strip()
            return value.strip('"\'')
    return None


def normalize_terminal_bench_task(task_id: str, yaml_text: str, source_url: str | None = None) -> BenchmarkTask:
    try:
        doc = yaml.safe_load(yaml_text) or {}
        if not isinstance(doc, dict):
            doc = {}
    except yaml.YAMLError:
        doc = {}
    instruction = doc.get("instruction") or doc.get("description") or doc.get("base_description") or doc.get("task") or _loose_yaml_field(yaml_text, "instruction") or _loose_yaml_field(yaml_text, "description") or f"Complete Terminal-Bench task {task_id}."
    timeout = int(float(doc.get("max_agent_timeout_sec") or doc.get("timeout_sec") or _loose_yaml_field(yaml_text, "max_agent_timeout_sec") or 1800))
    tags = [str(tag) for tag in doc.get("tags") or []]
    difficulty = str(doc.get("difficulty") or _loose_yaml_field(yaml_text, "difficulty") or "unknown")
    typical_calls = {"easy": 15, "medium": 30, "hard": 60}.get(difficulty.lower(), 30)
    return BenchmarkTask(
        task_id=f"terminal_bench__{task_id}",
        source="harbor-framework/terminal-bench",
        source_type="github",
        source_url=source_url,
        category="terminal_work",
        domain=doc.get("category") or difficulty,
        instruction=str(instruction),
        environment={"type": "terminal_container", "task_id": task_id, "difficulty": difficulty},
        complexity=Complexity(
            horizon=_horizon_from_tool_calls(typical_calls),
            interaction_type="autonomous_terminal",
            expected_tool_calls_typical=typical_calls,
            expected_human_minutes={"easy": 15, "medium": 45, "hard": 90}.get(difficulty.lower(), 45),
            ambiguity="medium",
            requires_planning=True,
            requires_code_execution=True,
            requires_recovery=True,
        ),
        budgets=Budget(max_wall_clock_seconds=timeout, max_total_tokens=750_000, max_estimated_usd=15.0, max_tool_calls=250, max_llm_calls=120),
        success_criteria=SuccessCriteria(type="container_tests", checker="terminal_bench_harness"),
        tags=["terminal", "container", "public", *tags],
        raw={"difficulty": difficulty, "yaml_keys": sorted(doc.keys())},
    )


def load_huggingface_subset(spec: dict[str, Any]) -> list[BenchmarkTask]:
    ds = load_dataset(spec["dataset_id"], split=spec.get("split", "train"))
    sample_size = int(spec.get("sample_size", 10))
    normalizer = spec["normalizer"]
    rows = _stable_sample(ds, sample_size, lambda row: row.get("instance_id") or row.get("id") or json.dumps(row, sort_keys=True)[:200])
    if normalizer == "swe_bench":
        return [normalize_swe_bench(dict(row)) for row in rows]
    raise ValueError(f"unsupported Hugging Face normalizer: {normalizer}")


def load_huggingface_jsonl_subset(spec: dict[str, Any]) -> list[BenchmarkTask]:
    response = requests.get(spec["url"], timeout=30)
    response.raise_for_status()
    rows = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    sample_size = int(spec.get("sample_size", 10))
    rows = _stable_sample(rows, sample_size, lambda row: row.get("id") or json.dumps(row, sort_keys=True)[:200])
    if spec["normalizer"] == "assistantbench":
        return [normalize_assistantbench(row, split=spec.get("split", "dev")) for row in rows]
    raise ValueError(f"unsupported JSONL normalizer: {spec['normalizer']}")


def _github_tree(repo: str, branch: str) -> list[dict[str, Any]]:
    url = f"{GITHUB_API}/repos/{repo}/git/trees/{branch}?recursive=1"
    response = requests.get(url, timeout=30, headers={"Accept": "application/vnd.github+json"})
    response.raise_for_status()
    return response.json().get("tree", [])


def load_terminal_bench_github_subset(spec: dict[str, Any]) -> list[BenchmarkTask]:
    repo = spec["repo"]
    branch = spec.get("branch", "main")
    tree = _github_tree(repo, branch)
    yaml_paths = [item["path"] for item in tree if item.get("type") == "blob" and item.get("path", "").endswith("task.yaml")]
    if not yaml_paths:
        yaml_paths = [item["path"] for item in tree if item.get("type") == "blob" and item.get("path", "").endswith("task.yml")]
    sample_size = int(spec.get("sample_size", 10))
    sampled_paths = _stable_sample(yaml_paths, sample_size, lambda path: path)
    tasks = []
    for path in sampled_paths:
        raw_url = f"{RAW_GITHUB}/{repo}/{branch}/{path}"
        response = requests.get(raw_url, timeout=30)
        response.raise_for_status()
        task_id = path.split("/")[-2] if "/" in path else path.rsplit(".", 1)[0]
        tasks.append(normalize_terminal_bench_task(task_id, response.text, source_url=raw_url))
    return tasks


def load_source(spec: dict[str, Any]) -> list[BenchmarkTask]:
    source_type = spec["type"]
    if source_type == "huggingface":
        return load_huggingface_subset(spec)
    if source_type == "huggingface_jsonl":
        return load_huggingface_jsonl_subset(spec)
    if source_type == "github_terminal_bench":
        return load_terminal_bench_github_subset(spec)
    raise ValueError(f"unsupported source type: {source_type}")


def load_sources_from_config(config_path: str) -> list[BenchmarkTask]:
    with open(config_path, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    tasks: list[BenchmarkTask] = []
    for spec in config.get("sources", []):
        tasks.extend(load_source(spec))
    return tasks
