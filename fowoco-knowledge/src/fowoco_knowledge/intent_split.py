from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .ingestion import file_sha256

DEFAULT_SEED = 20260727
DEFAULT_VALIDATION_RATIO = 0.2
DEFAULT_OUTPUT_DIR = Path("data/intent/splits/provisional-v1")
WORKER_ID_PATTERN = re.compile(r"(?i)\bwrk[-_ ]?\d+\b")


class IntentSplitError(ValueError):
    """Raised when an Intent split cannot be generated safely."""


@dataclass(frozen=True)
class TemplateGroup:
    key: str
    cases: tuple[dict[str, Any], ...]
    features: Counter[str]
    rank: str

    @property
    def size(self) -> int:
        return len(self.cases)


@dataclass(frozen=True)
class IntentSplitResult:
    train_ids: tuple[int, ...]
    validation_ids: tuple[int, ...]
    template_group_count: int
    duplicate_template_group_count: int
    max_template_group_size: int


def normalize_intent_template(hr_input: str) -> str:
    """Normalize identifiers without erasing task-defining dates, amounts, or nouns."""
    without_worker_id = WORKER_ID_PATTERN.sub("<WORKER>", hr_input)
    return " ".join(without_worker_id.split()).casefold()


def load_intent_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            case = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise IntentSplitError(f"intent source line {line_number}: invalid JSON") from exc
        if not isinstance(case, dict):
            raise IntentSplitError(f"intent source line {line_number}: record must be an object")
        cases.append(case)
    return cases


def read_split_ids(path: Path) -> tuple[int, ...]:
    ids: list[int] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        value = raw_line.strip()
        if not value:
            continue
        try:
            ids.append(int(value))
        except ValueError as exc:
            raise IntentSplitError(f"{path} line {line_number}: invalid ID") from exc
    return tuple(ids)


def _case_features(cases: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> Counter[str]:
    features: Counter[str] = Counter()
    for case in cases:
        intent_codes = tuple(item["intent"] for item in case["intents"])
        for intent_code in intent_codes:
            features[f"intent:{intent_code}"] += 1
        features[f"cardinality:{len(intent_codes)}"] += 1
        features[f"combination:{'|'.join(intent_codes)}"] += 1
    return features


def _build_template_groups(cases: list[dict[str, Any]], seed: int) -> list[TemplateGroup]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        grouped[normalize_intent_template(case["hr_input"])].append(case)

    groups: list[TemplateGroup] = []
    for key, grouped_cases in grouped.items():
        ordered_cases = tuple(sorted(grouped_cases, key=lambda item: item["id"]))
        rank = hashlib.sha256(f"{seed}\0{key}".encode()).hexdigest()
        groups.append(
            TemplateGroup(
                key=key,
                cases=ordered_cases,
                features=_case_features(ordered_cases),
                rank=rank,
            )
        )
    return groups


def _distribution_cost(
    counts: Counter[str],
    record_count: int,
    target_counts: dict[str, float],
    target_record_count: int,
) -> float:
    cost = 4 * ((record_count - target_record_count) ** 2 / max(target_record_count, 1))
    for feature, target in target_counts.items():
        if feature.startswith("intent:"):
            weight = 1.0
        elif feature.startswith("cardinality:"):
            weight = 0.6
        else:
            weight = 0.35
        cost += weight * ((counts[feature] - target) ** 2 / max(target, 1))
    return cost


def build_intent_split(
    cases: list[dict[str, Any]],
    *,
    seed: int = DEFAULT_SEED,
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
) -> IntentSplitResult:
    if not cases:
        raise IntentSplitError("intent source is empty")
    if not 0 < validation_ratio < 1:
        raise IntentSplitError("validation_ratio must be between 0 and 1")

    source_ids = [case["id"] for case in cases]
    if any(not isinstance(case_id, int) for case_id in source_ids):
        raise IntentSplitError("every intent case must have an integer id")
    if len(source_ids) != len(set(source_ids)):
        raise IntentSplitError("intent source contains duplicate ids")

    groups = _build_template_groups(cases, seed)
    total_features = _case_features(cases)
    target_record_count = round(len(cases) * validation_ratio)
    target_counts = {feature: count * validation_ratio for feature, count in total_features.items()}

    remaining = groups.copy()
    selected: list[TemplateGroup] = []
    validation_features: Counter[str] = Counter()
    validation_count = 0

    while validation_count < target_record_count:
        remaining_capacity = target_record_count - validation_count
        candidates = [group for group in remaining if group.size <= remaining_capacity]
        if not candidates:
            raise IntentSplitError("template grouping cannot satisfy the requested split size")

        selected_group = min(
            candidates,
            key=lambda group: (
                _distribution_cost(
                    validation_features + group.features,
                    validation_count + group.size,
                    target_counts,
                    target_record_count,
                ),
                group.rank,
            ),
        )
        selected.append(selected_group)
        validation_features.update(selected_group.features)
        validation_count += selected_group.size
        remaining.remove(selected_group)

    validation_ids = tuple(sorted(case["id"] for group in selected for case in group.cases))
    train_ids = tuple(sorted(set(source_ids) - set(validation_ids)))
    group_sizes = [group.size for group in groups]
    return IntentSplitResult(
        train_ids=train_ids,
        validation_ids=validation_ids,
        template_group_count=len(groups),
        duplicate_template_group_count=sum(size > 1 for size in group_sizes),
        max_template_group_size=max(group_sizes),
    )


def _label_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(item["intent"] for case in cases for item in case["intents"])
    return dict(sorted(counts.items()))


def _cardinality_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(len(case["intents"])) for case in cases)
    return dict(sorted(counts.items(), key=lambda item: int(item[0])))


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise IntentSplitError("split outputs must stay inside the knowledge project") from exc


