from pathlib import Path

import yaml


CONFIG_DIR = Path("configs")


def _load_config(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8"))


def test_named_source_configs_parse_and_use_expected_sources():
    expected_names = [
        "swe_bench_lite",
        "assistantbench_dev",
        "terminal_bench_github",
        "tau2_bench_retail",
        "tau2_bench_airline",
    ]
    expected_types = {
        "swe_bench_lite": "huggingface",
        "assistantbench_dev": "huggingface_jsonl",
        "terminal_bench_github": "github_terminal_bench",
        "tau2_bench_retail": "github_tau2_bench",
        "tau2_bench_airline": "github_tau2_bench",
    }

    for config_name in ("sources-smoke.yaml", "sources-dev.yaml", "sources-release.yaml"):
        config = _load_config(config_name)
        specs = config["sources"]
        assert [spec["name"] for spec in specs] == expected_names
        assert {spec["name"]: spec["type"] for spec in specs} == expected_types


def test_dev_alias_matches_sources_dev_config():
    assert _load_config("sources.yaml") == _load_config("sources-dev.yaml")


def test_source_config_sample_sizes_increase_from_smoke_to_release():
    smoke = {spec["name"]: spec["sample_size"] for spec in _load_config("sources-smoke.yaml")["sources"]}
    dev = {spec["name"]: spec["sample_size"] for spec in _load_config("sources-dev.yaml")["sources"]}
    release = {spec["name"]: spec["sample_size"] for spec in _load_config("sources-release.yaml")["sources"]}

    for name, smoke_size in smoke.items():
        assert smoke_size == 1
        assert dev[name] >= smoke_size
        assert release[name] >= dev[name]