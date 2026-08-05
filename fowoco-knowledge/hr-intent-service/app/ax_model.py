"""A.X-4.0-Light QLoRA 파인튜닝 모델 로드 및 추론."""

import json
import re

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

SYSTEM_PROMPT = """당신은 HR 업무 요청 문장(hr_input)을 분석하여 의도(Intent)를 분류하는 전문 AI 에이전트입니다.
Intent 모델의 책임은 Intent + evidence 추출까지입니다. Workflow 선택, Slot 수집, 외부기관 제출, 법적 판단, 업무 실행 여부는 이 모델의 책임이 아닙니다.

### 1. Intent 정의 (7개)
1. WORK_INSTRUCTION: 작업 지시, 근무 일정 변경, 현장 행동 안내
2. DOCUMENT_REQUEST: 여권/등록증/계약서/증명서 등 서류를 받거나 제출을 요청·추적하는 행위 자체
3. PAYROLL_EXPLANATION: 급여, 수당, 공제 내역, 출퇴근/근태 관련 설명·문의 (급여계좌 등록/변경은 제외 → WORKER_ONBOARDING)
4. WORKER_ONBOARDING: 신규 입사자 등록, 보험 최초 가입, 초기 프로필·급여계좌 등록 (서류가 이미 있는 상태에서의 처리)
5. EMPLOYMENT_CHANGE: 휴가, 퇴사, 무단결근/연락두절, 사업장 변경 등 재직 상태 변동 확인·신고
6. EXPIRY_RENEWAL: 근로계약, 체류기간, 고용허가기간 등 만료 임박·연장·갱신 절차
7. OUT_OF_SCOPE: 위 6개 외 HR 범주 밖 요청, 또는 새 실행 요청 없이 결과만 보고하는 문장. 다른 Intent와 병행 불가

### 2. 핵심 판별 규칙
- 규칙 A: 최종 목적이 아니라 발화문에서 지금 당장 실행을 요구하는 행위로 판단합니다.
- 규칙 B: "받아서/제출받아/요청해/첨부해줘" 등 서류 확보 표현이 명시적으로 있을 때만 DOCUMENT_REQUEST를 부착합니다.
- 규칙 C: 여러 Intent가 있으면 발화문 등장 순서대로 배열합니다. OUT_OF_SCOPE는 단독으로만 존재합니다.
- 규칙 D: evidence는 원문 문자를 그대로(exact substring) 추출합니다. OUT_OF_SCOPE는 evidence: null입니다.

### 3. 경계 규칙
- 완료/상태 보고 문장은 OUT_OF_SCOPE, 요청형이면 원래 Intent 유지.
- 휴가는 명시적 액션이면 EMPLOYMENT_CHANGE, 배경절이면 제외.
- 급여계좌 등록/변경은 WORKER_ONBOARDING, 순수 급여 설명/문의는 PAYROLL_EXPLANATION.

### 4. 출력 형식
다른 설명, 마크다운, 코드블록 없이 오직 아래 JSON 형식 텍스트만 출력합니다:
{"intents": [{"intent": "INTENT_CODE", "evidence": "원문에서 추출한 정확한 부분 문자열 또는 null"}]}

이제 아래 입력 문장을 위 규칙에 따라 JSON 형식으로만 분류하십시오."""


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class AxIntentModel:
    def __init__(
        self, base_model_name: str, adapter_path: str, device: str, max_new_tokens: int = 96, hf_token : str | None = None,
    ):
        self.max_new_tokens = max_new_tokens
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            quantization_config=bnb_config,
            torch_dtype=torch.float16,
            device_map={"": 0} if device != "cpu" else "cpu",
            token = hf_token,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(base_model_name, token=hf_token)
        self.model = PeftModel.from_pretrained(base_model, adapter_path, token=hf_token)
        self.model.eval()

    def predict(self, hr_input: str) -> list[dict]:
        """실패 시 예외를 던진다 — 호출부(pipeline)에서 graceful degradation 처리."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": hr_input},
        ]
        inputs = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device)

        with torch.no_grad():
            output = self.model.generate(
                **inputs, max_new_tokens=self.max_new_tokens, do_sample=False
            )

        raw = self.tokenizer.decode(
            output[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True
        )
        parsed = _extract_json(raw)
        if parsed is None:
            raise ValueError(f"A.X output could not be parsed as JSON: {raw!r}")
        return parsed.get("intents", [])