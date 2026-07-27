from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .ingestion import file_sha256
from .intent_model import validate_intent_model_output
from .intent_split import load_intent_cases, read_split_ids
from .provisional_baseline import (
    compact_json,
    evaluate_prediction_outputs,
)

DEFAULT_AX_MODEL = "ax4"
DEFAULT_AX_LOCAL_MODEL = "skt/A.X-4.0-Light"
DEFAULT_AX_PROMPT_PATH = Path("experiments/intent/prompts/ax-zero-shot-v1.md")
DEFAULT_AX_OUTPUT_DIR = Path("local-data/experiments/intent/ax-zero-shot-v1")
SENSITIVE_INPUT_PATTERNS = {
    "resident_or_alien_registration_number": re.compile(r"(?<!\d)\d{6}-?[1-8]\d{6}(?!\d)"),
    "mobile_phone_number": re.compile(r"(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)"),
    "passport_number": re.compile(r"(?<![A-Z0-9])[A-Z]{1,2}\d{7,8}(?![A-Z0-9])"),
    "bank_account_number": re.compile(r"(?<!\d)\d{3,6}-\d{2,6}-\d{3,8}(?!\d)"),
}

Transport = Callable[[urllib.request.Request, float], dict[str, Any]]


class AXIntentError(RuntimeError):
    """Raised when an A.X request or response cannot be handled safely."""


@dataclass(frozen=True)
class AXConfig:
    base_url: str
    model: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 90.0
    temperature: float = 0.0
    max_tokens: int = 512

    @property
    def chat_completions_url(self) -> str:
        base_url = self.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"


@dataclass(frozen=True)
class AXClassification:
    requested_model: str
    returned_model: str | None
    response_id: str | None
    raw_content: str
    parsed_output: Any
    parse_strategy: str | None
    issues: tuple[dict[str, str], ...]
    usage: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_model": self.requested_model,
            "returned_model": self.returned_model,
            "response_id": self.response_id,
            "raw_content": self.raw_content,
            "parsed_output": self.parsed_output,
            "parse_strategy": self.parse_strategy,
            "issues": list(self.issues),
            "usage": self.usage,
        }


