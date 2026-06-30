from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from agent_efficiency_bench.schemas import TraceEvent


class TraceRecorder:
    """Append-only JSONL trace writer for benchmark runs."""

    def __init__(self, path: str | Path, run_id: str, task_id: str):
        self.path = Path(path)
        self.run_id = run_id
        self.task_id = task_id
        self.started_at = time.perf_counter()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        event: str,
        data: dict[str, Any] | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> TraceEvent:
        trace_event = TraceEvent(
            t_rel_seconds=time.perf_counter() - self.started_at,
            event=event,
            task_id=self.task_id,
            run_id=self.run_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            data=data or {},
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(trace_event.model_dump_json(exclude_none=True) + "\n")
            fh.flush()
        return trace_event
