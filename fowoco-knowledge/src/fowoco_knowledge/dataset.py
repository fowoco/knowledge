from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

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

    def build_report(self) -> dict[str, Any]:
        seed = self.load_seed()
        evaluation = self.load_evaluation()
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
        pii_hits = self._scan_pii(seed, evaluation)
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
        seed: list[dict[str, str]], evaluation: list[dict[str, Any]]
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

        hits: list[dict[str, str]] = []
        for dataset, item_id, text in documents:
            for pattern_name, pattern in PII_PATTERNS.items():
                if pattern.search(text):
                    hits.append({"dataset": dataset, "id": item_id, "pattern": pattern_name})
        return hits


def format_report(report: dict[str, Any]) -> str:
    readiness = report["readiness"]
    seed = report["seed"]
    evaluation = report["evaluation"]
    quality = report["quality"]
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
        f"READY\tsmoke={readiness['smoke_evaluation_ready']}\t"
        f"gold_v1={readiness['gold_v1_ready']}\t"
        f"baseline={readiness['classification_baseline_ready']}",
        "INTENTS\t"
        + "\t".join(f"{intent}={count}" for intent, count in seed["intent_distribution"].items()),
    ]
    return "\n".join(lines)
