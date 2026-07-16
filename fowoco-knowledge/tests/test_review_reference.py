from __future__ import annotations

import csv
from pathlib import Path

from fowoco_knowledge.repository import KnowledgeRepository
from fowoco_knowledge.validation import NEXT_ACTIONS

ROOT = Path(__file__).resolve().parents[1]


def _reference_tags(field: str) -> set[str]:
    path = ROOT / "data/review/label_reference.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["tag"] for row in rows if row["field"] == field}


def test_review_reference_covers_context_pack_labels() -> None:
    repository = KnowledgeRepository(ROOT)
    intents = repository.load_yaml("knowledge/intents.yaml")
    domains = repository.load_yaml("knowledge/domains.yaml")
    workflows = repository.load_yaml("knowledge/workflow_catalog.yaml")
    slots = repository.load_yaml("knowledge/required_slots.yaml")
    ambiguities = repository.load_yaml("knowledge/ambiguity_patterns.yaml")

    expected_intents = {item["id"] for item in intents["intents"]}
    expected_intents.add(intents["out_of_scope_label"])

    assert _reference_tags("intents") == expected_intents
    assert _reference_tags("domains") == {item["id"] for item in domains["domains"]}
    assert _reference_tags("workflow_ids") == {item["id"] for item in workflows["workflows"]}
    assert _reference_tags("slots_json") == set(slots["slot_definitions"])
    assert _reference_tags("ambiguities") == {item["category"] for item in ambiguities["patterns"]}
    assert _reference_tags("next_action") == NEXT_ACTIONS


def test_review_reference_covers_fixed_review_labels() -> None:
    assert _reference_tags("source") == {
        "TEAM_SYNTHETIC",
        "INTERVIEW_DERIVED_ANON",
    }
    assert _reference_tags("input_mode") == {
        "WORKER_MESSAGE",
        "AGENT_TASK",
        "INTERNAL_REQUEST",
    }
    assert _reference_tags("change_type") == {
        "RESIGNATION",
        "ABSENCE",
        "UNREACHABLE",
        "WORKPLACE_CHANGE",
        "OTHER",
    }
    assert _reference_tags("sensitivity") == {"low", "medium", "high", "critical"}
    assert _reference_tags("decision") == {
        "APPROVE",
        "CORRECT",
        "REJECT",
        "EXPERT_REVIEW",
    }
