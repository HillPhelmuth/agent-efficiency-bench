from __future__ import annotations

import json
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


def write_prediction(predictions_path: str | Path, instance_id: str, model_patch: str, model_name_or_path: str) -> None:
    path = Path(predictions_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "instance_id": instance_id,
        "model_name_or_path": model_name_or_path,
        "model_patch": model_patch,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def parse_swe_bench_result(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)
