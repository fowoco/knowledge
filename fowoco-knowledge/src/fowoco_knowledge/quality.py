from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from .repository import KnowledgeRepository


@dataclass(frozen=True)
class QualityIssue:
    code: str
    severity: str
    slot_name: str | None = None
    expected: Any = None
    observed: Any = None


@dataclass(frozen=True)
class NoticeQualityResult:
    issues: list[QualityIssue]
    gate: str
    core_value_total: int
    core_value_preserved: int
    core_value_omitted: int
    core_value_changed: int
    unsupported_value_count: int
    critical_value_total: int
    critical_value_omitted: int

    @property
    def core_value_preservation_rate(self) -> float:
        if self.core_value_total == 0:
            return 1.0
        return round(self.core_value_preserved / self.core_value_total, 4)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["core_value_preservation_rate"] = self.core_value_preservation_rate
        result["issue_codes"] = [issue.code for issue in self.issues]
        return result


class NoticeQualityEvaluator:
    """Compare approved source Slots with values extracted from a generated notice."""

    _EMPTY_VALUES = (None, "", [])

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.policy = repository.load_yaml("knowledge/output_quality_policy.yaml")
        self.error_catalog = self.policy["error_catalog"]
        self.severity_rank = {
            severity: index
            for index, severity in enumerate(self.policy["gate_policy"]["severity_order"])
        }

    def evaluate(
        self,
        source_slots: dict[str, Any],
        candidate_slots: dict[str, Any],
        observed_claims: list[str] | None = None,
    ) -> NoticeQualityResult:
        issues: list[QualityIssue] = []
        immutable_slots = self.policy["immutable_slots"]
        critical_slots = set(self.policy["critical_slots"])

        total = preserved = omitted = changed = unsupported = 0
        critical_total = critical_omitted = 0
        for slot_name in immutable_slots:
            source = source_slots.get(slot_name)
            candidate = candidate_slots.get(slot_name)
            source_present = not self._is_empty(source)
            candidate_present = not self._is_empty(candidate)

            if source_present:
                total += 1
                if slot_name in critical_slots:
                    critical_total += 1
                if not candidate_present:
                    omitted += 1
                    if slot_name in critical_slots:
                        critical_omitted += 1
                    issues.append(
                        self._issue(
                            "CORE_VALUE_OMITTED",
                            slot_name=slot_name,
                            expected=source,
                        )
                    )
                elif self._canonical(source) != self._canonical(candidate):
                    changed += 1
                    issues.append(
                        self._issue(
                            "CORE_VALUE_CHANGED",
                            slot_name=slot_name,
                            expected=source,
                            observed=candidate,
                        )
                    )
                else:
                    preserved += 1
            elif candidate_present:
                unsupported += 1
                issues.append(
                    self._issue(
                        "UNSUPPORTED_VALUE_ADDED",
                        slot_name=slot_name,
                        observed=candidate,
                    )
                )

        for claim in observed_claims or []:
            claim_policy = self.policy["observed_claims"].get(claim)
            if claim_policy is None:
                raise ValueError(f"Unknown observed claim: {claim}")
            issues.append(self._issue(claim_policy["issue_code"]))

        return NoticeQualityResult(
            issues=issues,
            gate=self._gate(issues),
            core_value_total=total,
            core_value_preserved=preserved,
            core_value_omitted=omitted,
            core_value_changed=changed,
            unsupported_value_count=unsupported,
            critical_value_total=critical_total,
            critical_value_omitted=critical_omitted,
        )

    def evaluate_case(self, case: dict[str, Any]) -> NoticeQualityResult:
        return self.evaluate(
            case["source_slots"],
            case["candidate_slots"],
            case.get("observed_claims", []),
        )

    def _issue(
        self,
        code: str,
        slot_name: str | None = None,
        expected: Any = None,
        observed: Any = None,
    ) -> QualityIssue:
        config = self.error_catalog[code]
        return QualityIssue(
            code=code,
            severity=config["severity"],
            slot_name=slot_name,
            expected=expected,
            observed=observed,
        )

    def _gate(self, issues: list[QualityIssue]) -> str:
        if not issues:
            return self.policy["gate_policy"]["no_issue"]
        highest = max(issues, key=lambda issue: self.severity_rank[issue.severity])
        return self.policy["gate_policy"][highest.severity]

    @classmethod
    def _is_empty(cls, value: Any) -> bool:
        return value in cls._EMPTY_VALUES

    @staticmethod
    def _canonical(value: Any) -> str:
        if isinstance(value, str):
            return " ".join(value.split()).casefold()
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
