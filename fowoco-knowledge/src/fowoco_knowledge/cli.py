from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .dataset import DatasetManager, ReviewComparator, format_report, format_review_comparison
from .engine import RequestEvaluator
from .ingestion import OfficialDataPipeline
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

    sync_parser = subparsers.add_parser(
        "sync-official-data",
        help="Download pinned public data and rebuild normalized snapshots",
    )
    sync_parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Raw source cache (default: repository local-data/official)",
    )
    sync_parser.add_argument(
        "--output-dir",
        type=Path,
        help="Normalized output directory (default: data/processed)",
    )
    sync_parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not download missing raw files",
    )

    document_parser = subparsers.add_parser(
        "list-required-documents",
        help="List normalized document requirements for one application",
    )
    document_parser.add_argument("application_name")
    document_parser.add_argument("--json", action="store_true")

    industry_parser = subparsers.add_parser(
        "search-industries",
        help="Search normalized manufacturing business descriptions",
    )
    industry_parser.add_argument("query")
    industry_parser.add_argument("--limit", type=int, default=20)

    report_parser = subparsers.add_parser(
        "data-report",
        help="Report label distribution, leakage, privacy, and readiness gates",
    )
    report_parser.add_argument("--json", action="store_true")

    review_parser = subparsers.add_parser(
        "build-review-queue",
        help="Create a blind Seed review queue without proposed labels",
    )
    review_parser.add_argument("reviewer_code")
    review_parser.add_argument("output", type=Path)

    compare_parser = subparsers.add_parser(
        "compare-reviews",
        help="Compare two independent reviews and create an adjudication queue",
    )
    compare_parser.add_argument("reviewer_a", type=Path)
    compare_parser.add_argument("reviewer_b", type=Path)
    compare_parser.add_argument("--output", type=Path)
    compare_parser.add_argument("--json", action="store_true")
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

    if args.command == "sync-official-data":
        cache_dir = args.cache_dir or repository.root.parent / "local-data/official"
        output_dir = args.output_dir or repository.root / "data/processed"
        results = OfficialDataPipeline(repository.root).sync(
            cache_dir,
            output_dir,
            download_missing=not args.offline,
        )
        for result in results:
            print(
                f"SYNCED\t{result.source_id}\t{result.row_count}\t{result.output}\t{result.sha256}"
            )
        return 0

    if args.command == "list-required-documents":
        rows = repository.list_required_documents(args.application_name)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                print(
                    f"{row['requirement_marker']}\t{row['document_name']}\t"
                    f"sample={row['sample_form_available']}"
                )
        return 0

    if args.command == "search-industries":
        for row in repository.search_manufacturing_industries(args.query, args.limit):
            print(f"{row['industry_id']}\t{row['middle_category']}\t{row['business_content_ko']}")
        return 0

    if args.command == "data-report":
        report = DatasetManager(repository).build_report()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_report(report))
        return 0

    if args.command == "build-review-queue":
        output = args.output.expanduser().resolve()
        count = DatasetManager(repository).write_blind_review_queue(
            args.reviewer_code,
            output,
        )
        print(f"CREATED\t{output}\trows={count}\treviewer={args.reviewer_code}")
        return 0

    if args.command == "compare-reviews":
        output = args.output.expanduser().resolve() if args.output else None
        report = ReviewComparator(repository).compare(
            args.reviewer_a.expanduser().resolve(),
            args.reviewer_b.expanduser().resolve(),
            output,
        )
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_review_comparison(report))
        return 0

    return 2
