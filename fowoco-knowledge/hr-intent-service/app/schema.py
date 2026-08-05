"""BERT와 A.X의 서로 다른 출력 구조(evidence 유무, score 유무)를 하나의 응답 스키마로 통합한다."""

import time
from typing import Literal

from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=150)


class IntentItem(BaseModel):
    intent: str
    evidence: str | None = None  # BERT는 항상 None, A.X는 문자열 또는 None(OUT_OF_SCOPE)
    score: float | None = None  # BERT는 sigmoid 확률, A.X는 확률을 안 내므로 None


class ResponseMeta(BaseModel):
    selected_model: Literal["BERT", "AX", "BERT_FALLBACK"]
    routing_category: str
    routing_reason: str
    degraded: bool  # A.X 라우팅 대상이었으나 A.X 호출 실패로 BERT 결과를 대신 반환한 경우
    bert_margin: float
    bert_all_scores: dict[str, float]  # 항상 기록 (A.X로 넘어간 경우도 라우팅 재검증용으로 필요)
    device: str
    latency_ms: float


class ClassifyResponse(BaseModel):
    input: str
    intents: list[IntentItem]
    meta: ResponseMeta


def format_bert_output(
    hr_input: str,
    bert_intents: list[str],
    all_scores: dict[str, float],
    margin: float,
    device: str,
    start_time: float,
    degraded: bool = False,
    routing_category: str = "Pass_BERT",
    routing_reason: str = "BERT 신뢰 구간 통과",
) -> ClassifyResponse:
    return ClassifyResponse(
        input=hr_input,
        intents=[
            IntentItem(intent=name, evidence=None, score=round(all_scores[name], 4))
            for name in bert_intents
        ],
        meta=ResponseMeta(
            selected_model="BERT_FALLBACK" if degraded else "BERT",
            routing_category=routing_category,
            routing_reason=routing_reason,
            degraded=degraded,
            bert_margin=round(margin, 4),
            bert_all_scores={k: round(v, 4) for k, v in all_scores.items()},
            device=device,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 1),
        ),
    )


def format_ax_output(
    hr_input: str,
    ax_intents: list[dict],
    all_scores: dict[str, float],
    margin: float,
    device: str,
    start_time: float,
    routing_category: str,
    routing_reason: str,
) -> ClassifyResponse:
    return ClassifyResponse(
        input=hr_input,
        intents=[
            IntentItem(
                intent=item["intent"],
                evidence=item.get("evidence"),
                score=None,
            )
            for item in ax_intents
        ],
        meta=ResponseMeta(
            selected_model="AX",
            routing_category=routing_category,
            routing_reason=routing_reason,
            degraded=False,
            bert_margin=round(margin, 4),
            bert_all_scores={k: round(v, 4) for k, v in all_scores.items()},
            device=device,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 1),
        ),
    )