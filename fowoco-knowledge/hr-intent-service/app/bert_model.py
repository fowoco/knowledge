"""klue/roberta-base Full Fine-tuning 모델 로드 및 추론."""

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


class BertIntentModel:
    def __init__(self, model_dir: str, device: str, label_prob_threshold: float = 0.55, hf_token: str | None = None, ):
        self.device = "cuda" if (device == "auto" and torch.cuda.is_available()) else (
            device if device != "auto" else "cpu"
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, token=hf_token)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir, token=hf_token)
        self.model.to(self.device).eval()
        self.id2label = self.model.config.id2label
        self.label_prob_threshold = label_prob_threshold

    @torch.no_grad()
    def predict(self, text: str) -> tuple[dict[str, float], float, list[str]]:
        """확률 딕셔너리, margin, 활성화된 intent 리스트를 반환.

        margin: 활성화(threshold 이상)된 것 중 최저 확률 - 비활성화된 것 중 최고 확률.
        """
        enc = self.tokenizer(text, truncation=True, max_length=64, return_tensors="pt").to(
            self.device
        )
        logits = self.model(**enc).logits
        probs_array = torch.sigmoid(logits)[0].cpu().numpy()
        probs_dict = {self.id2label[i]: float(p) for i, p in enumerate(probs_array)}

        activated = [p for p in probs_array if p >= self.label_prob_threshold]
        not_activated = [p for p in probs_array if p < self.label_prob_threshold]

        if not activated:
            margin = float(max(probs_array)) - self.label_prob_threshold
        else:
            margin = float(min(activated)) - (float(max(not_activated)) if not_activated else 0.0)

        picked = [self.id2label[i] for i, p in enumerate(probs_array) if p >= self.label_prob_threshold]
        if not picked:
            picked = [self.id2label[int(probs_array.argmax())]]

        return probs_dict, margin, picked