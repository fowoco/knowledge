from __future__ import annotations

import csv
import json
from typing import Any

from jsonschema import Draft202012Validator

from .dataset import DatasetManager
from .ingestion import file_sha256
from .repository import KnowledgeRepository

SEED_COLUMNS = {
    "request_id",
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
    "expected_output",
    "review_status",
}

NEXT_ACTIONS = {
    "REQUEST_CLARIFICATION",
    "REQUEST_CLASSIFICATION_CONFIRMATION",
    "CREATE_DRAFT_TASK",
    "REQUIRE_HR_REVIEW",
    "SPLIT_AND_CONFIRM",
    "OUT_OF_SCOPE",
}

PROCESSED_DATASET_COLUMNS = {
    "required_documents_manufacturing.csv": {
        "requirement_id",
        "application_name",
        "document_name",
        "applicable_scope",
        "requirement_marker",
        "sample_form_available",
        "source_industry_text",
        "source_id",
        "source_version",
    },
    "manufacturing_industries.csv": {
        "industry_id",
        "major_category",
        "middle_category",
        "business_content_ko",
        "business_content_en",
        "source_id",
        "source_version",
    },
}


def split_codes(raw: str | None) -> list[str]:
    return [item.strip() for item in (raw or "").split("|") if item.strip()]


