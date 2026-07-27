from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from .ingestion import file_sha256
from .intent_model import validate_intent_model_output
from .intent_split import load_intent_cases, read_split_ids

INTENT_CODES = (
    "WORK_INSTRUCTION",
    "DOCUMENT_REQUEST",
    "PAYROLL_EXPLANATION",
    "WORKER_ONBOARDING",
    "EMPLOYMENT_CHANGE",
    "EXPIRY_RENEWAL",
    "OUT_OF_SCOPE",
)
WORKER_ID_PATTERN = re.compile(r"(?i)\bwrk[-_ ]?\d+\b")
TOKEN_PATTERN = re.compile(r"\S+")
DEFAULT_OUTPUT_DIR = Path("data/experiments/intent/provisional-char-ngram-nb-v1")


class ProvisionalBaselineError(ValueError):
    """Raised when the provisional baseline cannot run reproducibly."""


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def normalize_text(text: str) -> str:
    normalized = WORKER_ID_PATTERN.sub("<WORKER>", text)
    return " ".join(normalized.casefold().split())


def char_ngrams(text: str, ngram_min: int, ngram_max: int) -> Counter[str]:
    normalized = normalize_text(text)
    features: Counter[str] = Counter()
    for ngram_size in range(ngram_min, ngram_max + 1):
        for start in range(max(0, len(normalized) - ngram_size + 1)):
            feature = normalized[start : start + ngram_size]
            if feature.strip():
                features[feature] += 1
    return features


def _feature_log_odds(
    positive_texts: list[str],
    negative_texts: list[str],
    *,
    ngram_min: int,
    ngram_max: int,
    alpha: float,
) -> tuple[float, dict[str, float]]:
    positive_counts: Counter[str] = Counter()
    negative_counts: Counter[str] = Counter()
    for text in positive_texts:
        positive_counts.update(char_ngrams(text, ngram_min, ngram_max))
    for text in negative_texts:
        negative_counts.update(char_ngrams(text, ngram_min, ngram_max))

    vocabulary = set(positive_counts) | set(negative_counts)
    vocabulary_size = max(1, len(vocabulary))
    positive_total = sum(positive_counts.values())
    negative_total = sum(negative_counts.values())
    positive_denominator = positive_total + alpha * vocabulary_size
    negative_denominator = negative_total + alpha * vocabulary_size
    weights = {
        feature: math.log((positive_counts[feature] + alpha) / positive_denominator)
        - math.log((negative_counts[feature] + alpha) / negative_denominator)
        for feature in vocabulary
    }
    prior = math.log((len(positive_texts) + alpha) / (len(negative_texts) + alpha))
    return prior, weights


def _best_training_threshold(scores: list[float], truths: list[bool]) -> float:
    if len(scores) != len(truths) or not scores:
        raise ProvisionalBaselineError("threshold calibration inputs are invalid")
    positive_total = sum(truths)
    if positive_total == 0:
        return math.inf

    grouped: dict[float, list[bool]] = {}
    for score, truth in zip(scores, truths, strict=True):
        grouped.setdefault(score, []).append(truth)

    true_positives = 0
    false_positives = 0
    best_f1 = -1.0
    best_threshold = math.inf
    for threshold in sorted(grouped, reverse=True):
        group = grouped[threshold]
        true_positives += sum(group)
        false_positives += len(group) - sum(group)
        false_negatives = positive_total - true_positives
        denominator = 2 * true_positives + false_positives + false_negatives
        f1 = 2 * true_positives / denominator if denominator else 0.0
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold
    return best_threshold


