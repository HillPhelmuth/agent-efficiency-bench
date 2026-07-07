from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

from pydantic import BaseModel, Field

from agent_efficiency_bench.evaluators.base import EvaluationScore
from agent_efficiency_bench.providers.openrouter import OpenRouterClient
from agent_efficiency_bench.scoring import LIKERT_SCORE_MAX, UNEVALUATED_QUALITY_SCORE, coerce_quality_score
from agent_efficiency_bench.schemas import BenchmarkTask, ModelConfig, RunResult

DEFAULT_JUDGE_MODEL = "deepseek/deepseek-v4-flash"


class LLMJudgeScore(BaseModel):
    success: bool
    quality_score: float = Field(ge=1.0, le=LIKERT_SCORE_MAX)
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class LLMJudge(Protocol):
    def judge(self, *, instruction: str, answer: str, citations: list[str]) -> LLMJudgeScore: ...


class OpenRouterLLMJudge:
    """Cheap OpenRouter-backed judge for answer correctness without brittle string matching."""

    def __init__(
        self,
        model: str | None = None,
        client: OpenRouterClient | None = None,
        max_completion_tokens: int = 2048,
    ):
        self.model = model or os.getenv("AEB_LLM_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
        self.client = client or OpenRouterClient()
        self.max_completion_tokens = max_completion_tokens

    def judge(self, *, instruction: str, answer: str, citations: list[str]) -> LLMJudgeScore:
        response = self.client.chat(
            ModelConfig(
                model=self.model,
                temperature=0.0,
                max_completion_tokens=self.max_completion_tokens,
                extra={"response_format": {"type": "json_object"}},
            ),
            [
                {
                    "role": "system",
                    "content": (
                        "You are a strict but fair benchmark judge. Decide whether the submitted answer "
                        "contains a correct current answer to the user task. Do not require exact wording. "
                        "Prefer current, cited evidence over any stale benchmark answer key. Return only JSON "
                        "with keys: success (boolean), quality_score (1..5 Likert scale, where 1=poor/incorrect and 5=fully correct), reason (short string)."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": instruction,
                            "submitted_answer": answer,
                            "citations": citations,
                            "rubric": [
                                "The answer directly addresses the task asked.",
                                "The answer's final conclusion is supported by its cited sources or explicit reasoning.",
                                "Do not penalize formatting or wording differences.",
                                "Mark false if the answer refuses despite enough information, is internally inconsistent, or gives an unsupported final answer.",
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        return _parse_judge_response(response.content)


class LLMAnswerJudgeEvaluator:
    """Evaluate open-ended web-research answers with an LLM judge instead of stale string keys."""

    def __init__(self, judge: LLMJudge | None = None):
        self.judge = judge

    def evaluate(self, task: BenchmarkTask, result: RunResult) -> EvaluationScore:
        answer = str(result.output.get("answer") or "").strip()
        citations = _collect_citations(result.output, answer)
        if not answer:
            return EvaluationScore(success=False, quality_score=1.0, reason="missing answer")
        if _requires_citation(task) and not citations:
            return EvaluationScore(
                success=False,
                quality_score=1.0,
                reason="missing citation",
                details={"citations": citations, "judge": "not_called"},
            )
        try:
            judge = self.judge or OpenRouterLLMJudge()
            score = judge.judge(instruction=task.instruction, answer=answer, citations=citations)
        except ValueError as exc:
            return EvaluationScore(
                evaluated=False,
                success=False,
                quality_score=UNEVALUATED_QUALITY_SCORE,
                reason="LLM judge unavailable",
                details={"error": str(exc)},
            )
        return EvaluationScore(
            success=score.success,
            quality_score=score.quality_score,
            reason=score.reason or ("LLM judge passed" if score.success else "LLM judge failed"),
            details={"judge": "llm", "citations": citations, **score.details},
        )


def _parse_judge_response(content: str) -> LLMJudgeScore:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return LLMJudgeScore(success=False, quality_score=1.0, reason="Judge returned non-JSON response")
        payload = json.loads(match.group(0))
    success = bool(payload.get("success"))
    return LLMJudgeScore(
        success=success,
        quality_score=coerce_quality_score(payload.get("quality_score"), success=success),
        reason=str(payload.get("reason") or "LLM judge result"),
        details={key: value for key, value in payload.items() if key not in {"success", "quality_score", "reason"}},
    )


def _requires_citation(task: BenchmarkTask) -> bool:
    expected = task.raw.get("expected") if isinstance(task.raw, dict) else None
    if isinstance(expected, dict) and expected.get("requires_citation"):
        return True
    return bool(task.complexity.requires_external_search)


def _collect_citations(output: dict[str, Any], answer: str) -> list[str]:
    citations = list(output.get("citations") or [])
    for annotation in output.get("annotations") or []:
        if not isinstance(annotation, dict):
            continue
        citation = annotation.get("url_citation") or {}
        url = citation.get("url") if isinstance(citation, dict) else None
        if url and url not in citations:
            citations.append(url)
    for url in _urls_in_text(answer):
        if url not in citations:
            citations.append(url)
    return citations


def _urls_in_text(text: str) -> list[str]:
    return [match.rstrip(".,;:)]}>'\"*") for match in re.findall(r"https?://\S+", text)]
