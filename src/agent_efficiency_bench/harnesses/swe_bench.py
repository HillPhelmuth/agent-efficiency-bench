from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_SWE_BENCH_DATASET = "SWE-bench/SWE-bench_Lite"


def patch_path_for_task(output_dir: str | Path, instance_id: str) -> Path:
    return Path(output_dir) / f"{instance_id}.patch"


def build_swe_bench_eval_command(
    predictions_path: str,
    run_id: str,
    dataset_name: str = DEFAULT_SWE_BENCH_DATASET,
) -> list[str]:
    return [
        "python",
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        dataset_name,
        "--predictions_path",
        predictions_path,
        "--run_id",
        run_id,
    ]


def build_prediction_row(instance_id: str, model_patch: str, model_name_or_path: str) -> dict[str, str]:
    return {
        "instance_id": instance_id,
        "model_name_or_path": model_name_or_path,
        "model_patch": model_patch,
    }


def write_prediction(
    predictions_path: str | Path,
    instance_id: str,
    model_patch: str,
    model_name_or_path: str,
    *,
    append: bool = True,
) -> None:
    path = Path(predictions_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = build_prediction_row(instance_id=instance_id, model_patch=model_patch, model_name_or_path=model_name_or_path)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def check_swe_bench_prerequisites(require_package: bool = True) -> dict[str, bool]:
    prerequisites = {"python": shutil.which("python") is not None}
    if require_package:
        prerequisites["swebench"] = importlib.util.find_spec("swebench") is not None
    return prerequisites


def run_swe_bench_evaluation(
    predictions_path: str,
    run_id: str,
    dataset_name: str = DEFAULT_SWE_BENCH_DATASET,
    dry_run: bool = True,
    execute: bool = False,
    report_path: str | Path | None = None,
    suite_budget: dict[str, Any] | None = None,
    subprocess_run=subprocess.run,
) -> dict[str, Any]:
    prerequisites = check_swe_bench_prerequisites(require_package=execute)
    command = build_swe_bench_eval_command(predictions_path=predictions_path, run_id=run_id, dataset_name=dataset_name)
    report_file = Path(report_path) if report_path is not None else Path(predictions_path).with_name(f"{run_id}-report.json")
    payload = {
        "predictions_path": predictions_path,
        "run_id": run_id,
        "dataset_name": dataset_name,
        "command": command,
        "prerequisites": prerequisites,
        "dry_run": dry_run,
        "execute": execute,
        "report_path": str(report_file),
        "suite_budget": suite_budget or {},
    }

    if dry_run and not execute:
        payload["ready"] = all(prerequisites.values())
        return payload

    if not execute:
        raise ValueError("SWE-bench execution requires explicit execute=True")

    missing = [name for name, available in prerequisites.items() if not available]
    if missing:
        raise RuntimeError(f"Missing SWE-bench prerequisites: {', '.join(missing)}")

    completed = subprocess_run(command, capture_output=True, text=True, check=False)
    payload.update(
        {
            "ready": True,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    )
    if report_file.exists():
        payload["parsed_report"] = parse_swe_bench_report(report_file)
    return payload


def parse_swe_bench_report(path: str | Path) -> dict[str, Any]:
    report_path = Path(path)
    with report_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    resolved = _normalize_instance_ids(_first_present(raw, "resolved_ids", "resolved_instances", "resolved"))
    unresolved = _normalize_instance_ids(_first_present(raw, "unresolved_ids", "unresolved_instances", "unresolved"))
    total = len(resolved) + len(unresolved)
    return {
        "resolved_instances": resolved,
        "unresolved_instances": unresolved,
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "success_rate": (len(resolved) / total) if total else 0.0,
        "raw": raw,
    }


def parse_swe_bench_result(path: str | Path) -> dict[str, Any]:
    return parse_swe_bench_report(path)


def _first_present(raw: Any, *keys: str) -> Any:
    if not isinstance(raw, dict):
        return None
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    summary = raw.get("summary")
    if isinstance(summary, dict):
        for key in keys:
            if key in summary and summary[key] is not None:
                return summary[key]
    return None


def _normalize_instance_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
