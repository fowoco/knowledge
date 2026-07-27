from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .engine import RequestEvaluator
from .ingestion import OfficialDataPipeline
from .intent_consensus import (
    ConsensusNotFinalError,
    apply_consensus,
    build_consensus_manifest,
    build_consensus_rows,
    write_consensus_csv,
    write_manifest,
)
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

    consensus_parser = subparsers.add_parser(
        "build-intent-consensus",
        help="Compare Reviewer A/B results and build the Intent consensus pack",
    )
    consensus_parser.add_argument(
        "--assume-b-agrees",
        action="store_true",
        help="Build a clearly marked provisional proposal from Reviewer A results",
    )

    apply_parser = subparsers.add_parser(
        "apply-intent-consensus",
        help="Apply only a fully agreed Intent consensus to a separate JSONL output",
    )
    apply_parser.add_argument("--consensus", type=Path)
    apply_parser.add_argument("--manifest", type=Path)
    apply_parser.add_argument("--source", type=Path)
    apply_parser.add_argument("--output", type=Path, required=True)
    apply_parser.add_argument("--allow-exclude", action="store_true")
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

    if args.command == "build-intent-consensus":
        reviewer_a_path = repository.root / "data/review/intent_boundary_review_a.csv"
        reviewer_b_path = repository.root / "data/review/intent_boundary_review_b.csv"
        output_path = repository.root / "data/review/intent_boundary_review_consensus.csv"
        manifest_path = repository.root / "data/review/intent_boundary_consensus_manifest.yaml"
        rows = build_consensus_rows(
            reviewer_a_path,
            reviewer_b_path,
            assume_b_agrees=args.assume_b_agrees,
        )
        write_consensus_csv(output_path, rows)
        manifest = build_consensus_manifest(
            root=repository.root,
            reviewer_a_path=reviewer_a_path,
            reviewer_b_path=reviewer_b_path,
            output_path=output_path,
            rows=rows,
            assume_b_agrees=args.assume_b_agrees,
        )
        write_manifest(manifest_path, manifest)
        print(
            f"BUILT\t{manifest['status']}\t{len(rows)}\t"
            f"source_apply_allowed={manifest['source_application']['allowed']}"
        )
        return 0

    if args.command == "apply-intent-consensus":
        consensus_path = args.consensus or (
            repository.root / "data/review/intent_boundary_review_consensus.csv"
        )
        if not consensus_path.is_absolute():
            consensus_path = repository.root / consensus_path
        manifest_path = args.manifest or (
            repository.root / "data/review/intent_boundary_consensus_manifest.yaml"
        )
        if not manifest_path.is_absolute():
            manifest_path = repository.root / manifest_path
        source_path = args.source or (repository.root / "data/intent/hr_intent_dataset.jsonl")
        if not source_path.is_absolute():
            source_path = repository.root / source_path
        output_path = args.output
        if not output_path.is_absolute():
            output_path = repository.root / output_path
        try:
            changed_count, record_count = apply_consensus(
                consensus_path=consensus_path,
                source_path=source_path,
                output_path=output_path,
                manifest_path=manifest_path,
                allow_exclude=args.allow_exclude,
            )
        except ConsensusNotFinalError as error:
            print(f"BLOCKED: {error}")
            return 1
        print(f"APPLIED\tchanged={changed_count}\trecords={record_count}\t{output_path}")
        return 0

    return 2
