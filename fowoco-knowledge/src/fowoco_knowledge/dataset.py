from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .quality import NoticeQualityEvaluator
from .repository import KnowledgeRepository

GOLD_STATUSES = {"GOLD_TEAM", "GOLD_EXPERT"}
EXPERT_REVIEW_SENSITIVITIES = {"high", "critical"}

REVIEW_COLUMNS = [
    "request_id",
    "reviewer_code",
    "source",
    "input_mode",
    "hr_utterance",
    "system_context",
    "intents",
    "domains",
    "workflow_ids",
    "slots_json",
    "missing_slots",
    "ambiguities",
    "sensitivity",
    "next_action",
    "decision",
    "notes",
    "reviewed_at",
]

DISAGREEMENT_COLUMNS = [
    "request_id",
    "hr_utterance",
    "disagreement_fields",
    "reviewer_a_code",
    "reviewer_a_intents",
    "reviewer_a_domains",
    "reviewer_a_workflow_ids",
    "reviewer_a_slots_json",
    "reviewer_a_missing_slots",
    "reviewer_a_ambiguities",
    "reviewer_a_sensitivity",
    "reviewer_a_next_action",
    "reviewer_a_decision",
    "reviewer_b_code",
    "reviewer_b_intents",
    "reviewer_b_domains",
    "reviewer_b_workflow_ids",
    "reviewer_b_slots_json",
    "reviewer_b_missing_slots",
    "reviewer_b_ambiguities",
    "reviewer_b_sensitivity",
    "reviewer_b_next_action",
    "reviewer_b_decision",
    "adjudication_status",
    "final_intents",
    "final_domains",
    "final_workflow_ids",
    "final_notes",
]

