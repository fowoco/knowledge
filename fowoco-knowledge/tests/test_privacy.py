from __future__ import annotations

import copy
import json
from pathlib import Path

from fowoco_knowledge.privacy import DataProtector
from fowoco_knowledge.repository import KnowledgeRepository

ROOT = Path(__file__).resolve().parents[1]


def load_payload() -> dict:
    return json.loads((ROOT / "examples/llm_payload_with_pii.json").read_text(encoding="utf-8"))


def test_llm_payload_drops_documents_and_direct_identifiers() -> None:
    result = DataProtector(KnowledgeRepository(ROOT)).sanitize_for_llm("WF-DOC-001", load_payload())

    serialized = json.dumps(result.payload, ensure_ascii=False)
    assert "raw_document" not in result.payload
    assert "worker_name" not in result.payload
    assert "phone" not in result.payload
    assert "응우옌 반 A" not in serialized
    assert "010-1234-5678" not in serialized
    assert "[WORKER_NAME]" in result.payload["utterance"]
    assert "[PHONE]" in result.payload["utterance"]


def test_llm_payload_keeps_only_workflow_slots() -> None:
    result = DataProtector(KnowledgeRepository(ROOT)).sanitize_for_llm("WF-DOC-001", load_payload())

    assert set(result.payload["slots"]) == {
        "worker_id",
        "document_type",
        "due_at",
        "submission_channel",
    }
    assert any(
        redaction.kind == "slot_minimization" and redaction.path == "slots.unrelated_company_note"
        for redaction in result.redactions
    )


def test_sanitization_does_not_mutate_the_source_payload() -> None:
    source = load_payload()
    original = copy.deepcopy(source)

    DataProtector(KnowledgeRepository(ROOT)).sanitize_for_llm("WF-DOC-001", source)

    assert source == original
