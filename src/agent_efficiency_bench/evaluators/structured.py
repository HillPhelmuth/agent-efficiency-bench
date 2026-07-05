from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from agent_efficiency_bench.evaluators.base import EvaluationScore
from agent_efficiency_bench.scoring import LIKERT_SCORE_MIN, normalized_to_likert


class StructuredAnswerEvaluator:
    """Deterministic evaluator for web-research answers with citation checks."""

    def __init__(self, expected: dict[str, Any]):
        self.expected = expected

    def evaluate(self, task: Any, result: Any) -> EvaluationScore:
        answer = str(result.output.get("answer") or "")
        citations = _collect_citations(result.output)
        for url in _urls_in_text(answer):
            if url not in citations:
                citations.append(url)
        checks = {
            "text_contains": _check_text_contains(answer, self.expected.get("text_contains") or []),
            "numbers": _check_numbers(answer, self.expected.get("numbers") or []),
            "required_domains": _check_required_domains(answer, citations, self.expected.get("required_domains") or []),
        }
        if self.expected.get("requires_citation"):
            checks["requires_citation"] = {"passed": bool(citations), "citations": citations}

        passed, total = _count_checks(checks)
        success = total > 0 and passed == total
        return EvaluationScore(
            success=success,
            quality_score=normalized_to_likert(passed / total) if total else LIKERT_SCORE_MIN,
            reason="structured checks passed" if success else "structured checks failed",
            details={"checks": checks, "passed_checks": passed, "total_checks": total},
        )


def _check_text_contains(answer: str, expected_values: list[str]) -> list[dict[str, Any]]:
    normalized = answer.casefold()
    checks = []
    for value in expected_values:
        expected_parts = _expected_text_parts(str(value))
        checks.append(
            {
                "expected": value,
                "expected_parts": expected_parts,
                "passed": all(part.casefold() in normalized for part in expected_parts),
            }
        )
    return checks


def _check_numbers(answer: str, expected_numbers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actual_numbers = [float(match) for match in re.findall(r"(?<!\w)-?\d+(?:\.\d+)?", answer)]
    checks = []
    for spec in expected_numbers:
        expected = float(spec["value"])
        tolerance = float(spec.get("tolerance", 0.0))
        closest = min(actual_numbers, key=lambda value: abs(value - expected), default=None)
        passed = closest is not None and abs(closest - expected) <= tolerance
        checks.append(
            {
                "label": spec.get("label"),
                "expected": expected,
                "tolerance": tolerance,
                "closest_actual": closest,
                "passed": passed,
            }
        )
    return checks


def _check_required_domains(answer: str, citations: list[str], required_domains: list[str]) -> list[dict[str, Any]]:
    observed = {_domain(value) for value in citations + _urls_in_text(answer)}
    observed = {domain for domain in observed if domain}
    checks = []
    for required in required_domains:
        normalized_required = _normalize_domain(required)
        passed = any(domain == normalized_required or domain.endswith(f".{normalized_required}") for domain in observed)
        checks.append({"expected_domain": required, "observed_domains": sorted(observed), "passed": passed})
    return checks


def _collect_citations(output: dict[str, Any]) -> list[str]:
    citations = list(output.get("citations") or [])
    for annotation in output.get("annotations") or []:
        citation = annotation.get("url_citation") or {}
        url = citation.get("url")
        if url and url not in citations:
            citations.append(url)
    return citations


def _urls_in_text(text: str) -> list[str]:
    return [_clean_url(match) for match in re.findall(r"https?://\S+", text)]


def _clean_url(value: str) -> str:
    return value.rstrip(".,;:)]}>'\"*")


def _expected_text_parts(value: str) -> list[str]:
    parts = [part.strip() for part in value.splitlines() if part.strip()]
    return parts or [value]


def _domain(value: str) -> str:
    return _normalize_domain(urlparse(value).netloc or value)


def _normalize_domain(value: str) -> str:
    value = value.casefold().strip().removeprefix("www.")
    return value.split("/")[0]


def _count_checks(checks: dict[str, Any]) -> tuple[int, int]:
    passed = 0
    total = 0
    for value in checks.values():
        if isinstance(value, list):
            for item in value:
                total += 1
                passed += 1 if item.get("passed") else 0
        elif isinstance(value, dict):
            total += 1
            passed += 1 if value.get("passed") else 0
    return passed, total
