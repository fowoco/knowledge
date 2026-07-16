from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .engine import RequestEvaluator
from .repository import KnowledgeRepository
from .validation import KnowledgeValidator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FOWOCO knowledge tools")
    parser.add_argument("--root", help="fowoco-knowledge project root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="Validate schemas and cross references")
    subparsers.add_parser("list-workflows", help="List supported workflows")

    compile_parser = subparsers.add_parser(
        "compile-context", help="Compile the Agent context for one workflow"
    )
    compile_parser.add_argument("workflow_id")

    check_parser = subparsers.add_parser(
        "check-request", help="Validate classified request slots and ambiguity"
    )
    check_parser.add_argument("request_file", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = KnowledgeRepository(args.root)

    if args.command == "validate":
        errors = KnowledgeValidator(repository).validate_all()
        if errors:
            print(f"INVALID: {len(errors)} error(s)")
            for error in errors:
                print(f"- {error}")
            return 1
        print(f"VALID: FOWOCO Knowledge {repository.manifest['version']}")
        return 0

    if args.command == "list-workflows":
        for workflow in repository.list_workflows():
            print(
                f"{workflow['id']}\t{workflow['intent']}\t"
                f"{workflow['sensitivity']}\t{workflow['name']}"
            )
        return 0

    if args.command == "compile-context":
        print(
            json.dumps(repository.compile_context(args.workflow_id), ensure_ascii=False, indent=2)
        )
        return 0

    if args.command == "check-request":
        request = json.loads(args.request_file.read_text(encoding="utf-8"))
        result = RequestEvaluator(repository).evaluate(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    return 2
