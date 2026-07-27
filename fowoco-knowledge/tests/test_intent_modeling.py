from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from fowoco_knowledge.ingestion import file_sha256
from fowoco_knowledge.intent_model import validate_intent_model_output
from fowoco_knowledge.intent_split import (
    build_intent_split,
    load_intent_cases,
    normalize_intent_template,
    read_split_ids,
)
from fowoco_knowledge.repository import KnowledgeRepository

ROOT = Path(__file__).resolve().parents[1]


def test_intent_model_output_contract_and_runtime_constraints() -> None:
    repository = KnowledgeRepository(ROOT)
    schema = repository.load_json("schemas/intent-model-output.schema.json")
    valid_output = {
        "intents": [
            {"intent": "EXPIRY_RENEWAL", "evidence": "재계약 준비하면서"},
            {"intent": "DOCUMENT_REQUEST", "evidence": "서명본도 받아서"},
        ]
    }
    hr_input = "재계약 준비하면서 서명본도 받아서 첨부해줘"

    assert list(Draft202012Validator(schema).iter_errors(valid_output)) == []
    assert validate_intent_model_output(hr_input, valid_output, schema) == ()

    invalid_output = {
        "request_id": "req_should_be_server_owned",
        "intents": [
            {"intent": "DOCUMENT_REQUEST", "evidence": "원문에 없는 증거"},
            {"intent": "OUT_OF_SCOPE", "evidence": None},
        ],
    }
    issue_codes = {
        issue.code for issue in validate_intent_model_output(hr_input, invalid_output, schema)
    }
    assert issue_codes == {
        "INVALID_JSON",
        "EVIDENCE_NOT_SUBSTRING",
        "OUT_OF_SCOPE_MIXED",
    }


def test_provisional_intent_split_is_reproducible_and_grouped() -> None:
    repository = KnowledgeRepository(ROOT)
    manifest = repository.load_yaml("data/intent/splits/provisional-v1/manifest.yaml")
    cases = load_intent_cases(ROOT / manifest["source"]["path"])
    train_ids = read_split_ids(ROOT / manifest["outputs"]["train"]["path"])
    validation_ids = read_split_ids(ROOT / manifest["outputs"]["validation"]["path"])

    assert len(train_ids) == 1072
    assert len(validation_ids) == 268
    assert not set(train_ids) & set(validation_ids)
    assert set(train_ids) | set(validation_ids) == {case["id"] for case in cases}

    regenerated = build_intent_split(
        cases,
        seed=manifest["policy"]["seed"],
        validation_ratio=manifest["policy"]["validation_ratio"],
    )
    assert regenerated.train_ids == train_ids
    assert regenerated.validation_ids == validation_ids

    split_by_id = {
        **{case_id: "train" for case_id in train_ids},
        **{case_id: "validation" for case_id in validation_ids},
    }
    template_splits: dict[str, set[str]] = {}
    for case in cases:
        key = normalize_intent_template(case["hr_input"])
        template_splits.setdefault(key, set()).add(split_by_id[case["id"]])
    assert all(len(splits) == 1 for splits in template_splits.values())

    source_counts = Counter(item["intent"] for case in cases for item in case["intents"])
    validation_id_set = set(validation_ids)
    validation_cases = [case for case in cases if case["id"] in validation_id_set]
    validation_counts = Counter(
        item["intent"] for case in validation_cases for item in case["intents"]
    )
    for intent, source_count in source_counts.items():
        observed_ratio = validation_counts[intent] / source_count
        assert abs(observed_ratio - manifest["policy"]["validation_ratio"]) <= 0.01


def test_provisional_split_output_checksums_match_manifest() -> None:
    repository = KnowledgeRepository(ROOT)
    manifest = repository.load_yaml("data/intent/splits/provisional-v1/manifest.yaml")
    for output in manifest["outputs"].values():
        assert file_sha256(ROOT / output["path"]) == output["sha256"]


def test_training_source_has_no_direct_gold_test_overlap_contract() -> None:
    intent_cases = load_intent_cases(ROOT / "data/intent/hr_intent_dataset.jsonl")
    smoke_cases = [
        json.loads(line)
        for line in (ROOT / "data/evaluation/golden_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    normalized_training_inputs = {
        normalize_intent_template(case["hr_input"]) for case in intent_cases
    }
    normalized_smoke_inputs = {normalize_intent_template(case["utterance"]) for case in smoke_cases}
    assert not normalized_training_inputs & normalized_smoke_inputs