def _write_ids(path: Path, ids: tuple[int, ...]) -> None:
    path.write_text("".join(f"{case_id}\n" for case_id in ids), encoding="utf-8")


def build_and_write_intent_split(
    root: Path,
    *,
    output_dir: Path | None = None,
    seed: int = DEFAULT_SEED,
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
) -> dict[str, Any]:
    root = root.resolve()
    intent_manifest_path = root / "data/intent/manifest.yaml"
    intent_manifest = yaml.safe_load(intent_manifest_path.read_text(encoding="utf-8"))
    source_path = root / intent_manifest["path"]
    actual_source_sha256 = file_sha256(source_path)
    if actual_source_sha256 != intent_manifest["sha256"]:
        raise IntentSplitError("intent source checksum differs from data/intent/manifest.yaml")

    cases = load_intent_cases(source_path)
    if len(cases) != intent_manifest["record_count"]:
        raise IntentSplitError("intent source record count differs from its manifest")

    result = build_intent_split(
        cases,
        seed=seed,
        validation_ratio=validation_ratio,
    )
    if output_dir is None:
        resolved_output_dir = (root / DEFAULT_OUTPUT_DIR).resolve()
    elif output_dir.is_absolute():
        resolved_output_dir = output_dir.resolve()
    else:
        resolved_output_dir = (root / output_dir).resolve()
    _relative_path(resolved_output_dir, root)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    train_path = resolved_output_dir / "train_ids.txt"
    validation_path = resolved_output_dir / "validation_ids.txt"
    manifest_path = resolved_output_dir / "manifest.yaml"
    _write_ids(train_path, result.train_ids)
    _write_ids(validation_path, result.validation_ids)

    cases_by_id = {case["id"]: case for case in cases}
    train_cases = [cases_by_id[case_id] for case_id in result.train_ids]
    validation_cases = [cases_by_id[case_id] for case_id in result.validation_ids]
    train_ratio = 1 - validation_ratio
    split_manifest: dict[str, Any] = {
        "split_id": "FOWOCO-HR-INTENT-PROVISIONAL-SPLIT",
        "version": "0.1.0",
        "status": "provisional_pending_consensus",
        "schema": "schemas/intent-split-manifest.schema.json",
        "source": {
            "dataset_id": intent_manifest["dataset_id"],
            "version": intent_manifest["version"],
            "status": intent_manifest["status"],
            "path": intent_manifest["path"],
            "record_count": intent_manifest["record_count"],
            "sha256": actual_source_sha256,
        },
        "consensus": {
            "status": "pending",
            "assumed_for_provisional_split": True,
            "dependency_issue": 30,
            "dependency_pr": 31,
            "regenerate_when_source_changes": True,
        },
        "policy": {
            "method": "grouped_multilabel_greedy",
            "seed": seed,
            "train_ratio": train_ratio,
            "validation_ratio": validation_ratio,
            "target_train_count": len(result.train_ids),
            "target_validation_count": len(result.validation_ids),
            "template_normalization": {
                "worker_id_pattern": WORKER_ID_PATTERN.pattern,
                "worker_id_replacement": "<WORKER>",
                "collapse_whitespace": True,
                "casefold": True,
                "preserve_dates_amounts_and_task_terms": True,
            },
            "stratification_features": [
                "intent_code",
                "intent_cardinality",
                "ordered_intent_combination",
            ],
        },
        "outputs": {
            "train": {
                "path": _relative_path(train_path, root),
                "record_count": len(result.train_ids),
                "sha256": file_sha256(train_path),
            },
            "validation": {
                "path": _relative_path(validation_path, root),
                "record_count": len(result.validation_ids),
                "sha256": file_sha256(validation_path),
            },
        },
        "statistics": {
            "template_group_count": result.template_group_count,
            "duplicate_template_group_count": result.duplicate_template_group_count,
            "max_template_group_size": result.max_template_group_size,
            "label_counts": {
                "source": _label_counts(cases),
                "train": _label_counts(train_cases),
                "validation": _label_counts(validation_cases),
            },
            "intent_cardinality_counts": {
                "source": _cardinality_counts(cases),
                "train": _cardinality_counts(train_cases),
                "validation": _cardinality_counts(validation_cases),
            },
        },
        "limitations": [
            "Reviewer B와 A/B consensus 완료 전에는 최종 학습 분할이 아님",
            "Reviewer A의 proposed_intents_json은 현재 원본에 적용하지 않은 상태임",
            "독립 Gold Test를 포함하지 않음",
            "source SHA-256이 바뀌면 생성기를 다시 실행해야 함",
            "분할 비율과 내부 목표치는 baseline 비교용이며 성능 보장을 뜻하지 않음",
        ],
    }
    manifest_path.write_text(
        yaml.safe_dump(split_manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return split_manifest
