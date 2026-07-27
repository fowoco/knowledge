from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class IntentOutputIssue:
    code: str
    message: str


def validate_intent_model_output(
    hr_input: str,
    output: Any,
    schema: dict[str, Any],
) -> tuple[IntentOutputIssue, ...]:
    """Validate model output constraints that JSON Schema alone cannot express."""
    issues: list[IntentOutputIssue] = []
    validator = Draft202012Validator(schema)
    for error in sorted(
        validator.iter_errors(output),
        key=lambda item: "/".join(str(part) for part in item.path),
    ):
        path = ".".join(str(item) for item in error.path)
        location = f" at {path}" if path else ""
        issues.append(
            IntentOutputIssue(
                code="INVALID_JSON",
                message=f"output schema violation{location}: {error.message}",
            )
        )

    if not isinstance(output, dict) or not isinstance(output.get("intents"), list):
        return tuple(issues)

    intent_codes: list[str] = []
    evidence_positions: list[int] = []
    for item in output["intents"]:
        if not isinstance(item, dict):
            continue
        intent = item.get("intent")
        evidence = item.get("evidence")
        if isinstance(intent, str):
            if intent in intent_codes:
                issues.append(
                    IntentOutputIssue(
                        code="DUPLICATE_INTENT",
                        message=f"duplicate intent: {intent}",
                    )
                )
            intent_codes.append(intent)

        if intent == "OUT_OF_SCOPE":
            continue
        if isinstance(evidence, str) and evidence:
            position = hr_input.find(evidence)
            if position < 0:
                issues.append(
                    IntentOutputIssue(
                        code="EVIDENCE_NOT_SUBSTRING",
                        message=f"evidence is not an exact substring: {evidence}",
                    )
                )
            else:
                evidence_positions.append(position)

    if "OUT_OF_SCOPE" in intent_codes and len(intent_codes) != 1:
        issues.append(
            IntentOutputIssue(
                code="OUT_OF_SCOPE_MIXED",
                message="OUT_OF_SCOPE must be the only intent",
            )
        )
    if evidence_positions != sorted(evidence_positions):
        issues.append(
            IntentOutputIssue(
                code="INTENT_ORDER_ERROR",
                message="intents are not in evidence order",
            )
        )
    return tuple(issues)