class CharacterNgramMultilabelNB:
    """Dependency-free provisional lower-bound model for pipeline verification."""

    def __init__(
        self,
        *,
        ngram_min: int = 2,
        ngram_max: int = 5,
        alpha: float = 1.0,
        evidence_max_tokens: int = 6,
    ) -> None:
        if ngram_min < 1 or ngram_max < ngram_min:
            raise ValueError("invalid n-gram range")
        self.ngram_min = ngram_min
        self.ngram_max = ngram_max
        self.alpha = alpha
        self.evidence_max_tokens = evidence_max_tokens
        self.priors: dict[str, float] = {}
        self.weights: dict[str, dict[str, float]] = {}
        self.evidence_weights: dict[str, dict[str, float]] = {}
        self.thresholds: dict[str, float] = {}

    def _score(self, text: str, intent: str) -> float:
        features = char_ngrams(text, self.ngram_min, self.ngram_max)
        weights = self.weights[intent]
        return self.priors[intent] + sum(
            count * weights.get(feature, 0.0) for feature, count in features.items()
        )

    def fit(self, cases: list[dict[str, Any]]) -> CharacterNgramMultilabelNB:
        if not cases:
            raise ProvisionalBaselineError("training cases are empty")
        labels_by_case = [{item["intent"] for item in case["intents"]} for case in cases]
        for intent in INTENT_CODES:
            positive_texts = [
                case["hr_input"]
                for case, labels in zip(cases, labels_by_case, strict=True)
                if intent in labels
            ]
            negative_texts = [
                case["hr_input"]
                for case, labels in zip(cases, labels_by_case, strict=True)
                if intent not in labels
            ]
            if not positive_texts or not negative_texts:
                raise ProvisionalBaselineError(
                    f"{intent}: positive/negative training cases required"
                )
            prior, weights = _feature_log_odds(
                positive_texts,
                negative_texts,
                ngram_min=self.ngram_min,
                ngram_max=self.ngram_max,
                alpha=self.alpha,
            )
            self.priors[intent] = prior
            self.weights[intent] = weights

            positive_evidence = [
                item["evidence"]
                for case in cases
                for item in case["intents"]
                if item["intent"] == intent and isinstance(item["evidence"], str)
            ]
            negative_evidence = [
                item["evidence"]
                for case in cases
                for item in case["intents"]
                if item["intent"] != intent and isinstance(item["evidence"], str)
            ]
            if positive_evidence and negative_evidence:
                _, evidence_weights = _feature_log_odds(
                    positive_evidence,
                    negative_evidence,
                    ngram_min=self.ngram_min,
                    ngram_max=self.ngram_max,
                    alpha=self.alpha,
                )
                self.evidence_weights[intent] = evidence_weights
            else:
                self.evidence_weights[intent] = weights

        for intent in INTENT_CODES:
            scores = [self._score(case["hr_input"], intent) for case in cases]
            truths = [intent in labels for labels in labels_by_case]
            self.thresholds[intent] = _best_training_threshold(scores, truths)
        return self

    def _extract_evidence(self, hr_input: str, intent: str) -> str:
        tokens = list(TOKEN_PATTERN.finditer(hr_input))
        if not tokens:
            return hr_input
        weights = self.evidence_weights[intent]
        best: tuple[float, int, int, str] | None = None
        for start_index in range(len(tokens)):
            for end_index in range(
                start_index,
                min(len(tokens), start_index + self.evidence_max_tokens),
            ):
                start = tokens[start_index].start()
                end = tokens[end_index].end()
                candidate = hr_input[start:end]
                if WORKER_ID_PATTERN.fullmatch(candidate):
                    continue
                feature_score = sum(
                    count * max(0.0, weights.get(feature, 0.0))
                    for feature, count in char_ngrams(
                        candidate,
                        self.ngram_min,
                        self.ngram_max,
                    ).items()
                )
                normalized_score = feature_score / math.sqrt(max(1, len(candidate)))
                rank = (normalized_score, -len(candidate), -start, candidate)
                if best is None or rank > best:
                    best = rank
        if best is None or best[0] <= 0:
            return hr_input
        return best[3]

    def predict(self, hr_input: str) -> dict[str, list[dict[str, str | None]]]:
        if not self.thresholds:
            raise ProvisionalBaselineError("model must be fitted before prediction")
        scores = {intent: self._score(hr_input, intent) for intent in INTENT_CODES}
        selected = [intent for intent in INTENT_CODES if scores[intent] >= self.thresholds[intent]]
        if not selected:
            selected = [max(INTENT_CODES, key=scores.__getitem__)]

        if "OUT_OF_SCOPE" in selected:
            other_selected = [intent for intent in selected if intent != "OUT_OF_SCOPE"]
            if not other_selected or scores["OUT_OF_SCOPE"] >= max(
                scores[intent] for intent in other_selected
            ):
                return {"intents": [{"intent": "OUT_OF_SCOPE", "evidence": None}]}
            selected = other_selected

        evidence_items = [
            {
                "intent": intent,
                "evidence": self._extract_evidence(hr_input, intent),
                "_score": scores[intent],
            }
            for intent in selected
        ]
        evidence_items.sort(
            key=lambda item: (
                hr_input.find(str(item["evidence"])),
                -float(item["_score"]),
            )
        )
        return {
            "intents": [
                {
                    "intent": str(item["intent"]),
                    "evidence": str(item["evidence"]),
                }
                for item in evidence_items[:6]
            ]
        }

    def configuration(self) -> dict[str, Any]:
        return {
            "family": "multilabel_multinomial_naive_bayes",
            "features": "character_ngrams",
            "ngram_min": self.ngram_min,
            "ngram_max": self.ngram_max,
            "alpha": self.alpha,
            "threshold_calibration": "train_in_sample_f1_only",
            "thresholds": {intent: round(self.thresholds[intent], 12) for intent in INTENT_CODES},
            "evidence_strategy": ("highest_positive_weight_contiguous_token_span"),
            "evidence_max_tokens": self.evidence_max_tokens,
            "external_dependencies": [],
        }


