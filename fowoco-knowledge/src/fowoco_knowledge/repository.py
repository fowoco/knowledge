from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import yaml


class KnowledgeNotFoundError(FileNotFoundError):
    """Raised when the knowledge project root cannot be located."""


def discover_project_root(explicit_root: str | Path | None = None) -> Path:
    """Find the directory containing ``knowledge/manifest.yaml``."""
    candidates: list[Path] = []
    if explicit_root:
        candidates.append(Path(explicit_root))

    env_root = os.getenv("FOWOCO_KNOWLEDGE_ROOT")
    if env_root:
        candidates.append(Path(env_root))

    cwd = Path.cwd()
    candidates.extend([cwd, cwd / "fowoco-knowledge"])

    source_path = Path(__file__).resolve()
    candidates.extend(source_path.parents)

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / "knowledge" / "manifest.yaml").is_file():
            return resolved

    raise KnowledgeNotFoundError(
        "FOWOCO knowledge root를 찾지 못했습니다. --root 또는 FOWOCO_KNOWLEDGE_ROOT를 지정하세요."
    )


class KnowledgeRepository:
    """Read versioned FOWOCO context files and compile an Agent context."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = discover_project_root(root)

    def load_yaml(self, relative_path: str | Path) -> dict[str, Any]:
        path = self.root / relative_path
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"YAML root must be a mapping: {path}")
        return data

    def load_json(self, relative_path: str | Path) -> dict[str, Any]:
        import json

        path = self.root / relative_path
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"JSON root must be an object: {path}")
        return data

    def load_csv(self, relative_path: str | Path) -> list[dict[str, str]]:
        path = self.root / relative_path
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @property
    def manifest(self) -> dict[str, Any]:
        return self.load_yaml("knowledge/manifest.yaml")

    def load_context_files(self) -> dict[str, dict[str, Any]]:
        return {
            key: self.load_yaml(relative_path)
            for key, relative_path in self.manifest["files"].items()
        }

    def list_workflows(self) -> list[dict[str, Any]]:
        return self.load_yaml("knowledge/workflow_catalog.yaml")["workflows"]

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        for workflow in self.list_workflows():
            if workflow["id"] == workflow_id:
                return workflow
        raise KeyError(f"Unknown workflow_id: {workflow_id}")

    def list_required_documents(self, application_name: str) -> list[dict[str, str]]:
        rows = self.load_csv("data/processed/required_documents_manufacturing.csv")
        return [row for row in rows if row["application_name"] == application_name]

    def search_manufacturing_industries(self, query: str, limit: int = 20) -> list[dict[str, str]]:
        normalized_query = query.casefold().strip()
        if not normalized_query:
            return []
        rows = self.load_csv("data/processed/manufacturing_industries.csv")
        matches = [
            row
            for row in rows
            if normalized_query
            in " ".join(
                [
                    row["middle_category"],
                    row["business_content_ko"],
                    row["business_content_en"],
                ]
            ).casefold()
        ]
        return matches[: max(0, limit)]

    def compile_context(self, workflow_id: str) -> dict[str, Any]:
        """Build the smallest coherent context bundle for one Workflow."""
        context = self.load_context_files()
        workflow = next(
            item for item in context["workflows"]["workflows"] if item["id"] == workflow_id
        )

        intent = next(
            item for item in context["intents"]["intents"] if item["id"] == workflow["intent"]
        )
        domains = [
            item for item in context["domains"]["domains"] if item["id"] in workflow["domains"]
        ]
        slot_policy = context["slots"]["workflow_requirements"][workflow["required_slots_ref"]]
        sources = [
            item for item in context["sources"]["sources"] if item["id"] in workflow["source_ids"]
        ]
        guardrails = [
            item
            for item in context["guardrails"]["rules"]
            if "ALL" in item["applies_to"] or workflow["intent"] in item["applies_to"]
        ]
        checklist = next(
            (
                item
                for item in context["checklists"]["checklists"]
                if item["workflow_id"] == workflow_id
            ),
            None,
        )
        templates = [
            item
            for item in context["multilingual_templates"]["templates"]
            if item["workflow_id"] == workflow_id
        ]
        administrative_procedure = next(
            (
                item
                for item in context["procedures"]["procedures"]
                if item["workflow_id"] == workflow_id
            ),
            None,
        )

        return {
            "pack": {
                "id": self.manifest["pack_id"],
                "version": self.manifest["version"],
                "status": self.manifest["status"],
            },
            "workflow": workflow,
            "intent": intent,
            "domains": domains,
            "slot_policy": slot_policy,
            "ambiguity_policy": context["ambiguities"],
            "easy_korean": context["easy_korean"],
            "templates": templates,
            "guardrails": guardrails,
            "quality_policy": context["quality_policy"],
            "data_protection": context["data_protection"],
            "checklist": checklist,
            "official_sources": sources,
            "administrative_procedure": administrative_procedure,
        }
