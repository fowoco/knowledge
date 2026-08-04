from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest
import yaml

from fowoco_knowledge.ax_intent import (
    AXClassification,
    AXConfig,
    AXIntentClient,
    AXIntentError,
    classify_with_local_transformers,
    load_ax_config,
    load_ax_prompt,
    parse_ax_json_content,
    reject_sensitive_input,
    run_ax_evaluation,
)
from fowoco_knowledge.cli import main
from fowoco_knowledge.repository import KnowledgeRepository

ROOT = Path(__file__).resolve().parents[1]


def test_ax_json_parser_handles_direct_and_wrapped_objects() -> None:
    expected = {
        "intents": [
            {
                "intent": "DOCUMENT_REQUEST",
                "evidence": "여권 사본 받아줘",
            }
        ]
    }
    raw_json = json.dumps(expected, ensure_ascii=False)

    assert parse_ax_json_content(raw_json) == (expected, "direct_json")
    assert parse_ax_json_content(f"```json\n{raw_json}\n```") == (
        expected,
        "markdown_fence",
    )
    assert parse_ax_json_content(f"분류 결과입니다.\n{raw_json}") == (
        expected,
        "embedded_json_object",
    )
    with pytest.raises(AXIntentError, match="유효한 JSON"):
        parse_ax_json_content("JSON이 아닌 응답")


