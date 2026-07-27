from __future__ import annotations

from pathlib import Path

import yaml

from fowoco_knowledge.ingestion import file_sha256
from fowoco_knowledge.intent_split import load_intent_cases, read_split_ids
from fowoco_knowledge.provisional_baseline import (
    CharacterNgramMultilabelNB,
    evaluate_baseline,
    run_provisional_baseline,
)
from fowoco_knowledge.repository import KnowledgeRepository

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "data/experiments/intent/provisional-char-ngram-nb-v1/report.yaml"


def test_provisional_baseline_report_is_reproducible() -> None:
    committed = yaml.safe_load(REPORT_PATH.read_text(encoding="utf-8"))
    generated_dir = ROOT / "data/experiments/intent/.test-provisional-baseline"
    regenerated = run_provisional_baseline(
        ROOT,
        output_dir=Path("data/experiments/intent/.test-provisional-baseline"),
    )
    try:
        assert regenerated["source"] == committed["source"]
        assert regenerated["split"] == committed["split"]
        assert regenerated["model"] == committed["model"]
        assert regenerated["metrics"] == committed["metrics"]
        assert (
            file_sha256(generated_dir / "predictions.jsonl")
            == committed["artifacts"]["predictions"]["sha256"]
        )
    finally:
        for path in generated_dir.iterdir():
            path.unlink()
        generated_dir.rmdir()


def test_validation_records_are_not_used_for_fit() -> None:
    split_manifest = yaml.safe_load(
        (ROOT / "data/intent/splits/provisional-v1/manifest.yaml").read_text(encoding="utf-8")
    )
    cases = load_intent_cases(ROOT / split_manifest["source"]["path"])
    cases_by_id = {case["id"]: case for case in cases}
    train_ids = read_split_ids(ROOT / split_manifest["outputs"]["train"]["path"])
    validation_ids = read_split_ids(ROOT / split_manifest["outputs"]["validation"]["path"])

    model = CharacterNgramMultilabelNB().fit([cases_by_id[case_id] for case_id in train_ids])
    assert set(train_ids).isdisjoint(validation_ids)
    assert len(train_ids) == 1072
    assert len(validation_ids) == 268
    assert model.thresholds


def test_baseline_outputs_follow_structural_gates() -> None:
    repository = KnowledgeRepository(ROOT)
    output_schema = repository.load_json("schemas/intent-model-output.schema.json")
    training_cases = [
        {
            "id": 1,
            "hr_input": "WRK-001 여권 사본 받아주세요",
            "intents": [
                {
                    "intent": "DOCUMENT_REQUEST",
                    "evidence": "여권 사본 받아주세요",
                }
            ],
        },
        {
            "id": 2,
            "hr_input": "WRK-002 비자 만료라 연장 준비",
            "intents": [
                {
                    "intent": "EXPIRY_RENEWAL",
                    "evidence": "비자 만료라 연장 준비",
                }
            ],
        },
        {
            "id": 3,
            "hr_input": "WRK-003 급여 공제 설명",
            "intents": [
                {
                    "intent": "PAYROLL_EXPLANATION",
                    "evidence": "급여 공제 설명",
                }
            ],
        },
        {
            "id": 4,
            "hr_input": "WRK-004 신규 근로자 등록",
            "intents": [
                {
                    "intent": "WORKER_ONBOARDING",
                    "evidence": "신규 근로자 등록",
                }
            ],
        },
        {
            "id": 5,
            "hr_input": "WRK-005 퇴사 처리",
            "intents": [{"intent": "EMPLOYMENT_CHANGE", "evidence": "퇴사 처리"}],
        },
        {
            "id": 6,
            "hr_input": "WRK-006 작업 배치 안내",
            "intents": [{"intent": "WORK_INSTRUCTION", "evidence": "작업 배치 안내"}],
        },
        {
            "id": 7,
            "hr_input": "오늘 점심 추천",
            "intents": [{"intent": "OUT_OF_SCOPE", "evidence": None}],
        },
    ]
    model = CharacterNgramMultilabelNB(
        ngram_min=1,
        ngram_max=2,
    ).fit(training_cases)
    metrics, predictions = evaluate_baseline(
        model=model,
        validation_cases=training_cases,
        output_schema=output_schema,
    )

    assert len(predictions) == 7
    assert metrics["structural_gate_rates"] == {
        "JSON_SCHEMA_VALID": 1.0,
        "EVIDENCE_EXACT_SUBSTRING": 1.0,
        "INTENT_ORDER": 1.0,
        "OUT_OF_SCOPE_EXCLUSIVE": 1.0,
    }
    assert all(not prediction["structural_issues"] for prediction in predictions)