PII_PATTERNS = {
    "resident_or_foreigner_number": re.compile(r"(?<!\d)\d{6}-[1-8]\d{6}(?!\d)"),
    "phone_number": re.compile(r"(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}


def split_codes(raw: str | None) -> list[str]:
    return [item.strip() for item in (raw or "").split("|") if item.strip()]


def normalize_utterance(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


class DatasetManager:
    """Inspect dataset readiness and create independent blind-review queues."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository
        self.manifest = repository.load_yaml("data/dataset_manifest.yaml")

    def load_seed(self) -> list[dict[str, str]]:
        return self.repository.load_csv(self.manifest["datasets"]["seed"]["path"])

    def load_evaluation(self) -> list[dict[str, Any]]:
        path = self.repository.root / self.manifest["datasets"]["evaluation"]["path"]
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def load_notice_quality_evaluation(self) -> list[dict[str, Any]]:
        path = self.repository.root / self.manifest["datasets"]["notice_quality_evaluation"]["path"]
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def load_interview_evidence(self) -> list[dict[str, str]]:
        return self.repository.load_csv(self.manifest["datasets"]["interview_evidence"]["path"])

    def build_report(self) -> dict[str, Any]:
        seed = self.load_seed()
        evaluation = self.load_evaluation()
        notice_quality = self.load_notice_quality_evaluation()
        interview_evidence = self.load_interview_evidence()
        targets = self.manifest["targets"]

        seed_intents = Counter(code for row in seed for code in split_codes(row.get("intents")))
        seed_domains = Counter(code for row in seed for code in split_codes(row.get("domains")))
        review_statuses = Counter(row["review_status"] for row in seed)
        sensitivities = Counter(row["sensitivity"] for row in seed)
        input_modes = Counter(row["input_mode"] for row in seed)
        sources = Counter(row["source"] for row in seed)

        duplicate_seed = self._duplicates((row["request_id"], row["hr_utterance"]) for row in seed)
        duplicate_evaluation = self._duplicates(
            (case["case_id"], case["utterance"]) for case in evaluation
        )
        seed_by_text = {normalize_utterance(row["hr_utterance"]): row["request_id"] for row in seed}
        evaluation_by_text = {
            normalize_utterance(case["utterance"]): case["case_id"] for case in evaluation
        }
        overlap = [
            {
                "seed_id": seed_by_text[text],
                "evaluation_id": evaluation_by_text[text],
                "normalized_utterance": text,
            }
            for text in sorted(seed_by_text.keys() & evaluation_by_text.keys())
        ]
        pii_hits = self._scan_pii(seed, evaluation, notice_quality, interview_evidence)
        notice_quality_report = self._notice_quality_report(notice_quality)
        gold_count = sum(row["review_status"] in GOLD_STATUSES for row in seed)
        workflow_expert_review_required = sum(
            row["sensitivity"] in EXPERT_REVIEW_SENSITIVITIES for row in seed
        )
        in_scope_intents = {
            item["id"] for item in self.repository.load_yaml("knowledge/intents.yaml")["intents"]
        }
        evaluation_intents = {intent for case in evaluation for intent in case["expected_intents"]}

        return {
            "contract_version": self.manifest["version"],
            "representative_model": self.manifest["representative_model"]["id"],
            "seed": {
                "rows": len(seed),
                "gold_rows": gold_count,
                "multi_intent_rows": sum(len(split_codes(row.get("intents"))) > 1 for row in seed),
                "workflow_expert_review_required_rows": workflow_expert_review_required,
                "intent_distribution": dict(sorted(seed_intents.items())),
                "domain_distribution": dict(sorted(seed_domains.items())),
                "review_status_distribution": dict(sorted(review_statuses.items())),
                "sensitivity_distribution": dict(sorted(sensitivities.items())),
                "input_mode_distribution": dict(sorted(input_modes.items())),
                "source_distribution": dict(sorted(sources.items())),
                "duplicate_utterances": duplicate_seed,
            },
            "evaluation": {
                "rows": len(evaluation),
                "locked": self.manifest["datasets"]["evaluation"]["locked"],
                "covered_in_scope_intents": sorted(in_scope_intents & evaluation_intents),
                "missing_in_scope_intents": sorted(in_scope_intents - evaluation_intents),
                "duplicate_utterances": duplicate_evaluation,
            },
            "quality": {
                "seed_evaluation_overlap": overlap,
                "pii_pattern_hits": pii_hits,
            },
            "notice_quality": notice_quality_report,
            "business_evidence": {
                "rows": len(interview_evidence),
                "interviews": len({row["interview_id"] for row in interview_evidence}),
                "target_fit_distribution": dict(
                    sorted(Counter(row["target_fit"] for row in interview_evidence).items())
                ),
                "finding_type_distribution": dict(
                    sorted(Counter(row["finding_type"] for row in interview_evidence).items())
                ),
                "purchase_intent_distribution": dict(
                    sorted(Counter(row["purchase_intent"] for row in interview_evidence).items())
                ),
                "quantitative_baseline_rows": sum(
                    bool(re.match(r"^\d", row["metric_value"])) for row in interview_evidence
                ),
            },
            "readiness": {
                "smoke_evaluation_ready": (
                    len(evaluation) >= targets["smoke_evaluation_min_rows"]
                    and not overlap
                    and not duplicate_evaluation
                    and not pii_hits
                    and in_scope_intents <= evaluation_intents
                ),
                "gold_v1_ready": (
                    gold_count >= targets["gold_v1_min_rows"]
                    and not duplicate_seed
                    and not overlap
                    and not pii_hits
                ),
                "classification_baseline_ready": (
                    gold_count >= targets["baseline_total_rows"]
                    and all(
                        seed_intents[intent] >= targets["baseline_min_rows_per_in_scope_intent"]
                        for intent in in_scope_intents
                    )
                    and not duplicate_seed
                    and not overlap
                    and not pii_hits
                ),
            },
            "targets": targets,
        }

    def write_blind_review_queue(self, reviewer_code: str, output: Path) -> int:
        reviewer_code = reviewer_code.strip()
        if not reviewer_code:
            raise ValueError("reviewer_code must not be blank")
        rows = self.load_seed()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "request_id": row["request_id"],
                        "reviewer_code": reviewer_code,
                        "source": row["source"],
                        "input_mode": row["input_mode"],
                        "hr_utterance": row["hr_utterance"],
                        "system_context": row["system_context"],
                        "slots_json": "{}",
                    }
                )
        return len(rows)

    @staticmethod
    def _duplicates(items: Any) -> list[dict[str, Any]]:
        by_text: dict[str, list[str]] = defaultdict(list)
        for item_id, utterance in items:
            by_text[normalize_utterance(utterance)].append(item_id)
        return [
            {"normalized_utterance": text, "ids": ids}
            for text, ids in sorted(by_text.items())
            if len(ids) > 1
        ]

    @staticmethod
    def _scan_pii(
        seed: list[dict[str, str]],
        evaluation: list[dict[str, Any]],
        notice_quality: list[dict[str, Any]],
        interview_evidence: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        documents: list[tuple[str, str, str]] = []
        for row in seed:
            documents.append(("seed", row["request_id"], row["hr_utterance"]))
            documents.append(("seed_context", row["request_id"], row["system_context"]))
        for case in evaluation:
            documents.append(("evaluation", case["case_id"], case["utterance"]))
            documents.append(
                (
                    "evaluation_context",
                    case["case_id"],
                    json.dumps(case.get("system_context", {}), ensure_ascii=False),
                )
            )
        for case in notice_quality:
            documents.append(("notice_quality", case["case_id"], case["candidate_text"]))
        for row in interview_evidence:
            documents.append(("interview_evidence", row["finding_id"], row["finding_summary"]))
            documents.append(("interview_limitation", row["finding_id"], row["limitation"]))

        hits: list[dict[str, str]] = []
        for dataset, item_id, text in documents:
            for pattern_name, pattern in PII_PATTERNS.items():
                if pattern.search(text):
                    hits.append({"dataset": dataset, "id": item_id, "pattern": pattern_name})
        return hits

    def _notice_quality_report(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        evaluator = NoticeQualityEvaluator(self.repository)
        issue_counts: Counter[str] = Counter()
        gate_counts: Counter[str] = Counter()
        total_core = preserved_core = 0
        total_critical = omitted_critical = unsupported = 0
        contract_mismatches: list[dict[str, Any]] = []

        for case in cases:
            result = evaluator.evaluate_case(case)
            actual_codes = [issue.code for issue in result.issues]
            issue_counts.update(actual_codes)
            gate_counts[result.gate] += 1
            total_core += result.core_value_total
            preserved_core += result.core_value_preserved
            total_critical += result.critical_value_total
            omitted_critical += result.critical_value_omitted
            unsupported += result.unsupported_value_count
            if actual_codes != case["expected_issue_codes"] or result.gate != case["expected_gate"]:
                contract_mismatches.append(
                    {
                        "case_id": case["case_id"],
                        "expected_issue_codes": case["expected_issue_codes"],
                        "actual_issue_codes": actual_codes,
                        "expected_gate": case["expected_gate"],
                        "actual_gate": result.gate,
                    }
                )

        return {
            "rows": len(cases),
            "locked": self.manifest["datasets"]["notice_quality_evaluation"]["locked"],
            "issue_distribution": dict(sorted(issue_counts.items())),
            "gate_distribution": dict(sorted(gate_counts.items())),
            "core_value_preservation_rate": round(preserved_core / total_core, 4)
            if total_core
            else 1.0,
            "critical_omission_rate": round(omitted_critical / total_critical, 4)
            if total_critical
            else 0.0,
            "unsupported_value_rate": round(unsupported / len(cases), 4) if cases else 0.0,
            "contract_mismatches": contract_mismatches,
            "contract_accuracy": round((len(cases) - len(contract_mismatches)) / len(cases), 4)
            if cases
            else 0.0,
            "injected_error_cases": sum(bool(case["expected_issue_codes"]) for case in cases),
            "interpretation": "detector_regression_fixture_not_model_performance",
        }


class ReviewComparator:
    """Compare two independent review files and prepare an adjudication queue."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    def compare(
        self, reviewer_a: Path, reviewer_b: Path, output: Path | None = None
    ) -> dict[str, Any]:
        rows_a, code_a = self._load_reviews(reviewer_a)
        rows_b, code_b = self._load_reviews(reviewer_b)
        if code_a == code_b:
            raise ValueError("review files must use different reviewer codes")
        if set(rows_a) != set(rows_b):
            missing_a = sorted(set(rows_b) - set(rows_a))
            missing_b = sorted(set(rows_a) - set(rows_b))
            raise ValueError(
                f"review request IDs differ: missing_a={missing_a}, missing_b={missing_b}"
            )

        pending: list[str] = []
        completed_pairs: list[tuple[dict[str, str], dict[str, str]]] = []
        disagreements: list[dict[str, str]] = []
        for request_id in sorted(rows_a):
            row_a = rows_a[request_id]
            row_b = rows_b[request_id]
            if not self._is_complete(row_a) or not self._is_complete(row_b):
                pending.append(request_id)
                continue
            completed_pairs.append((row_a, row_b))
            fields = self._disagreement_fields(row_a, row_b)
            if fields:
                disagreements.append(self._disagreement_row(row_a, row_b, fields))

        known_intents = [
            item["id"] for item in self.repository.load_yaml("knowledge/intents.yaml")["intents"]
        ] + [self.repository.load_yaml("knowledge/intents.yaml")["out_of_scope_label"]]
        known_domains = [
            item["id"] for item in self.repository.load_yaml("knowledge/domains.yaml")["domains"]
        ]
        completed = len(completed_pairs)
        intent_exact = self._exact_match_rate(completed_pairs, "intents")
        domain_exact = self._exact_match_rate(completed_pairs, "domains")
        workflow_exact = self._exact_match_rate(completed_pairs, "workflow_ids")
        intent_kappa = self._macro_binary_kappa(completed_pairs, "intents", known_intents)
        domain_kappa = self._macro_binary_kappa(completed_pairs, "domains", known_domains)

        report = {
            "reviewer_a": code_a,
            "reviewer_b": code_b,
            "total_rows": len(rows_a),
            "completed_rows": completed,
            "pending_rows": len(pending),
            "pending_request_ids": pending,
            "disagreement_rows": len(disagreements),
            "agreement": {
                "intent_exact_match": intent_exact,
                "domain_exact_match": domain_exact,
                "workflow_exact_match": workflow_exact,
                "intent_macro_kappa": intent_kappa,
                "domain_macro_kappa": domain_kappa,
            },
            "label_guide_ready": (
                completed == len(rows_a)
                and intent_kappa is not None
                and domain_kappa is not None
                and intent_kappa >= 0.70
                and domain_kappa >= 0.70
            ),
        }
        if output is not None:
            self._write_disagreements(output, disagreements)
            report["disagreement_output"] = str(output.resolve())
        return report

    @staticmethod
    def _load_reviews(path: Path) -> tuple[dict[str, dict[str, str]], str]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not set(REVIEW_COLUMNS) <= set(reader.fieldnames or []):
                raise ValueError(f"invalid review columns: {path}")
            rows = list(reader)
        indexed: dict[str, dict[str, str]] = {}
        reviewer_codes: set[str] = set()
        for row in rows:
            request_id = row["request_id"].strip()
            if request_id in indexed:
                raise ValueError(f"duplicate review request_id: {request_id}")
            indexed[request_id] = row
            reviewer_codes.add(row["reviewer_code"].strip())
        if len(reviewer_codes) != 1 or "" in reviewer_codes:
            raise ValueError(f"review file must contain one non-empty reviewer_code: {path}")
        return indexed, reviewer_codes.pop()

    @staticmethod
    def _is_complete(row: dict[str, str]) -> bool:
        return bool(row["intents"].strip() and row["decision"].strip())

    @staticmethod
    def _canonical_value(row: dict[str, str], field: str) -> Any:
        if field in {"intents", "domains", "workflow_ids", "missing_slots", "ambiguities"}:
            return frozenset(split_codes(row[field]))
        if field == "slots_json":
            try:
                return json.loads(row[field] or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid slots_json for {row['request_id']}: {exc}") from exc
        return row[field].strip()

    @classmethod
    def _disagreement_fields(cls, row_a: dict[str, str], row_b: dict[str, str]) -> list[str]:
        fields = [
            "intents",
            "domains",
            "workflow_ids",
            "slots_json",
            "missing_slots",
            "ambiguities",
            "sensitivity",
            "next_action",
            "decision",
        ]
        return [
            field
            for field in fields
            if cls._canonical_value(row_a, field) != cls._canonical_value(row_b, field)
        ]

    @staticmethod
    def _disagreement_row(
        row_a: dict[str, str], row_b: dict[str, str], fields: list[str]
    ) -> dict[str, str]:
        result = {
            "request_id": row_a["request_id"],
            "hr_utterance": row_a["hr_utterance"],
            "disagreement_fields": "|".join(fields),
            "adjudication_status": "PENDING",
        }
        for prefix, row in (("reviewer_a", row_a), ("reviewer_b", row_b)):
            result[f"{prefix}_code"] = row["reviewer_code"]
            for field in (
                "intents",
                "domains",
                "workflow_ids",
                "slots_json",
                "missing_slots",
                "ambiguities",
                "sensitivity",
                "next_action",
                "decision",
            ):
                result[f"{prefix}_{field}"] = row[field]
        return result

    @staticmethod
    def _exact_match_rate(
        pairs: list[tuple[dict[str, str], dict[str, str]]], field: str
    ) -> float | None:
        if not pairs:
            return None
        matches = sum(
            frozenset(split_codes(row_a[field])) == frozenset(split_codes(row_b[field]))
            for row_a, row_b in pairs
        )
        return round(matches / len(pairs), 4)

    @staticmethod
    def _macro_binary_kappa(
        pairs: list[tuple[dict[str, str], dict[str, str]]],
        field: str,
        labels: list[str],
    ) -> float | None:
        if not pairs:
            return None
        kappas: list[float] = []
        for label in labels:
            values_a = [label in split_codes(row_a[field]) for row_a, _ in pairs]
            values_b = [label in split_codes(row_b[field]) for _, row_b in pairs]
            observed = sum(a == b for a, b in zip(values_a, values_b, strict=True)) / len(pairs)
            positive_a = sum(values_a) / len(pairs)
            positive_b = sum(values_b) / len(pairs)
            expected = positive_a * positive_b + (1 - positive_a) * (1 - positive_b)
            if expected == 1:
                kappas.append(1.0 if observed == 1 else 0.0)
            else:
                kappas.append((observed - expected) / (1 - expected))
        return round(sum(kappas) / len(kappas), 4)

    @staticmethod
    def _write_disagreements(output: Path, rows: list[dict[str, str]]) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=DISAGREEMENT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)


def format_report(report: dict[str, Any]) -> str:
    readiness = report["readiness"]
    seed = report["seed"]
    evaluation = report["evaluation"]
    quality = report["quality"]
    notice_quality = report["notice_quality"]
    evidence = report["business_evidence"]
    lines = [
        f"MODEL\t{report['representative_model']}",
        f"SEED\trows={seed['rows']}\tgold={seed['gold_rows']}\t"
        f"multi_intent={seed['multi_intent_rows']}\tworkflow_expert_required="
        f"{seed['workflow_expert_review_required_rows']}",
        f"EVALUATION\trows={evaluation['rows']}\tlocked={evaluation['locked']}\t"
        f"missing_intents={len(evaluation['missing_in_scope_intents'])}",
        f"QUALITY\tseed_duplicates={len(seed['duplicate_utterances'])}\t"
        f"evaluation_duplicates={len(evaluation['duplicate_utterances'])}\t"
        f"split_overlap={len(quality['seed_evaluation_overlap'])}\t"
        f"pii_hits={len(quality['pii_pattern_hits'])}",
        f"NOTICE_QUALITY\trows={notice_quality['rows']}\t"
        f"contract_accuracy={notice_quality['contract_accuracy']}\t"
        f"injected_errors={notice_quality['injected_error_cases']}\t"
        f"contract_mismatches={len(notice_quality['contract_mismatches'])}",
        f"BUSINESS_EVIDENCE\trows={evidence['rows']}\tinterviews={evidence['interviews']}\t"
        f"quantitative_baselines={evidence['quantitative_baseline_rows']}",
        f"READY\tsmoke={readiness['smoke_evaluation_ready']}\t"
        f"gold_v1={readiness['gold_v1_ready']}\t"
        f"baseline={readiness['classification_baseline_ready']}",
        "INTENTS\t"
        + "\t".join(f"{intent}={count}" for intent, count in seed["intent_distribution"].items()),
    ]
    return "\n".join(lines)


def format_review_comparison(report: dict[str, Any]) -> str:
    agreement = report["agreement"]
    return "\n".join(
        [
            f"REVIEWERS\t{report['reviewer_a']}\t{report['reviewer_b']}",
            f"ROWS\ttotal={report['total_rows']}\tcompleted={report['completed_rows']}\t"
            f"pending={report['pending_rows']}\tdisagreements={report['disagreement_rows']}",
            f"AGREEMENT\tintent_exact={agreement['intent_exact_match']}\t"
            f"domain_exact={agreement['domain_exact_match']}\t"
            f"workflow_exact={agreement['workflow_exact_match']}",
            f"KAPPA\tintent={agreement['intent_macro_kappa']}\t"
            f"domain={agreement['domain_macro_kappa']}",
            f"READY\tlabel_guide={report['label_guide_ready']}",
        ]
    )
