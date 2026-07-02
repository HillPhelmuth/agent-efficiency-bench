from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from agent_efficiency_bench.schemas import BenchmarkTask


@dataclass
class AuditWarning:
    task_id: str
    code: str
    message: str


@dataclass
class TaskAudit:
    total_tasks: int
    counts: dict[str, dict[str, int]]
    requirements: dict[str, int]
    warnings: list[AuditWarning] = field(default_factory=list)


def audit_tasks(tasks: list[BenchmarkTask], min_instruction_chars: int = 20) -> TaskAudit:
    counts = {
        "source": dict(Counter(task.source for task in tasks)),
        "category": dict(Counter(task.category for task in tasks)),
        "horizon": dict(Counter(task.complexity.horizon for task in tasks)),
        "interaction_type": dict(Counter(task.complexity.interaction_type for task in tasks)),
        "success_criteria_type": dict(Counter(task.success_criteria.type for task in tasks)),
    }
    requirements = {
        "requires_external_search": sum(1 for task in tasks if task.complexity.requires_external_search),
        "requires_code_execution": sum(1 for task in tasks if task.complexity.requires_code_execution),
        "requires_recovery": sum(1 for task in tasks if task.complexity.requires_recovery),
    }
    warnings: list[AuditWarning] = []
    for task in tasks:
        warnings.extend(_warnings_for_task(task, min_instruction_chars=min_instruction_chars))
    return TaskAudit(total_tasks=len(tasks), counts=counts, requirements=requirements, warnings=warnings)


def _warnings_for_task(task: BenchmarkTask, min_instruction_chars: int) -> list[AuditWarning]:
    warnings = []
    instruction = task.instruction.strip()
    if len(instruction) < min_instruction_chars:
        warnings.append(
            AuditWarning(
                task_id=task.task_id,
                code="short_instruction",
                message=f"Instruction has fewer than {min_instruction_chars} characters.",
            )
        )
    if instruction in {"|-", "TODO", "TBD", "N/A"}:
        warnings.append(
            AuditWarning(
                task_id=task.task_id,
                code="placeholder_instruction",
                message="Instruction appears to be a placeholder.",
            )
        )
    if task.success_criteria.type == "manual":
        warnings.append(
            AuditWarning(
                task_id=task.task_id,
                code="manual_evaluator",
                message="Task uses manual success criteria and has no deterministic evaluator.",
            )
        )
    if task.success_criteria.type in {"structured_answer", "exact"} and not task.raw.get("answer"):
        warnings.append(
            AuditWarning(
                task_id=task.task_id,
                code="missing_expected_answer",
                message="Structured/exact task is missing raw.answer metadata.",
            )
        )
    return warnings


def format_audit_markdown(audit: TaskAudit) -> str:
    lines = ["# Task Audit", "", f"Total tasks: {audit.total_tasks}", ""]
    for section, values in audit.counts.items():
        lines.extend([f"## Count by {section}", "", "| value | count |", "|---|---:|"])
        for value, count in sorted(values.items()):
            lines.append(f"| {value} | {count} |")
        lines.append("")
    lines.extend(["## Requirement Counts", "", "| requirement | count |", "|---|---:|"])
    for key, value in sorted(audit.requirements.items()):
        lines.append(f"| {key} | {value} |")
    lines.append("")
    lines.extend(["## Warnings", "", "| task_id | code | message |", "|---|---|---|"])
    if audit.warnings:
        for warning in audit.warnings:
            lines.append(f"| {warning.task_id} | {warning.code} | {warning.message} |")
    else:
        lines.append("| - | - | No warnings |")
    lines.append("")
    return "\n".join(lines)