def test_ax_client_uses_openai_compatible_contract_without_exposing_key() -> None:
    captured: dict[str, object] = {}

    def fake_transport(
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data or b"{}")
        captured["timeout"] = timeout_seconds
        return {
            "id": "chatcmpl-test",
            "model": "ax4",
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"intents":[{"intent":"DOCUMENT_REQUEST",'
                            '"evidence":"여권 사본 받아줘"}]}'
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
        }

    config = AXConfig(
        base_url="https://example.test/v1",
        model="ax4",
        api_key="unit-test-secret",
        timeout_seconds=12,
    )
    client = AXIntentClient(config, transport=fake_transport)
    schema = KnowledgeRepository(ROOT).load_json("schemas/intent-model-output.schema.json")
    result = client.classify(
        hr_input="여권 사본 받아줘",
        system_prompt="JSON만 출력",
        output_schema=schema,
    )

    assert isinstance(result, AXClassification)
    assert result.issues == ()
    assert result.parsed_output["intents"][0]["intent"] == "DOCUMENT_REQUEST"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer unit-test-secret"
    assert captured["timeout"] == 12
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "ax4"
    assert payload["temperature"] == 0.0
    assert "unit-test-secret" not in json.dumps(result.to_dict())
    assert "unit-test-secret" not in json.dumps(payload)


def test_ax_config_requires_environment_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AX_API_KEY", raising=False)
    monkeypatch.delenv("ADOTX_API_KEY", raising=False)
    with pytest.raises(AXIntentError, match="환경변수"):
        load_ax_config()

    monkeypatch.setenv("AX_API_KEY", "test-only")
    config = load_ax_config(
        base_url="http://localhost:8000/v1",
        model="skt/A.X-4.0-Light",
    )
    assert config.model == "skt/A.X-4.0-Light"
    assert config.chat_completions_url.endswith("/chat/completions")
    assert "test-only" not in repr(config)


def test_ax_config_requires_explicit_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AX_API_KEY", "test-only")
    monkeypatch.delenv("AX_BASE_URL", raising=False)
    with pytest.raises(AXIntentError, match="guest endpoint는 현재 종료"):
        load_ax_config()


def test_ax_client_surfaces_provider_service_message() -> None:
    def fake_transport(
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> dict[str, object]:
        del request, timeout_seconds
        return {
            "message": {
                "ko": "Guest 용 API Endpoint 서비스는 종료되었습니다.",
                "en": "The guest API endpoint service is no longer available.",
            }
        }

    client = AXIntentClient(
        AXConfig(
            base_url="https://example.test/v1",
            model="ax4",
            api_key="test-only",
        ),
        transport=fake_transport,
    )
    schema = KnowledgeRepository(ROOT).load_json("schemas/intent-model-output.schema.json")
    with pytest.raises(AXIntentError, match="서비스 메시지.*종료"):
        client.classify(
            hr_input="WRK-001 계약 갱신 준비",
            system_prompt="JSON만 출력",
            output_schema=schema,
        )


def test_ax_input_privacy_guard_rejects_identifier_patterns() -> None:
    reject_sensitive_input("WRK-001 계약 만료 확인")
    reject_sensitive_input("2026-07-27까지 제출")
    with pytest.raises(AXIntentError, match="mobile_phone_number"):
        reject_sensitive_input("연락처는 010-1234-5678입니다")
    with pytest.raises(AXIntentError, match="passport_number"):
        reject_sensitive_input("여권번호 M12345678 확인")


def test_ax_evaluation_writes_local_report_without_api_key(
    tmp_path: Path,
) -> None:
    source_cases = {
        case["hr_input"]: case
        for case in (
            json.loads(line)
            for line in (ROOT / "data/intent/hr_intent_dataset.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        )
    }

    def fake_transport(
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> dict[str, object]:
        del timeout_seconds
        payload = json.loads(request.data or b"{}")
        user_content = payload["messages"][1]["content"]
        hr_input = json.loads(user_content.splitlines()[-1])["hr_input"]
        case = source_cases[hr_input]
        return {
            "id": f"chatcmpl-{case['id']}",
            "model": "ax4",
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"intents": case["intents"]},
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {"total_tokens": 20},
        }

    client = AXIntentClient(
        AXConfig(
            base_url="https://example.test/v1",
            model="ax4",
            api_key="must-not-be-written",
        ),
        transport=fake_transport,
    )
    output_dir = tmp_path / "ax-smoke"
    report = run_ax_evaluation(
        project_root=ROOT,
        client=client,
        limit=3,
        delay_seconds=0,
        output_dir=output_dir,
    )

    assert report["evaluation"]["record_count"] == 3
    assert report["evaluation"]["failure_count"] == 0
    assert report["evaluation"]["metrics"]["intent_exact_match"] == 1.0
    assert report["provider"]["api_key_stored"] is False
    report_text = (output_dir / "report.yaml").read_text(encoding="utf-8")
    predictions_text = (output_dir / "predictions.jsonl").read_text(encoding="utf-8")
    assert "must-not-be-written" not in report_text
    assert "must-not-be-written" not in predictions_text
    assert yaml.safe_load(report_text)["status"] == "provisional_pre_consensus"


def test_ax_cli_requires_explicit_external_confirmation() -> None:
    assert (
        main(
            [
                "--root",
                str(ROOT),
                "test-intent-ax",
                "WRK-001 여권 사본 받아줘",
            ]
        )
        == 2
    )


def test_ax_local_cli_requires_explicit_model_download_confirmation() -> None:
    assert (
        main(
            [
                "--root",
                str(ROOT),
                "test-intent-ax-local",
                "WRK-001 여권 사본 받아줘",
            ]
        )
        == 2
    )


def test_ax_local_missing_dependencies_returns_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def block_import(name: str, *args: object, **kwargs: object) -> object:
        del args, kwargs
        if name in {"torch", "transformers"}:
            raise ImportError(name)
        return original_import(name)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", block_import)
    schema = KnowledgeRepository(ROOT).load_json("schemas/intent-model-output.schema.json")
    with pytest.raises(AXIntentError, match="ax-local"):
        classify_with_local_transformers(
            hr_input="WRK-001 여권 사본 받아줘",
            system_prompt="JSON만 출력",
            output_schema=schema,
        )


def test_versioned_ax_prompt_is_inside_project() -> None:
    path, prompt = load_ax_prompt(ROOT)
    assert path.is_relative_to(ROOT)
    assert "DOCUMENT_REQUEST" in prompt
    assert "OUT_OF_SCOPE" in prompt
    assert "JSON 객체 하나만 출력" in prompt