def load_ax_config(
    *,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float = 90.0,
    temperature: float = 0.0,
    max_tokens: int = 512,
) -> AXConfig:
    api_key = os.getenv("AX_API_KEY") or os.getenv("ADOTX_API_KEY")
    if not api_key:
        raise AXIntentError("AX_API_KEY 또는 ADOTX_API_KEY 환경변수를 설정해야 합니다.")
    resolved_base_url = base_url or os.getenv("AX_BASE_URL")
    if not resolved_base_url:
        raise AXIntentError(
            "AX_BASE_URL 또는 --base-url을 설정해야 합니다. "
            "공식 문서의 guest endpoint는 현재 종료 상태입니다."
        )
    return AXConfig(
        base_url=resolved_base_url,
        model=model or os.getenv("AX_MODEL") or DEFAULT_AX_MODEL,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def reject_sensitive_input(hr_input: str) -> None:
    matches = [
        name for name, pattern in SENSITIVE_INPUT_PATTERNS.items() if pattern.search(hr_input)
    ]
    if matches:
        raise AXIntentError("A.X 테스트에 사용할 수 없는 개인정보 패턴: " + ", ".join(matches))


def parse_ax_json_content(content: str) -> tuple[Any, str]:
    stripped = content.strip()
    candidates: list[tuple[str, str]] = [(stripped, "direct_json")]
    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        candidates.insert(0, (fenced.group(1).strip(), "markdown_fence"))
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(
            (
                stripped[first_brace : last_brace + 1],
                "embedded_json_object",
            )
        )

    attempted: set[str] = set()
    for candidate, strategy in candidates:
        if candidate in attempted:
            continue
        attempted.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            raise AXIntentError("A.X JSON 응답의 최상위 값이 객체가 아닙니다.")
        return parsed, strategy
    raise AXIntentError("A.X 응답에서 유효한 JSON 객체를 찾지 못했습니다.")


def _default_transport(
    request: urllib.request.Request,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise AXIntentError(f"A.X API HTTP {error.code}: {body[:500]}") from error
    except urllib.error.URLError as error:
        raise AXIntentError(f"A.X API 연결 실패: {error.reason}") from error
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise AXIntentError("A.X API가 JSON이 아닌 응답을 반환했습니다.") from error
    if not isinstance(payload, dict):
        raise AXIntentError("A.X API 응답의 최상위 값이 객체가 아닙니다.")
    return payload


class AXIntentClient:
    def __init__(
        self,
        config: AXConfig,
        *,
        transport: Transport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or _default_transport

    def classify(
        self,
        *,
        hr_input: str,
        system_prompt: str,
        output_schema: dict[str, Any],
    ) -> AXClassification:
        reject_sensitive_input(hr_input)
        user_content = "다음 JSON의 hr_input을 분류하십시오.\n" + compact_json(
            {"hr_input": hr_input}
        )
        request_payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        request = urllib.request.Request(
            self.config.chat_completions_url,
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        response = self.transport(request, self.config.timeout_seconds)
        if "choices" not in response and isinstance(
            response.get("message"),
            dict | str,
        ):
            service_message = response["message"]
            if isinstance(service_message, dict):
                rendered_message = " / ".join(
                    str(service_message[key]) for key in ("ko", "en") if service_message.get(key)
                )
            else:
                rendered_message = service_message
            raise AXIntentError(f"A.X API 서비스 메시지: {rendered_message}")
        try:
            message = response["choices"][0]["message"]
            raw_content = message["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise AXIntentError(
                "A.X API 응답에서 choices[0].message.content를 찾지 못했습니다."
            ) from error
        if not isinstance(raw_content, str):
            raise AXIntentError("A.X message.content가 문자열이 아닙니다.")

        parsed_output: Any = None
        parse_strategy: str | None = None
        issues: list[dict[str, str]] = []
        try:
            parsed_output, parse_strategy = parse_ax_json_content(raw_content)
        except AXIntentError as error:
            issues.append({"code": "INVALID_JSON", "message": str(error)})
        if parsed_output is not None:
            issues.extend(
                {
                    "code": issue.code,
                    "message": issue.message,
                }
                for issue in validate_intent_model_output(
                    hr_input,
                    parsed_output,
                    output_schema,
                )
            )
        usage = response.get("usage")
        return AXClassification(
            requested_model=self.config.model,
            returned_model=(
                response.get("model") if isinstance(response.get("model"), str) else None
            ),
            response_id=(response.get("id") if isinstance(response.get("id"), str) else None),
            raw_content=raw_content,
            parsed_output=parsed_output,
            parse_strategy=parse_strategy,
            issues=tuple(issues),
            usage=usage if isinstance(usage, dict) else {},
        )


def _resolve_local_device(torch_module: Any, requested_device: str) -> str:
    if requested_device != "auto":
        if requested_device not in {"cuda", "mps", "cpu"}:
            raise AXIntentError("--device는 auto, cuda, mps, cpu 중 하나여야 합니다.")
        return requested_device
    if torch_module.cuda.is_available():
        return "cuda"
    mps = getattr(torch_module.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def classify_with_local_transformers(
    *,
    hr_input: str,
    system_prompt: str,
    output_schema: dict[str, Any],
    model_id: str = DEFAULT_AX_LOCAL_MODEL,
    device: str = "auto",
    max_new_tokens: int = 512,
) -> AXClassification:
    """Run the official A.X model locally after an explicit CLI confirmation."""
    reject_sensitive_input(hr_input)
    if max_new_tokens < 1:
        raise AXIntentError("--max-new-tokens는 1 이상이어야 합니다.")
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as error:
        raise AXIntentError(
            '로컬 A.X 실행 의존성이 없습니다. pip install -e ".[ax-local]"을 먼저 실행하세요.'
        ) from error

    resolved_device = _resolve_local_device(torch, device)
    if resolved_device == "cuda" and not torch.cuda.is_available():
        raise AXIntentError("CUDA를 사용할 수 없습니다.")
    mps = getattr(torch.backends, "mps", None)
    if resolved_device == "mps" and (mps is None or not mps.is_available()):
        raise AXIntentError("MPS를 사용할 수 없습니다.")

    if resolved_device == "cuda":
        dtype = torch.bfloat16
    elif resolved_device == "mps":
        dtype = torch.float16
    else:
        dtype = torch.float32

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
            device_map={"": resolved_device},
        )
        model.eval()
    except Exception as error:
        raise AXIntentError(f"로컬 A.X 모델을 불러오지 못했습니다: {error}") from error

    user_content = "다음 JSON의 hr_input을 분류하십시오.\n" + compact_json({"hr_input": hr_input})
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    try:
        input_ids = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
        ).to(resolved_device)
        with torch.inference_mode():
            generated_ids = model.generate(
                input_ids,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        completion_ids = generated_ids[0, input_ids.shape[-1] :]
        raw_content = tokenizer.decode(
            completion_ids,
            skip_special_tokens=True,
        ).strip()
    except Exception as error:
        raise AXIntentError(f"로컬 A.X 추론에 실패했습니다: {error}") from error

    parsed_output: Any = None
    parse_strategy: str | None = None
    issues: list[dict[str, str]] = []
    try:
        parsed_output, parse_strategy = parse_ax_json_content(raw_content)
    except AXIntentError as error:
        issues.append({"code": "INVALID_JSON", "message": str(error)})
    if parsed_output is not None:
        issues.extend(
            {
                "code": issue.code,
                "message": issue.message,
            }
            for issue in validate_intent_model_output(
                hr_input,
                parsed_output,
                output_schema,
            )
        )

    return AXClassification(
        requested_model=model_id,
        returned_model=model_id,
        response_id="local-transformers",
        raw_content=raw_content,
        parsed_output=parsed_output,
        parse_strategy=parse_strategy,
        issues=tuple(issues),
        usage={
            "prompt_tokens": int(input_ids.shape[-1]),
            "completion_tokens": int(completion_ids.shape[-1]),
            "total_tokens": int(input_ids.shape[-1] + completion_ids.shape[-1]),
        },
    )


def parse_case_ids(raw: str | None) -> tuple[int, ...] | None:
    if raw is None:
        return None
    try:
        ids = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as error:
        raise AXIntentError("--ids는 쉼표로 구분한 정수여야 합니다.") from error
    if not ids:
        raise AXIntentError("--ids에 하나 이상의 ID가 필요합니다.")
    if len(ids) != len(set(ids)):
        raise AXIntentError("--ids에 중복 ID가 있습니다.")
    return ids


def load_ax_prompt(
    project_root: Path,
    prompt_path: Path | None = None,
) -> tuple[Path, str]:
    resolved = (
        prompt_path.resolve()
        if prompt_path is not None and prompt_path.is_absolute()
        else project_root.resolve() / (prompt_path or DEFAULT_AX_PROMPT_PATH)
    )
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError as error:
        raise AXIntentError("A.X prompt 파일은 knowledge 프로젝트 안에 있어야 합니다.") from error
    if not resolved.is_file():
        raise AXIntentError(f"A.X prompt 파일을 찾을 수 없습니다: {resolved}")
    return resolved, resolved.read_text(encoding="utf-8")


def _select_cases(
    *,
    source_cases: list[dict[str, Any]],
    validation_ids: tuple[int, ...],
    case_ids: tuple[int, ...] | None,
    limit: int | None,
    all_validation: bool,
) -> tuple[list[dict[str, Any]], str]:
    cases_by_id = {case["id"]: case for case in source_cases}
    if case_ids is not None:
        missing = [case_id for case_id in case_ids if case_id not in cases_by_id]
        if missing:
            raise AXIntentError(f"원본에 없는 ID: {missing[:5]}")
        return [cases_by_id[case_id] for case_id in case_ids], "selected_ids"
    if all_validation:
        if limit is not None:
            raise AXIntentError("--all-validation과 --limit은 함께 사용할 수 없습니다.")
        return [cases_by_id[case_id] for case_id in validation_ids], "validation_all"
    if limit is None or limit < 1:
        raise AXIntentError(
            "호출량 보호를 위해 --limit N, --ids 또는 --all-validation이 필요합니다."
        )
    return (
        [cases_by_id[case_id] for case_id in validation_ids[:limit]],
        "validation_limited",
    )


def _resolve_ax_output_dir(
    *,
    project_root: Path,
    output_dir: Path | None,
) -> Path:
    if output_dir is None:
        return project_root.parent / DEFAULT_AX_OUTPUT_DIR
    return (
        output_dir.resolve()
        if output_dir.is_absolute()
        else (project_root.parent / output_dir).resolve()
    )


def run_ax_evaluation(
    *,
    project_root: Path,
    client: AXIntentClient,
    prompt_path: Path | None = None,
    case_ids: tuple[int, ...] | None = None,
    limit: int | None = None,
    all_validation: bool = False,
    delay_seconds: float = 0.5,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    if delay_seconds < 0:
        raise AXIntentError("--delay-seconds는 0 이상이어야 합니다.")
    project_root = project_root.resolve()
    resolved_prompt_path, system_prompt = load_ax_prompt(
        project_root,
        prompt_path,
    )
    output_schema_path = project_root / "schemas/intent-model-output.schema.json"
    output_schema = json.loads(output_schema_path.read_text(encoding="utf-8"))

    intent_manifest = yaml.safe_load(
        (project_root / "data/intent/manifest.yaml").read_text(encoding="utf-8")
    )
    source_path = project_root / intent_manifest["path"]
    if file_sha256(source_path) != intent_manifest["sha256"]:
        raise AXIntentError("Intent 원본 checksum이 manifest와 다릅니다.")
    split_manifest_path = project_root / "data/intent/splits/provisional-v1/manifest.yaml"
    split_manifest = yaml.safe_load(split_manifest_path.read_text(encoding="utf-8"))
    validation_path = project_root / split_manifest["outputs"]["validation"]["path"]
    if file_sha256(validation_path) != split_manifest["outputs"]["validation"]["sha256"]:
        raise AXIntentError("Validation ID checksum이 manifest와 다릅니다.")

    source_cases = load_intent_cases(source_path)
    validation_ids = read_split_ids(validation_path)
    selected_cases, evaluation_scope = _select_cases(
        source_cases=source_cases,
        validation_ids=validation_ids,
        case_ids=case_ids,
        limit=limit,
        all_validation=all_validation,
    )

    outputs: list[Any] = []
    api_rows: list[dict[str, Any]] = []
    failure_count = 0
    returned_models: Counter[str] = Counter()
    total_usage: Counter[str] = Counter()
    for index, case in enumerate(selected_cases):
        if index and delay_seconds:
            time.sleep(delay_seconds)
        try:
            classification = client.classify(
                hr_input=case["hr_input"],
                system_prompt=system_prompt,
                output_schema=output_schema,
            )
        except AXIntentError as error:
            failure_count += 1
            outputs.append(None)
            api_rows.append(
                {
                    "id": case["id"],
                    "hr_input": case["hr_input"],
                    "expected": {"intents": case["intents"]},
                    "requested_model": client.config.model,
                    "returned_model": None,
                    "response_id": None,
                    "raw_content": "",
                    "parsed_output": None,
                    "parse_strategy": None,
                    "issues": [{"code": "API_ERROR", "message": str(error)}],
                    "usage": {},
                }
            )
            continue
        outputs.append(classification.parsed_output)
        if classification.parsed_output is None:
            failure_count += 1
        if classification.returned_model:
            returned_models[classification.returned_model] += 1
        for key, value in classification.usage.items():
            if isinstance(value, int):
                total_usage[key] += value
        api_rows.append(
            {
                "id": case["id"],
                "hr_input": case["hr_input"],
                "expected": {"intents": case["intents"]},
                **classification.to_dict(),
            }
        )

    metrics, evaluated_predictions = evaluate_prediction_outputs(
        cases=selected_cases,
        outputs=outputs,
        output_schema=output_schema,
    )
    evaluation_by_id = {row["id"]: row for row in evaluated_predictions}
    for row in api_rows:
        evaluated = evaluation_by_id[row["id"]]
        row["structural_issues"] = evaluated["structural_issues"]

    resolved_output_dir = _resolve_ax_output_dir(
        project_root=project_root,
        output_dir=output_dir,
    )
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = resolved_output_dir / "predictions.jsonl"
    report_path = resolved_output_dir / "report.yaml"
    with predictions_path.open("w", encoding="utf-8") as handle:
        for row in api_rows:
            handle.write(compact_json(row) + "\n")

    report = {
        "experiment_id": "FOWOCO-INTENT-AX-ZERO-SHOT-V1",
        "version": "0.1.0",
        "status": "provisional_pre_consensus",
        "provider": {
            "base_url": client.config.base_url,
            "requested_model": client.config.model,
            "returned_model_counts": dict(sorted(returned_models.items())),
            "api_key_stored": False,
        },
        "prompt": {
            "path": str(resolved_prompt_path.relative_to(project_root)),
            "sha256": file_sha256(resolved_prompt_path),
        },
        "source": {
            "path": intent_manifest["path"],
            "status": intent_manifest["status"],
            "sha256": intent_manifest["sha256"],
        },
        "evaluation": {
            "scope": evaluation_scope,
            "record_count": len(selected_cases),
            "case_ids": [case["id"] for case in selected_cases],
            "failure_count": failure_count,
            "delay_seconds": delay_seconds,
            "metrics": metrics,
        },
        "usage": dict(sorted(total_usage.items())),
        "artifacts": {
            "predictions": {
                "path": str(predictions_path),
                "record_count": len(api_rows),
                "sha256": file_sha256(predictions_path),
            }
        },
        "claims_not_allowed": [
            "최종 모델 성능",
            "Gold Test 성능",
            "A.X-4.0-Light 성능(반환 모델이 Light로 확인되지 않은 경우)",
            "A/B consensus가 반영된 라벨 성능",
        ],
        "limitations": [
            "수정 전 recheck_required 라벨을 기준으로 평가함",
            "외부 API 응답은 동일 요청에도 달라질 수 있음",
            "제한 실행 결과는 전체 Validation 성능이 아님",
            "실제 개인정보나 기업정보를 외부 API로 전송하지 않음",
        ],
    }
    report_path.write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return report
