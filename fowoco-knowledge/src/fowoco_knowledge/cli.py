from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .ax_intent import (
    DEFAULT_AX_LOCAL_MODEL,
    AXIntentClient,
    AXIntentError,
    classify_with_local_transformers,
    load_ax_config,
    load_ax_prompt,
    parse_case_ids,
    run_ax_evaluation,
)
from .engine import RequestEvaluator
from .ingestion import OfficialDataPipeline
from .intent_split import (
    DEFAULT_SEED,
    DEFAULT_VALIDATION_RATIO,
    build_and_write_intent_split,
)
from .provisional_baseline import run_provisional_baseline
from .repository import KnowledgeRepository
from .validation import KnowledgeValidator


def add_ax_connection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        help="OpenAI-compatible base URL (or AX_BASE_URL)",
    )
    parser.add_argument(
        "--model",
        help="Provider model name (or AX_MODEL)",
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument(
        "--prompt",
        type=Path,
        help="Prompt file inside the knowledge project",
    )
    parser.add_argument(
        "--confirm-external",
        action="store_true",
        help="Confirm that dummy input may be sent to the configured external API",
    )


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

    split_parser = subparsers.add_parser(
        "build-intent-splits",
        help="Build provisional grouped Train/Validation ID manifests",
    )
    split_parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory inside the knowledge project",
    )
    split_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    split_parser.add_argument(
        "--validation-ratio",
        type=float,
        default=DEFAULT_VALIDATION_RATIO,
    )

    baseline_parser = subparsers.add_parser(
        "run-intent-provisional-baseline",
        help="Run a dependency-free provisional Intent baseline",
    )
    baseline_parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory inside the knowledge project",
    )

    ax_test_parser = subparsers.add_parser(
        "test-intent-ax",
        help="Classify one dummy HR utterance with an A.X-compatible endpoint",
    )
    ax_test_parser.add_argument("hr_input")
    add_ax_connection_arguments(ax_test_parser)

    ax_local_parser = subparsers.add_parser(
        "test-intent-ax-local",
        help="Classify one dummy HR utterance with local official A.X-4.0-Light",
    )
    ax_local_parser.add_argument("hr_input")
    ax_local_parser.add_argument(
        "--model-id",
        default=DEFAULT_AX_LOCAL_MODEL,
        help=f"Hugging Face model ID (default: {DEFAULT_AX_LOCAL_MODEL})",
    )
    ax_local_parser.add_argument(
        "--device",
        default="auto",
        choices=("auto", "cuda", "mps", "cpu"),
    )
    ax_local_parser.add_argument("--max-new-tokens", type=int, default=512)
    ax_local_parser.add_argument(
        "--prompt",
        type=Path,
        help="Prompt file inside the knowledge project",
    )
    ax_local_parser.add_argument(
        "--confirm-model-download",
        action="store_true",
        help="Confirm that the large model may be downloaded and loaded locally",
    )

    ax_evaluation_parser = subparsers.add_parser(
        "run-intent-ax-evaluation",
        help="Run a limited or explicit provisional A.X evaluation",
    )
    ax_evaluation_parser.add_argument(
        "--ids",
        help="Comma-separated source record IDs",
    )
    ax_evaluation_parser.add_argument("--limit", type=int)
    ax_evaluation_parser.add_argument(
        "--all-validation",
        action="store_true",
        help="Explicitly run all 268 provisional Validation records",
    )
    ax_evaluation_parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.5,
    )
    ax_evaluation_parser.add_argument(
        "--output-dir",
        type=Path,
        help="Local output directory (default: ignored local-data path)",
    )
    add_ax_connection_arguments(ax_evaluation_parser)
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

    if args.command == "build-intent-splits":
        manifest = build_and_write_intent_split(
            repository.root,
            output_dir=args.output_dir,
            seed=args.seed,
            validation_ratio=args.validation_ratio,
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-intent-provisional-baseline":
        report = run_provisional_baseline(
            repository.root,
            output_dir=args.output_dir,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.command == "test-intent-ax-local":
        if not args.confirm_model_download:
            print(
                "BLOCKED: 대용량 A.X 모델 다운로드·로딩을 확인하려면 "
                "--confirm-model-download를 지정하세요."
            )
            return 2
        try:
            _, system_prompt = load_ax_prompt(repository.root, args.prompt)
            output_schema = repository.load_json("schemas/intent-model-output.schema.json")
            classification = classify_with_local_transformers(
                hr_input=args.hr_input,
                system_prompt=system_prompt,
                output_schema=output_schema,
                model_id=args.model_id,
                device=args.device,
                max_new_tokens=args.max_new_tokens,
            )
            result = {
                "hr_input": args.hr_input,
                **classification.to_dict(),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if classification.issues else 0
        except AXIntentError as error:
            print(f"ERROR: {error}")
            return 1

    if args.command in {"test-intent-ax", "run-intent-ax-evaluation"}:
        if not args.confirm_external:
            print("BLOCKED: 외부 API 전송을 확인하려면 --confirm-external을 지정하세요.")
            return 2
        try:
            config = load_ax_config(
                base_url=args.base_url,
                model=args.model,
                timeout_seconds=args.timeout,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
            client = AXIntentClient(config)
            if args.command == "test-intent-ax":
                _, system_prompt = load_ax_prompt(
                    repository.root,
                    args.prompt,
                )
                output_schema = repository.load_json("schemas/intent-model-output.schema.json")
                classification = client.classify(
                    hr_input=args.hr_input,
                    system_prompt=system_prompt,
                    output_schema=output_schema,
                )
                result = {
                    "hr_input": args.hr_input,
                    **classification.to_dict(),
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 1 if classification.issues else 0

            report = run_ax_evaluation(
                project_root=repository.root,
                client=client,
                prompt_path=args.prompt,
                case_ids=parse_case_ids(args.ids),
                limit=args.limit,
                all_validation=args.all_validation,
                delay_seconds=args.delay_seconds,
                output_dir=args.output_dir,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        except AXIntentError as error:
            print(f"ERROR: {error}")
            return 1

    return 2
