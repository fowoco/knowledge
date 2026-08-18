from __future__ import annotations

import csv
import json
import re
from collections import Counter
from typing import Any

from jsonschema import Draft202012Validator

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

INTENT_DATA_PII_PATTERNS = {
    "resident_or_alien_registration_number": re.compile(r"(?<!\d)\d{6}-?[1-8]\d{6}(?!\d)"),
    "mobile_phone_number": re.compile(r"(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)"),
    "passport_number": re.compile(r"(?<![A-Z0-9])[A-Z]{1,2}\d{7,8}(?![A-Z0-9])"),
}


def find_internal_keys(text: str, internal_keys: set[str]) -> list[str]:
    """Return machine-facing identifiers exposed in user-facing text."""
    found: list[str] = []
    for key in sorted(internal_keys):
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append(key)
    return found


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
        self._validate_workflow_schema()
        self._validate_required_slot_contracts()
        self._validate_cross_references()
        self._validate_seed_data()
        self._validate_evaluation_data()
        self._validate_catalog_e2e_data()
        self._validate_intent_data()
        self._validate_intent_split()
        return self.errors

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

    def _validate_required_slot_contracts(self) -> None:
        config = self.repository.load_yaml("knowledge/required_slots.yaml")
        schema = self.repository.load_json("schemas/required-slots.schema.json")
        schema_errors = list(Draft202012Validator(schema).iter_errors(config))
        for error in schema_errors:
            path = ".".join(str(item) for item in error.path)
            self.errors.append(f"required slots schema [{path}]: {error.message}")
        if schema_errors:
            return

        known_slots = set(config["slot_definitions"])
        known_sources = set(config["source_priority_definitions"])
        known_rules = set(config["validation_rule_definitions"])
        workflows = {
            item["id"]: item
            for item in self.repository.load_yaml("knowledge/workflow_catalog.yaml")["workflows"]
        }
        internal_keys = self._user_facing_internal_keys()

        for workflow_id, requirement in config["workflow_requirements"].items():
            if workflow_id not in workflows:
                self.errors.append(f"slot contract: unknown workflow {workflow_id}")
                continue
            if workflows[workflow_id]["required_slots_ref"] != workflow_id:
                self.errors.append(f"slot contract: workflow ref mismatch {workflow_id}")

            required = set(requirement["required"])
            optional = set(requirement.get("optional", []))
            contracts = requirement["slot_contracts"]
            contract_names = set(contracts)
            if required & optional:
                self.errors.append(f"slot contract {workflow_id}: required and optional overlap")
            if contract_names != required | optional:
                self.errors.append(
                    f"slot contract {workflow_id}: contracts must match required and optional slots"
                )
            if not set(requirement["resolvable_from_context"]) <= contract_names:
                self.errors.append(
                    f"slot contract {workflow_id}: unknown resolvable_from_context slot"
                )

            for slot_name, contract in contracts.items():
                if slot_name not in known_slots:
                    self.errors.append(f"slot contract {workflow_id}: unknown slot {slot_name}")
                if contract["required"] != (slot_name in required):
                    self.errors.append(
                        f"slot contract {workflow_id}.{slot_name}: required flag mismatch"
                    )
                for source in contract["source_priority"]:
                    if source not in known_sources:
                        self.errors.append(
                            f"slot contract {workflow_id}.{slot_name}: unknown source {source}"
                        )
                for rule in contract["validation_rules"]:
                    if rule not in known_rules:
                        self.errors.append(
                            f"slot contract {workflow_id}.{slot_name}: unknown rule {rule}"
                        )
                for field in ("display_name_ko", "worker_prompt_easy_ko"):
                    leaked = find_internal_keys(contract[field], internal_keys)
                    if leaked:
                        self.errors.append(
                            f"slot contract {workflow_id}.{slot_name}: internal key exposed "
                            f"in {field} ({', '.join(leaked)})"
                        )

    def _validate_cross_references(self) -> None:
        context = self.repository.load_context_files()
        intents = self._index_unique(context["intents"]["intents"], "intent")
        domains = self._index_unique(context["domains"]["domains"], "domain")
        sources = self._index_unique(context["sources"]["sources"], "source")
        workflows = self._index_unique(context["workflows"]["workflows"], "workflow")
        case_templates = self._index_unique(context["workflows"]["case_templates"], "case template")
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

        for template_id, template in case_templates.items():
            if template["intent"] not in intents:
                self.errors.append(f"{template_id}: unknown intent {template['intent']}")
            for workflow_id in template["workflow_ids"]:
                if workflow_id not in workflows:
                    self.errors.append(f"{template_id}: unknown workflow {workflow_id}")
            task_keys = {task["key"] for task in template["tasks"]}
            tasks_by_key = {task["key"]: task for task in template["tasks"]}
            if len(task_keys) != len(template["tasks"]):
                self.errors.append(f"{template_id}: duplicate task key")
            task_orders = {task["order"] for task in template["tasks"]}
            if len(task_orders) != len(template["tasks"]):
                self.errors.append(f"{template_id}: duplicate task order")
            for task in template["tasks"]:
                if task["workflow_id"] not in template["workflow_ids"]:
                    self.errors.append(
                        f"{template_id}.{task['key']}: workflow not declared by template"
                    )
                dependencies = task["depends_on"] + task["depends_on_if_present"]
                for dependency in dependencies:
                    if dependency not in task_keys:
                        self.errors.append(
                            f"{template_id}.{task['key']}: unknown dependency {dependency}"
                        )
                    if dependency == task["key"]:
                        self.errors.append(
                            f"{template_id}.{task['key']}: task cannot depend on itself"
                        )
                    elif dependency in tasks_by_key and (
                        tasks_by_key[dependency]["order"] >= task["order"]
                    ):
                        self.errors.append(
                            f"{template_id}.{task['key']}: dependency {dependency} "
                            "must have a lower order"
                        )

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

    def _validate_catalog_e2e_data(self) -> None:
        manifest = self.repository.load_yaml("data/evaluation/e2e_catalog_manifest.yaml")
        path = self.repository.root / manifest["path"]
        schema = self.repository.load_json(manifest["schema"])
        validator = Draft202012Validator(schema)
        context = self.repository.load_context_files()
        known_intents = {item["id"] for item in context["intents"]["intents"]} | {
            context["intents"]["out_of_scope_label"]
        }
        known_workflows = {item["id"] for item in context["workflows"]["workflows"]}
        known_slots = set(context["slots"]["slot_definitions"])
        supported_locales = set(self.repository.manifest["supported_worker_locales"]) | {
            self.repository.manifest["default_locale"]
        }
        internal_keys = self._user_facing_internal_keys()

        if file_sha256(path) != manifest["sha256"]:
            self.errors.append("catalog e2e data: checksum mismatch")

        cases: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for line_number, raw_line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not raw_line.strip():
                continue
            try:
                case = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                self.errors.append(f"catalog e2e line {line_number}: invalid JSON ({exc})")
                continue
            cases.append(case)
            for error in validator.iter_errors(case):
                error_path = ".".join(str(item) for item in error.path)
                location = f" [{error_path}]" if error_path else ""
                self.errors.append(f"catalog e2e line {line_number}{location}: {error.message}")

            case_id = case.get("case_id")
            if case_id in seen_ids:
                self.errors.append(f"catalog e2e line {line_number}: duplicate {case_id}")
            seen_ids.add(case_id)
            self._check_codes(
                line_number, "intent", case.get("expected_intents", []), known_intents
            )
            self._check_codes(
                line_number,
                "workflow",
                case.get("expected_workflow_ids", []),
                known_workflows,
            )
            self._check_codes(
                line_number,
                "slot",
                list(case.get("expected_slots", {})),
                known_slots,
            )

            intents = case.get("expected_intents", [])
            workflows = case.get("expected_workflow_ids", [])
            if "OUT_OF_SCOPE" in intents and (len(intents) != 1 or workflows):
                self.errors.append(
                    f"catalog e2e line {line_number}: OUT_OF_SCOPE must not have workflows"
                )

            workers = {
                worker["worker_id"]: worker
                for worker in case.get("directory_context", {}).get("workers", [])
            }
            lookup = case.get("expected_subject_lookup", {})
            worker_id = lookup.get("worker_id")
            candidates = set(lookup.get("candidate_worker_ids", []))
            if worker_id is not None and worker_id not in workers:
                self.errors.append(
                    f"catalog e2e line {line_number}: matched worker missing from directory"
                )
            if not candidates <= set(workers):
                self.errors.append(
                    f"catalog e2e line {line_number}: candidate worker missing from directory"
                )
            if lookup.get("status") == "AMBIGUOUS" and not lookup.get("requires_confirmation"):
                self.errors.append(
                    f"catalog e2e line {line_number}: ambiguous name must require confirmation"
                )
            if lookup.get("match_basis") == "PHONETIC_ALIAS" and not lookup.get(
                "requires_confirmation"
            ):
                self.errors.append(
                    f"catalog e2e line {line_number}: phonetic alias must require confirmation"
                )

            for notice in case.get("worker_notices", []):
                if notice["locale"] not in supported_locales:
                    self.errors.append(f"catalog e2e line {line_number}: unsupported notice locale")
                missing_values = [
                    value for value in notice["critical_values"] if value not in notice["text"]
                ]
                if missing_values:
                    self.errors.append(
                        f"catalog e2e line {line_number}: notice loses critical values "
                        f"({', '.join(missing_values)})"
                    )
                leaked = find_internal_keys(notice["text"], internal_keys)
                if leaked:
                    self.errors.append(
                        f"catalog e2e line {line_number}: notice exposes internal keys "
                        f"({', '.join(leaked)})"
                    )

            for text in [
                case.get("hr_input", ""),
                *[n["text"] for n in case.get("worker_notices", [])],
            ]:
                for pii_kind, pattern in INTENT_DATA_PII_PATTERNS.items():
                    if pattern.search(text):
                        self.errors.append(
                            f"catalog e2e line {line_number}: possible PII ({pii_kind})"
                        )

        if len(cases) != manifest["record_count"]:
            self.errors.append("catalog e2e data: record count mismatch")

        tags = {tag for case in cases for tag in case.get("scenario_tags", [])}
        required_tags = {
            "SPACING_VARIANT",
            "ROMANIZED_ALIAS",
            "CASE_VARIANT",
            "PHONETIC_ALIAS",
            "AMBIGUOUS_NAME",
            "COMPOSITE_REQUEST",
            "BOUNDARY_INTENT",
            "OUT_OF_SCOPE",
            "VIETNAMESE_NOTICE",
            "EXTERNAL_EXECUTION",
        }
        if not required_tags <= tags:
            self.errors.append("catalog e2e data: required scenario coverage is missing")
        if manifest["status"] == "pending_independent_review" and any(
            case.get("review", {}).get("adjudication") != "PENDING" for case in cases
        ):
            self.errors.append("catalog e2e data: review status conflicts with manifest")

    def _user_facing_internal_keys(self) -> set[str]:
        context = self.repository.load_context_files()
        keys = set(context["slots"]["slot_definitions"])
        keys.update(item["id"] for item in context["intents"]["intents"])
        keys.add(context["intents"]["out_of_scope_label"])
        for workflow in context["workflows"]["workflows"]:
            keys.add(workflow["id"])
            keys.update(step["id"] for step in workflow["steps"])
            keys.update(step["output"] for step in workflow["steps"])
        keys.update(item["id"] for item in context["sources"]["sources"])
        return keys

    def _validate_intent_data(self) -> None:
        intent_manifest = self.repository.load_yaml("data/intent/manifest.yaml")
        schema = self.repository.load_json(intent_manifest["schema"])
        validator = Draft202012Validator(schema)
        context = self.repository.load_context_files()
        known_intents = {item["id"] for item in context["intents"]["intents"]} | {
            context["intents"]["out_of_scope_label"]
        }
        out_of_scope_label = context["intents"]["out_of_scope_label"]
        seen_ids: set[int] = set()
        seen_inputs: set[str] = set()
        path = self.repository.root / intent_manifest["path"]
        record_count = 0

        for line_number, raw_line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not raw_line.strip():
                continue
            record_count += 1
            try:
                case = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                self.errors.append(f"intent data line {line_number}: invalid JSON ({exc})")
                continue
            if not isinstance(case, dict):
                self.errors.append(f"intent data line {line_number}: record must be an object")
                continue

            for error in validator.iter_errors(case):
                error_path = ".".join(str(item) for item in error.path)
                location = f" [{error_path}]" if error_path else ""
                self.errors.append(f"intent data line {line_number}{location}: {error.message}")

            case_id = case.get("id")
            if isinstance(case_id, int):
                if case_id in seen_ids:
                    self.errors.append(f"intent data line {line_number}: duplicate id {case_id}")
                seen_ids.add(case_id)

            hr_input = case.get("hr_input")
            if not isinstance(hr_input, str):
                continue
            if not hr_input.strip():
                self.errors.append(f"intent data line {line_number}: blank hr_input")
                continue

            normalized_input = " ".join(hr_input.split()).casefold()
            if normalized_input in seen_inputs:
                self.errors.append(f"intent data line {line_number}: duplicate normalized hr_input")
            seen_inputs.add(normalized_input)

            for pii_kind, pattern in INTENT_DATA_PII_PATTERNS.items():
                if pattern.search(hr_input):
                    self.errors.append(f"intent data line {line_number}: possible PII ({pii_kind})")

            intents = case.get("intents")
            if not isinstance(intents, list):
                continue

            intent_codes: list[str] = []
            evidence_positions: list[int] = []
            for item in intents:
                if not isinstance(item, dict):
                    continue
                intent = item.get("intent")
                evidence = item.get("evidence")
                if isinstance(intent, str):
                    if intent in intent_codes:
                        self.errors.append(
                            f"intent data line {line_number}: duplicate intent {intent}"
                        )
                    intent_codes.append(intent)
                    if intent not in known_intents:
                        self.errors.append(
                            f"intent data line {line_number}: unknown intent {intent}"
                        )

                if intent == out_of_scope_label:
                    continue
                if isinstance(evidence, str) and evidence:
                    position = hr_input.find(evidence)
                    if position < 0:
                        self.errors.append(
                            f"intent data line {line_number}: evidence is not an exact substring"
                        )
                    else:
                        evidence_positions.append(position)

            if out_of_scope_label in intent_codes and len(intent_codes) != 1:
                self.errors.append(
                    f"intent data line {line_number}: OUT_OF_SCOPE must be the only intent"
                )
            if evidence_positions != sorted(evidence_positions):
                self.errors.append(
                    f"intent data line {line_number}: intents are not in evidence order"
                )

        if record_count != intent_manifest["record_count"]:
            self.errors.append("intent data: record count mismatch")
        if file_sha256(path) != intent_manifest["sha256"]:
            self.errors.append("intent data: checksum mismatch")

        review = intent_manifest.get("review", {})
        pre_review_relative_path = review.get("pre_review_path")
        if pre_review_relative_path:
            pre_review_path = self.repository.root / pre_review_relative_path
            if not pre_review_path.is_file():
                self.errors.append("intent data: pre-review archive missing")
                return
            if file_sha256(pre_review_path) != review.get("pre_review_sha256"):
                self.errors.append("intent data: pre-review archive checksum mismatch")

            final_cases = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            pre_review_cases = [
                json.loads(line)
                for line in pre_review_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            final_identity = [(case["id"], case["hr_input"]) for case in final_cases]
            pre_review_identity = [(case["id"], case["hr_input"]) for case in pre_review_cases]
            if review.get("ids_and_hr_inputs_unchanged") and final_identity != pre_review_identity:
                self.errors.append("intent data: pre-review IDs or inputs differ from final data")
            changed_count = sum(
                final_case["intents"] != pre_review_case["intents"]
                for final_case, pre_review_case in zip(final_cases, pre_review_cases, strict=False)
            )
            if changed_count != review.get("changed_label_record_count"):
                self.errors.append("intent data: changed label record count mismatch")

    def _validate_intent_split(self) -> None:
        manifest = self.repository.load_yaml("data/intent/splits/manifest.yaml")
        schema = self.repository.load_json(manifest["schema"])
        schema_errors = list(Draft202012Validator(schema).iter_errors(manifest))
        for error in schema_errors:
            path = ".".join(str(item) for item in error.path)
            self.errors.append(f"intent split schema [{path}]: {error.message}")
        if schema_errors:
            return

        intent_manifest = self.repository.load_yaml("data/intent/manifest.yaml")
        source = manifest["source"]
        source_path = self.repository.root / source["path"]
        if source["path"] != intent_manifest["path"]:
            self.errors.append("intent split: source path differs from intent manifest")
        if source["sha256"] != intent_manifest["sha256"]:
            self.errors.append("intent split: source checksum differs from intent manifest")
        if not source_path.is_file():
            self.errors.append("intent split: source file missing")
            return
        if file_sha256(source_path) != source["sha256"]:
            self.errors.append("intent split: source checksum mismatch")

        cases = [
            json.loads(line)
            for line in source_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        case_by_id = {case["id"]: case for case in cases}
        source_ids = set(case_by_id)
        if len(cases) != source["record_count"]:
            self.errors.append("intent split: source record count mismatch")
        if len(case_by_id) != len(cases):
            self.errors.append("intent split: duplicate source id")

        split_ids: dict[str, set[int]] = {}
        for split_name in ("train", "validation"):
            output = manifest["outputs"][split_name]
            output_path = self.repository.root / output["path"]
            if not output_path.is_file():
                self.errors.append(f"intent split {split_name}: output file missing")
                continue
            if file_sha256(output_path) != output["sha256"]:
                self.errors.append(f"intent split {split_name}: checksum mismatch")

            raw_ids = [
                line.strip()
                for line in output_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            try:
                parsed_ids = [int(case_id) for case_id in raw_ids]
            except ValueError:
                self.errors.append(f"intent split {split_name}: non-integer id")
                continue

            current_ids = set(parsed_ids)
            split_ids[split_name] = current_ids
            if len(parsed_ids) != output["record_count"]:
                self.errors.append(f"intent split {split_name}: record count mismatch")
            if len(current_ids) != len(parsed_ids):
                self.errors.append(f"intent split {split_name}: duplicate id")
            if current_ids - source_ids:
                self.errors.append(f"intent split {split_name}: unknown source id")

        if set(split_ids) != {"train", "validation"}:
            return

        train_ids = split_ids["train"]
        validation_ids = split_ids["validation"]
        if train_ids & validation_ids:
            self.errors.append("intent split: train and validation overlap")
        if train_ids | validation_ids != source_ids:
            self.errors.append("intent split: source ids are missing or duplicated across outputs")

        policy = manifest["policy"]
        if manifest["outputs"]["train"]["record_count"] != policy["target_train_count"]:
            self.errors.append("intent split: train count differs from policy target")
        if manifest["outputs"]["validation"]["record_count"] != policy["target_validation_count"]:
            self.errors.append("intent split: validation count differs from policy target")

        normalization = policy["template_normalization"]
        worker_id_pattern = re.compile(normalization["worker_id_pattern"])

        def normalize_template(value: str) -> str:
            normalized = worker_id_pattern.sub(normalization["worker_id_replacement"], value)
            if normalization["collapse_whitespace"]:
                normalized = " ".join(normalized.split())
            if normalization["casefold"]:
                normalized = normalized.casefold()
            return normalized

        template_groups: dict[str, set[int]] = {}
        for case in cases:
            template = normalize_template(case["hr_input"])
            template_groups.setdefault(template, set()).add(case["id"])
        if any(group & train_ids and group & validation_ids for group in template_groups.values()):
            self.errors.append("intent split: normalized template leaks across outputs")

        statistics = manifest["statistics"]
        group_sizes = [len(group) for group in template_groups.values()]
        if len(template_groups) != statistics["template_group_count"]:
            self.errors.append("intent split: template group count mismatch")
        if sum(size > 1 for size in group_sizes) != statistics["duplicate_template_group_count"]:
            self.errors.append("intent split: duplicate template group count mismatch")
        if max(group_sizes, default=0) != statistics["max_template_group_size"]:
            self.errors.append("intent split: maximum template group size mismatch")
        for split_name, ids in {
            "source": source_ids,
            "train": train_ids,
            "validation": validation_ids,
        }.items():
            selected_cases = [case_by_id[case_id] for case_id in ids]
            label_counts = Counter(
                item["intent"] for case in selected_cases for item in case["intents"]
            )
            cardinality_counts = Counter(str(len(case["intents"])) for case in selected_cases)
            if dict(label_counts) != statistics["label_counts"][split_name]:
                self.errors.append(f"intent split {split_name}: label statistics mismatch")
            if dict(cardinality_counts) != statistics["intent_cardinality_counts"][split_name]:
                self.errors.append(f"intent split {split_name}: cardinality statistics mismatch")

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
