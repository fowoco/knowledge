from __future__ import annotations

import copy
import re
from dataclasses import asdict, dataclass
from typing import Any

from .repository import KnowledgeRepository


@dataclass(frozen=True)
class Redaction:
    kind: str
    path: str
    label: str


@dataclass(frozen=True)
class SanitizationResult:
    payload: dict[str, Any]
    redactions: list[Redaction]

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload": self.payload,
            "redactions": [asdict(redaction) for redaction in self.redactions],
        }


class DataProtector:
    """Build the minimum masked payload allowed to cross the LLM boundary."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository
        self.policy = repository.load_yaml("knowledge/data_protection.yaml")
        boundary = self.policy["llm_boundary"]
        self.allowed_top_level = set(boundary["allowed_top_level_fields"])
        self.blocked_fields = set(boundary["blocked_fields"])
        self.contextual_fields = set(boundary["contextual_exact_value_fields"])
        self.patterns = {
            name: re.compile(pattern) for name, pattern in boundary["text_masking_patterns"].items()
        }
        self.replacements = boundary["replacements"]

    def sanitize_for_llm(self, workflow_id: str, payload: dict[str, Any]) -> SanitizationResult:
        source = copy.deepcopy(payload)
        contextual_values = self._collect_contextual_values(source)
        redactions: list[Redaction] = []
        result: dict[str, Any] = {}

        for key, value in source.items():
            path = key
            if key in self.blocked_fields:
                redactions.append(Redaction("field_drop", path, key))
                continue
            if key not in self.allowed_top_level:
                redactions.append(Redaction("field_minimization", path, key))
                continue
            if key == "slots":
                result[key] = self._sanitize_slots(
                    workflow_id,
                    value if isinstance(value, dict) else {},
                    contextual_values,
                    redactions,
                )
                continue
            result[key] = self._sanitize_value(value, path, contextual_values, redactions)

        result["workflow_id"] = workflow_id
        return SanitizationResult(payload=result, redactions=redactions)

    def _sanitize_slots(
        self,
        workflow_id: str,
        slots: dict[str, Any],
        contextual_values: dict[str, str],
        redactions: list[Redaction],
    ) -> dict[str, Any]:
        workflow = self.repository.get_workflow(workflow_id)
        requirements = self.repository.load_yaml("knowledge/required_slots.yaml")[
            "workflow_requirements"
        ][workflow["required_slots_ref"]]
        allowed_slots = set(requirements.get("required", [])) | set(
            requirements.get("optional", [])
        )
        result: dict[str, Any] = {}
        for key, value in slots.items():
            path = f"slots.{key}"
            if key in self.blocked_fields:
                redactions.append(Redaction("field_drop", path, key))
                continue
            if key not in allowed_slots:
                redactions.append(Redaction("slot_minimization", path, key))
                continue
            result[key] = self._sanitize_value(value, path, contextual_values, redactions)
        return result

    def _sanitize_value(
        self,
        value: Any,
        path: str,
        contextual_values: dict[str, str],
        redactions: list[Redaction],
    ) -> Any:
        if isinstance(value, str):
            return self._mask_text(value, path, contextual_values, redactions)
        if isinstance(value, list):
            return [
                self._sanitize_value(item, f"{path}[{index}]", contextual_values, redactions)
                for index, item in enumerate(value)
            ]
        if isinstance(value, dict):
            nested: dict[str, Any] = {}
            for key, item in value.items():
                nested_path = f"{path}.{key}"
                if key in self.blocked_fields:
                    redactions.append(Redaction("field_drop", nested_path, key))
                    continue
                nested[key] = self._sanitize_value(item, nested_path, contextual_values, redactions)
            return nested
        return value

    def _mask_text(
        self,
        text: str,
        path: str,
        contextual_values: dict[str, str],
        redactions: list[Redaction],
    ) -> str:
        masked = text
        for field, value in contextual_values.items():
            if value and value in masked:
                masked = masked.replace(value, f"[{field.upper()}]")
                redactions.append(Redaction("contextual_mask", path, field))
        for name, pattern in self.patterns.items():
            masked, count = pattern.subn(self.replacements[name], masked)
            if count:
                redactions.append(Redaction("pattern_mask", path, name))
        return masked

    def _collect_contextual_values(self, payload: dict[str, Any]) -> dict[str, str]:
        values: dict[str, str] = {}

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in self.contextual_fields and isinstance(item, str) and item.strip():
                        values[key] = item.strip()
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(payload)
        return values
