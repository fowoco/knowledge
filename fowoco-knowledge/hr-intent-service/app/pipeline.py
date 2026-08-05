"""BERT + 가드레일 + A.X를 조합하는 하이브리드 추론 파이프라인."""

import logging
import time

from .ax_model import AxIntentModel
from .bert_model import BertIntentModel
from .config import Settings
from .guardrail import HRRoutingGuardrail
from .schema import ClassifyResponse, format_ax_output, format_bert_output

logger = logging.getLogger(__name__)


class HybridIntentPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings

        logger.info("Loading BERT model from %s", settings.bert_model_dir)
        self.bert = BertIntentModel(
            model_dir=settings.bert_model_dir,
            device=settings.device,
            label_prob_threshold=settings.label_prob_threshold,
            hf_token=settings.hf_token,
        )

        self.guardrail = HRRoutingGuardrail(
            margin_threshold=settings.margin_threshold,
            max_trained_labels=settings.max_trained_labels,
            label_prob_threshold=settings.label_prob_threshold,
        )

        # A.X는 선택적으로 로드한다 — 실패해도 BERT만으로 서비스가 뜨도록 한다.
        self.ax: AxIntentModel | None = None
        if settings.enable_ax :
            try:
                logger.info("Loading A.X model (adapter: %s)", settings.ax_adapter_path)
                self.ax = AxIntentModel(
                    base_model_name=settings.ax_base_model_name,
                    adapter_path=settings.ax_adapter_path,
                    device=settings.device,
                    max_new_tokens=settings.ax_max_new_tokens,
                    hf_token=settings.hf_token,
                )
            except Exception:
                logger.exception(
                    "A.X model failed to load. Service starts in BERT-only degraded mode."
                )
        else :
            logger.info("A.X disabled via settings (enable_ax=False). BERT-only mode.")

    @property
    def ax_available(self) -> bool:
        return self.ax is not None

    def predict(self, instruction: str) -> ClassifyResponse:
        start = time.perf_counter()
        probs, margin, bert_intents = self.bert.predict(instruction)
        route = self.guardrail.should_route_to_ax(instruction, probs, margin)

        if route.should_route and self.ax_available:
            try:
                ax_intents = self.ax.predict(instruction)
                return format_ax_output(
                    hr_input=instruction,
                    ax_intents=ax_intents,
                    all_scores=probs,
                    margin=margin,
                    device=self.bert.device,
                    start_time=start,
                    routing_category=route.category,
                    routing_reason=route.reason,
                )
            except Exception:
                logger.exception("A.X inference failed for input, falling back to BERT")
                # 아래로 흘러서 degraded BERT 응답 반환

        degraded = route.should_route  # 넘겨야 했는데 A.X를 못 쓴 경우만 True
        return format_bert_output(
            hr_input=instruction,
            bert_intents=bert_intents,
            all_scores=probs,
            margin=margin,
            device=self.bert.device,
            start_time=start,
            degraded=degraded,
            routing_category=route.category,
            routing_reason=route.reason,
        )