def _safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _metric_counts(
    expected: set[str],
    predicted: set[str],
    counts: dict[str, Counter[str]],
) -> None:
    for intent in INTENT_CODES:
        if intent in expected and intent in predicted:
            counts[intent]["tp"] += 1
        elif intent not in expected and intent in predicted:
            counts[intent]["fp"] += 1
        elif intent in expected and intent not in predicted:
            counts[intent]["fn"] += 1


def _metrics_from_counts(
    counts: dict[str, Counter[str]],
) -> tuple[dict[str, Any], float, float]:
    per_intent: dict[str, Any] = {}
    totals: Counter[str] = Counter()
    f1_values: list[float] = []
    for intent in INTENT_CODES:
        intent_counts = counts[intent]
        totals.update(intent_counts)
        precision = _safe_divide(
            intent_counts["tp"],
            intent_counts["tp"] + intent_counts["fp"],
        )
        recall = _safe_divide(
            intent_counts["tp"],
            intent_counts["tp"] + intent_counts["fn"],
        )
        f1 = _safe_divide(2 * precision * recall, precision + recall)
        f1_values.append(f1)
        per_intent[intent] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "support": intent_counts["tp"] + intent_counts["fn"],
        }
    micro_precision = _safe_divide(
        totals["tp"],
        totals["tp"] + totals["fp"],
    )
    micro_recall = _safe_divide(
        totals["tp"],
        totals["tp"] + totals["fn"],
    )
    micro_f1 = _safe_divide(
        2 * micro_precision * micro_recall,
        micro_precision + micro_recall,
    )
    return per_intent, sum(f1_values) / len(f1_values), micro_f1