class KnowledgeValidator:
    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository
        self.errors: list[str] = []

    def validate_all(self) -> list[str]:
        self.errors = []
        self._validate_manifest_files()
        self._validate_processed_datasets()
        self._validate_dataset_manifest()
        self._validate_workflow_schema()
        self._validate_cross_references()
        self._validate_seed_data()
        self._validate_evaluation_data()
        return self.errors

    def _validate_dataset_manifest(self) -> None:
        schema = self.repository.load_json("schemas/dataset-manifest.schema.json")
        manifest = self.repository.load_yaml("data/dataset_manifest.yaml")
        validator = Draft202012Validator(schema)
        for error in validator.iter_errors(manifest):
            path = ".".join(str(item) for item in error.path)
            self.errors.append(f"dataset manifest [{path}]: {error.message}")

        for dataset_id, dataset in manifest.get("datasets", {}).items():
            path = self.repository.root / dataset["path"]
            if not path.is_file():
                self.errors.append(f"dataset {dataset_id}: missing {dataset['path']}")
                continue
            expected_sha256 = dataset.get("sha256")
            if dataset.get("locked") and not expected_sha256:
                self.errors.append(f"dataset {dataset_id}: locked dataset requires sha256")
            if expected_sha256 and file_sha256(path) != expected_sha256:
                self.errors.append(f"dataset {dataset_id}: checksum mismatch")

        report = DatasetManager(self.repository).build_report()
        if report["seed"]["duplicate_utterances"]:
            self.errors.append("seed dataset contains duplicate utterances")
        if report["evaluation"]["duplicate_utterances"]:
            self.errors.append("evaluation dataset contains duplicate utterances")
        if report["quality"]["seed_evaluation_overlap"]:
            self.errors.append("seed and evaluation datasets overlap")
        if report["quality"]["pii_pattern_hits"]:
            self.errors.append("seed or evaluation dataset contains a PII pattern")

    def _validate_manifest_files(self) -> None:
        manifest = self.repository.manifest
        for key, relative_path in manifest.get("files", {}).items():
            if not (self.repository.root / relative_path).is_file():
                self.errors.append(f"manifest file missing: {key} -> {relative_path}")
        for key, relative_path in manifest.get("datasets", {}).items():
            if not (self.repository.root / relative_path).is_file():
                self.errors.append(f"manifest dataset missing: {key} -> {relative_path}")

    def _validate_processed_datasets(self) -> None:
        processed_manifest_path = self.repository.root / "data/processed/manifest.yaml"
        if not processed_manifest_path.is_file():
            return
        processed_manifest = self.repository.load_yaml("data/processed/manifest.yaml")
        source_manifest = self.repository.load_yaml("data/external/source_manifest.yaml")
        known_sources = {item["id"] for item in source_manifest["sources"]}

        for dataset in processed_manifest.get("datasets", []):
            filename = dataset["path"]
            path = self.repository.root / "data/processed" / filename
            if not path.is_file():
                self.errors.append(f"processed dataset missing: {filename}")
                continue
            if dataset["source_id"] not in known_sources:
                self.errors.append(
                    f"processed dataset {filename}: unknown source {dataset['source_id']}"
                )
            if file_sha256(path) != dataset["sha256"]:
                self.errors.append(f"processed dataset {filename}: checksum mismatch")

            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            if len(rows) != dataset["row_count"]:
                self.errors.append(f"processed dataset {filename}: row count mismatch")
            expected_columns = PROCESSED_DATASET_COLUMNS.get(filename)
            if expected_columns and set(reader.fieldnames or []) != expected_columns:
                self.errors.append(f"processed dataset {filename}: column mismatch")
            if filename == "manufacturing_industries.csv" and any(
                row["major_category"] != "제조업" for row in rows
            ):
                self.errors.append(f"processed dataset {filename}: non-manufacturing row")
            critical_fields = {
                "required_documents_manufacturing.csv": [
                    "requirement_id",
                    "application_name",
                    "document_name",
                ],
                "manufacturing_industries.csv": [
                    "industry_id",
                    "middle_category",
                    "business_content_ko",
                ],
            }.get(filename, [])
            for line_number, row in enumerate(rows, start=2):
                if any(not row.get(field, "").strip() for field in critical_fields):
                    self.errors.append(
                        f"processed dataset {filename} line {line_number}: blank critical field"
                    )

    def _validate_workflow_schema(self) -> None:
        schema = self.repository.load_json("schemas/workflow-catalog.schema.json")
        catalog = self.repository.load_yaml("knowledge/workflow_catalog.yaml")
        validator = Draft202012Validator(schema)
        for error in validator.iter_errors(catalog):
            path = ".".join(str(item) for item in error.path)
            self.errors.append(f"workflow schema [{path}]: {error.message}")

    def _validate_cross_references(self) -> None:
        context = self.repository.load_context_files()
        intents = self._index_unique(context["intents"]["intents"], "intent")
        domains = self._index_unique(context["domains"]["domains"], "domain")
        sources = self._index_unique(context["sources"]["sources"], "source")
        workflows = self._index_unique(context["workflows"]["workflows"], "workflow")
        checklists = self._index_unique(context["checklists"]["checklists"], "checklist")
        procedures = self._index_unique(context["procedures"]["procedures"], "procedure")
        slot_refs = context["slots"]["workflow_requirements"]

        for workflow_id, workflow in workflows.items():
            if workflow["intent"] not in intents:
                self.errors.append(f"{workflow_id}: unknown intent {workflow['intent']}")
            for domain in workflow["domains"]:
                if domain not in domains:
                    self.errors.append(f"{workflow_id}: unknown domain {domain}")
            for source_id in workflow["source_ids"]:
                if source_id not in sources:
                    self.errors.append(f"{workflow_id}: unknown source {source_id}")
            if workflow["required_slots_ref"] not in slot_refs:
                self.errors.append(
                    f"{workflow_id}: unknown slot policy {workflow['required_slots_ref']}"
                )
            checklist_id = workflow.get("checklist_id")
            if checklist_id and checklist_id not in checklists:
                self.errors.append(f"{workflow_id}: unknown checklist {checklist_id}")

        document_types = set(context["checklists"]["document_types"])
        for checklist_id, checklist in checklists.items():
            if checklist["workflow_id"] not in workflows:
                self.errors.append(f"{checklist_id}: unknown workflow {checklist['workflow_id']}")
            for item in checklist["items"]:
                if item["document_type"] not in document_types:
                    self.errors.append(
                        f"{checklist_id}: unknown document type {item['document_type']}"
                    )
            for source_id in checklist.get("official_sources", []):
                if source_id not in sources:
                    self.errors.append(f"{checklist_id}: unknown source {source_id}")

        for template in context["multilingual_templates"]["templates"]:
            if template["workflow_id"] not in workflows:
                self.errors.append(f"{template['id']}: unknown workflow {template['workflow_id']}")

        required_documents = self.repository.load_csv(
            "data/processed/required_documents_manufacturing.csv"
        )
        application_names = {row["application_name"] for row in required_documents}
        for procedure_id, procedure in procedures.items():
            if procedure["workflow_id"] not in workflows:
                self.errors.append(f"{procedure_id}: unknown workflow {procedure['workflow_id']}")
            for source_id in procedure["source_ids"]:
                if source_id not in sources:
                    self.errors.append(f"{procedure_id}: unknown source {source_id}")
            for key in ("next_workflow_ids", "possible_prerequisite_workflow_ids"):
                for workflow_id in procedure.get(key, []):
                    if workflow_id not in workflows:
                        self.errors.append(f"{procedure_id}: unknown workflow {workflow_id}")
            application_name = procedure.get("dataset_application_name")
            if application_name and application_name not in application_names:
                self.errors.append(
                    f"{procedure_id}: unknown dataset application {application_name}"
                )

        valid_guardrail_targets = set(intents) | {"ALL"}
        for rule in context["guardrails"]["rules"]:
            for target in rule["applies_to"]:
                if target not in valid_guardrail_targets:
                    self.errors.append(f"{rule['id']}: unknown applies_to {target}")

    def _validate_seed_data(self) -> None:
        context = self.repository.load_context_files()
        known_intents = {item["id"] for item in context["intents"]["intents"]} | {
            context["intents"]["out_of_scope_label"]
        }
        known_domains = {item["id"] for item in context["domains"]["domains"]}
        known_workflows = {item["id"] for item in context["workflows"]["workflows"]}
        known_sources = set(self.repository.load_yaml("data/provenance.yaml")["sources"])
        review_statuses = set(self.repository.load_yaml("data/provenance.yaml")["review_statuses"])
        input_modes = set(self.repository.manifest["input_modes"])

        path = self.repository.root / "data/seed/gold_seed.csv"
        seen: set[str] = set()
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if set(reader.fieldnames or []) != SEED_COLUMNS:
                self.errors.append("seed CSV columns do not match the documented schema")
                return
            for line_number, row in enumerate(reader, start=2):
                request_id = row["request_id"]
                if request_id in seen:
                    self.errors.append(f"seed line {line_number}: duplicate {request_id}")
                seen.add(request_id)
                self._check_codes(line_number, "intent", split_codes(row["intents"]), known_intents)
                self._check_codes(line_number, "domain", split_codes(row["domains"]), known_domains)
                self._check_codes(
                    line_number, "workflow", split_codes(row["workflow_ids"]), known_workflows
                )
                if row["source"] not in known_sources:
                    self.errors.append(f"seed line {line_number}: unknown source {row['source']}")
                if row["input_mode"] not in input_modes:
                    self.errors.append(
                        f"seed line {line_number}: invalid input_mode {row['input_mode']}"
                    )
                if row["next_action"] not in NEXT_ACTIONS:
                    self.errors.append(
                        f"seed line {line_number}: invalid next_action {row['next_action']}"
                    )
                if row["review_status"] not in review_statuses:
                    self.errors.append(
                        f"seed line {line_number}: invalid review_status {row['review_status']}"
                    )
                try:
                    parsed_slots = json.loads(row["slots_json"])
                    if not isinstance(parsed_slots, dict):
                        raise TypeError("slots_json must be an object")
                except (json.JSONDecodeError, TypeError) as exc:
                    self.errors.append(f"seed line {line_number}: invalid slots_json ({exc})")

    def _validate_evaluation_data(self) -> None:
        schema = self.repository.load_json("schemas/golden-case.schema.json")
        validator = Draft202012Validator(schema)
        context = self.repository.load_context_files()
        known_intents = {item["id"] for item in context["intents"]["intents"]} | {
            context["intents"]["out_of_scope_label"]
        }
        known_domains = {item["id"] for item in context["domains"]["domains"]}
        known_workflows = {item["id"] for item in context["workflows"]["workflows"]}
        seen: set[str] = set()
        path = self.repository.root / "data/evaluation/golden_cases.jsonl"
        for line_number, raw_line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not raw_line.strip():
                continue
            try:
                case = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                self.errors.append(f"evaluation line {line_number}: invalid JSON ({exc})")
                continue
            for error in validator.iter_errors(case):
                self.errors.append(f"evaluation line {line_number}: {error.message}")
            case_id = case.get("case_id")
            if case_id in seen:
                self.errors.append(f"evaluation line {line_number}: duplicate {case_id}")
            seen.add(case_id)
            self._check_codes(
                line_number, "intent", case.get("expected_intents", []), known_intents
            )
            self._check_codes(
                line_number, "domain", case.get("expected_domains", []), known_domains
            )
            self._check_codes(
                line_number,
                "workflow",
                case.get("expected_workflow_ids", []),
                known_workflows,
            )

    def _index_unique(self, items: list[dict[str, Any]], kind: str) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for item in items:
            item_id = item["id"]
            if item_id in indexed:
                self.errors.append(f"duplicate {kind} id: {item_id}")
            indexed[item_id] = item
        return indexed

    def _check_codes(self, line_number: int, kind: str, values: list[str], known: set[str]) -> None:
        for value in values:
            if value not in known:
                self.errors.append(f"line {line_number}: unknown {kind} {value}")
