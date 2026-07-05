from __future__ import annotations

LIKERT_SCORE_MIN = 1.0
LIKERT_SCORE_MAX = 5.0
UNEVALUATED_QUALITY_SCORE = 0.0


def likert_score(success: bool) -> float:
    return LIKERT_SCORE_MAX if success else LIKERT_SCORE_MIN


def normalized_to_likert(score: float) -> float:
    normalized = float(score)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"normalized score must be between 0 and 1, got {score!r}")
    return LIKERT_SCORE_MIN + ((LIKERT_SCORE_MAX - LIKERT_SCORE_MIN) * normalized)


def coerce_quality_score(score: float | int | None, *, success: bool | None = None) -> float:
    if score is None:
        if success is None:
            raise ValueError("success is required when score is omitted")
        return likert_score(success)

    numeric = float(score)
    if numeric == UNEVALUATED_QUALITY_SCORE:
        return LIKERT_SCORE_MIN
    if 0.0 < numeric < 1.0:
        return normalized_to_likert(numeric)
    if numeric == 1.0:
        if success is False:
            return LIKERT_SCORE_MIN
        return LIKERT_SCORE_MAX
    if LIKERT_SCORE_MIN <= numeric <= LIKERT_SCORE_MAX:
        return numeric
    raise ValueError(f"quality score must be within legacy 0-1 or Likert 1-5 bounds, got {score!r}")


def coerce_persisted_quality_score(score: float | int, *, success: bool, terminated_by: str | None = None) -> float:
    numeric = float(score)
    if terminated_by == "not_evaluated":
        return numeric
    if 0.0 <= numeric <= 1.0:
        return coerce_quality_score(numeric, success=success)
    return numeric