def evaluate_baseline(
    *,
    model: CharacterNgramMultilabelNB,
    validation_cases: list[dict[str, Any]],
    output_schema: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    label_counts = {intent: Counter() for intent in INTENT_CODES}
    structural_failures: Counter[str] = Counter()
    error_counts: Counter[str] = Counter()
    predictions: list[dict[str, Any]] = []
    intent_exact_matches = 0
    evidence_exact_matches = 0
    evidence_expected_count = 0

    for case in validation_cases:
        output = model.predict(case["hr_input"])
        issues = validate_intent_model_output(
            case["hr_input"],
            output,
            output_schema,
        )
        issue_codes = sorted({issue.code for issue in issues})
        structural_failures.update(issue_codes)

        expected_codes = [item["intent"] for item in case["intents"]]
        predicted_codes = [item["intent"] for item in output["intents"]]
        expected_set = set(expected_codes)
        predicted_set = set(predicted_codes)
        _metric_counts(expected_set, predicted_set, label_counts)
        if expected_codes == predicted_codes:
            intent_exact_matches += 1
        if expected_set - predicted_set:
            error_counts["MISSING_INTENT"] += 1
        if predicted_set - expected_set:
            error_counts["EXTRA_INTENT"] += 1

        expected_evidence = {
            item["intent"]: item["evidence"]
            for item in case["intents"]
            if item["intent"] != "OUT_OF_SCOPE"
        }
        predicted_evidence = {
            item["intent"]: item["evidence"]
            for item in output["intents"]
            if item["intent"] != "OUT_OF_SCOPE"
        }
        for intent, evidence in expected_evidence.items():
            evidence_expected_count += 1
            if predicted_evidence.get(intent) == evidence:
                evidence_exact_matches += 1
            elif (
                isinstance(predicted_evidence.get(intent), str)
                and isinstance(evidence, str)
                and evidence in predicted_evidence[intent]
            ):
                error_counts["EVIDENCE_TOO_BROAD"] += 1

        predictions.append(
            {
                "id": case["id"],
                "hr_input": case["hr_input"],
                "expected": {"intents": case["intents"]},
                "predicted": output,
                "structural_issues": issue_codes,
            }
        )

    per_intent, macro_f1, micro_f1 = _metrics_from_counts(label_counts)
    record_count = len(validation_cases)
    metrics = {
        "record_count": record_count,
        "intent_exact_match": round(
            _safe_divide(intent_exact_matches, record_count),
            6,
        ),
        "macro_f1": round(macro_f1, 6),
        "micro_f1": round(micro_f1, 6),
        "per_intent": per_intent,
        "evidence_gold_exact_match": round(
            _safe_divide(evidence_exact_matches, evidence_expected_count),
            6,
        ),
        "evidence_gold_item_count": evidence_expected_count,
        "structural_gate_rates": {
            "JSON_SCHEMA_VALID": round(
                1
                - _safe_divide(
                    structural_failures["INVALID_JSON"],
                    record_count,
                ),
                6,
            ),
            "EVIDENCE_EXACT_SUBSTRING": round(
                1
                - _safe_divide(
                    structural_failures["EVIDENCE_NOT_SUBSTRING"],
                    record_count,
                ),
                6,
            ),
            "INTENT_ORDER": round(
                1
                - _safe_divide(
                    structural_failures["INTENT_ORDER_ERROR"],
                    record_count,
                ),
                6,
            ),
            "OUT_OF_SCOPE_EXCLUSIVE": round(
                1
                - _safe_divide(
                    structural_failures["OUT_OF_SCOPE_MIXED"],
                    record_count,
                ),
                6,
            ),
        },
        "error_case_counts": dict(sorted((error_counts + structural_failures).items())),
    }
    return metrics, predictions


def _resolve_inside_root(path: Path, root: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise ProvisionalBaselineError(
            "baseline outputs must stay inside the knowledge project"
        ) from error
    return resolved


def run_provisional_baseline(
    root: Path,
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    split_manifest_path = root / "data/intent/splits/provisional-v1/manifest.yaml"
    split_manifest = yaml.safe_load(split_manifest_path.read_text(encoding="utf-8"))
    if split_manifest["status"] == "locked":
        raise ProvisionalBaselineError("this command is only for a provisional split")

    source_path = root / split_manifest["source"]["path"]
    if file_sha256(source_path) != split_manifest["source"]["sha256"]:
        raise ProvisionalBaselineError("source checksum differs from the split manifest")
    train_path = root / split_manifest["outputs"]["train"]["path"]
    validation_path = root / split_manifest["outputs"]["validation"]["path"]
    for name, path in (("train", train_path), ("validation", validation_path)):
        if file_sha256(path) != split_manifest["outputs"][name]["sha256"]:
            raise ProvisionalBaselineError(f"{name} ID checksum differs from the split manifest")

    cases = load_intent_cases(source_path)
    cases_by_id = {case["id"]: case for case in cases}
    train_ids = read_split_ids(train_path)
    validation_ids = read_split_ids(validation_path)
    if set(train_ids) & set(validation_ids):
        raise ProvisionalBaselineError("Train/Validation IDs overlap")
    if set(train_ids) | set(validation_ids) != set(cases_by_id):
        raise ProvisionalBaselineError("Train/Validation IDs do not cover the source")

    train_cases = [cases_by_id[case_id] for case_id in train_ids]
    validation_cases = [cases_by_id[case_id] for case_id in validation_ids]
    model = CharacterNgramMultilabelNB().fit(train_cases)
    output_schema_path = root / "schemas/intent-model-output.schema.json"
    output_schema = json.loads(output_schema_path.read_text(encoding="utf-8"))
    metrics, predictions = evaluate_baseline(
        model=model,
        validation_cases=validation_cases,
        output_schema=output_schema,
    )

    resolved_output_dir = _resolve_inside_root(
        output_dir or DEFAULT_OUTPUT_DIR,
        root,
    )
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = resolved_output_dir / "predictions.jsonl"
    report_path = resolved_output_dir / "report.yaml"
    with predictions_path.open("w", encoding="utf-8") as handle:
        for prediction in predictions:
            handle.write(compact_json(prediction) + "\n")

    report = {
        "experiment_id": "FOWOCO-INTENT-PROVISIONAL-CHAR-NGRAM-NB-V1",
        "version": "0.1.0",
        "status": "provisional_pre_consensus",
        "purpose": ("수정 전 라벨로 모델링·평가 파이프라인과 오류 유형을 검증하는 하한선"),
        "source": {
            **split_manifest["source"],
            "manifest_path": "data/intent/manifest.yaml",
        },
        "split": {
            "manifest_path": str(split_manifest_path.relative_to(root)),
            "manifest_sha256": file_sha256(split_manifest_path),
            "status": split_manifest["status"],
            "train": {
                "path": str(train_path.relative_to(root)),
                "record_count": len(train_cases),
                "sha256": file_sha256(train_path),
            },
            "validation": {
                "path": str(validation_path.relative_to(root)),
                "record_count": len(validation_cases),
                "sha256": file_sha256(validation_path),
            },
            "validation_used_for_training_or_thresholds": False,
        },
        "model": model.configuration(),
        "metrics": metrics,
        "artifacts": {
            "predictions": {
                "path": str(predictions_path.relative_to(root)),
                "record_count": len(predictions),
                "sha256": file_sha256(predictions_path),
            }
        },
        "claims_not_allowed": [
            "최종 모델 성능",
            "Gold Test 성능",
            "운영 배포 가능",
            "A/B consensus가 반영된 라벨 성능",
        ],
        "rerun_required_when": [
            "A/B consensus가 원본 라벨을 변경",
            "source 또는 split checksum이 변경",
            "Intent 규칙 또는 모델 설정이 변경",
        ],
        "limitations": [
            "Reviewer B와 A/B consensus 전 수정 전 라벨을 사용함",
            "Train 내부 점수로 threshold를 정해 운영 threshold로 사용할 수 없음",
            "문자 n-gram Naive Bayes는 A.X 또는 Transformer 모델 후보를 대체하지 않음",
            "evidence 추출은 규칙 기반 하한선이며 자연스러움이나 최소 완결 구간을 보장하지 않음",
            "Validation은 baseline 개발용이며 독립 Gold Test가 아님",
            "모델 학습·추론 코드는 최종적으로 fowoco/ai 저장소로 이전해야 함",
        ],
    }
    report_path.write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return report
