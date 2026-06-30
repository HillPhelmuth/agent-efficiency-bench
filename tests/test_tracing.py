import json

from agent_efficiency_bench.tracing import TraceRecorder


def test_trace_recorder_writes_jsonl_events(tmp_path):
    path = tmp_path / "trace.jsonl"
    recorder = TraceRecorder(path=path, run_id="r1", task_id="t1")

    recorder.emit("task_start", data={"x": 1})
    recorder.emit("task_end", data={"success": True})

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["event"] for row in rows] == ["task_start", "task_end"]
    assert rows[0]["run_id"] == "r1"
    assert rows[0]["task_id"] == "t1"
    assert rows[1]["t_rel_seconds"] >= rows[0]["t_rel_seconds"]
