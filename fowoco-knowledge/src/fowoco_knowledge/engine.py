from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from jsonschema import Draft202012Validator

from .repository import KnowledgeRepository


@dataclass(frozen=True)
class AmbiguityMatch:
    pattern_id: str
    category: str
    matched_term: str
    question: str


@dataclass(frozen=True)
class EvaluationResult:
    request_id: str
    workflow_id: str
    workflow_name: str
    valid_input_mode: bool
    missing_slots: list[str]
    ambiguities: list[AmbiguityMatch]
    action: str
    hr_approval_required: bool
    official_source_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RequestEvaluator:
    """Validate classified model output before a Workflow is executed."""

    _RESOLUTION_FIELDS = {
        "TIME": {"due_at", "effective_at", "incident_at", "pay_period"},
        "LOCATION": {"work_location", "submission_channel"},
        "OBJECT": {"document_type", "source_document_id", "work_action"},
        "TARGET": {"worker_id"},
        "AMOUNT": {"source_document_id", "pay_item"},
        "ACTION": {"work_action", "change_type", "document_type", "source_document_id"},
    }

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository
        schema = repository.load_json("schemas/agent-request.schema.json")
        self.schema_validator = Draft202012Validator(schema)

    def evaluate(self, request: dict[str, Any]) -> EvaluationResult:
        schema_errors = sorted(
            self.schema_validator.iter_errors(request), key=lambda e: list(e.path)
        )
        if schema_errors:
            message = "; ".join(error.message for error in schema_errors)
            raise ValueError(f"Invalid agent request: {message}")

        workflow = self.repository.get_workflow(request["workflow_id"])
        slots = request["slots"]
        slot_config = self.repository.load_yaml("knowledge/required_slots.yaml")
        requirements = slot_config["workflow_requirements"][workflow["required_slots_ref"]]
        missing = [
            slot_name
            for slot_name in requirements.get("required", [])
            if slots.get(slot_name) in (None, "", [])
        ]
        ambiguities = self._find_unresolved_ambiguities(request["utterance"], slots)
        valid_input_mode = request["input_mode"] in workflow["supported_input_modes"]

        confidence = self._top_confidence(request.get("intent_candidates", []))
        if not valid_input_mode:
            action = "REQUEST_CLARIFICATION"
        elif confidence is not None and confidence < 0.65:
            action = "REQUEST_CLASSIFICATION_CONFIRMATION"
        elif missing or ambiguities:
            action = "REQUEST_CLARIFICATION"
        elif workflow["sensitivity"] in {"high", "critical"}:
            action = "REQUIRE_HR_REVIEW"
        else:
            action = "CREATE_DRAFT_TASK"

        return EvaluationResult(
            request_id=request["request_id"],
            workflow_id=workflow["id"],
            workflow_name=workflow["name"],
            valid_input_mode=valid_input_mode,
            missing_slots=missing,
            ambiguities=ambiguities,
            action=action,
            hr_approval_required=True,
            official_source_ids=workflow["source_ids"],
        )

    def _find_unresolved_ambiguities(
        self, utterance: str, slots: dict[str, Any]
    ) -> list[AmbiguityMatch]:
        config = self.repository.load_yaml("knowledge/ambiguity_patterns.yaml")
        matches: list[AmbiguityMatch] = []
        for pattern in config["patterns"]:
            category = pattern["category"]
            resolution_fields = self._RESOLUTION_FIELDS.get(category, set())
            resolved = any(slots.get(field) not in (None, "", []) for field in resolution_fields)
            if resolved:
                continue
            for term in pattern["terms"]:
                if term in utterance:
                    matches.append(
                        AmbiguityMatch(
                            pattern_id=pattern["id"],
                            category=category,
                            matched_term=term,
                            question=pattern["question_template"],
                        )
                    )
                    break
        return matches

    @staticmethod
    def _top_confidence(candidates: list[dict[str, Any]]) -> float | None:
        if not candidates:
            return None
        return max(float(item["confidence"]) for item in candidates)
