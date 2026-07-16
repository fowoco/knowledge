# 안내문 출력 품질 검증

## 목적

FOWOCO는 번역문이 자연스러운지만 평가하지 않습니다. HR이 승인한 원문과 구조화 입력에서
`대상자·날짜·서류명·금액·행동`이 빠지거나 바뀌지 않았는지 먼저 확인합니다. 법령을 근거 없이
단정하거나 기관 제출을 완료했다고 주장하는 출력은 문장이 자연스러워도 차단합니다.

## 검증 위치

```text
HR 입력과 보완
  -> 승인된 Source Slots
  -> 안내문 생성
  -> 생성문에서 Candidate Slots 재추출
  -> 결정론적 핵심값 비교
  -> 위험 주장 검사
  -> 통과 시에만 HR 승인 화면
```

LLM이 자기 출력을 스스로 채점하게 두지 않습니다. 날짜·서류명·식별자처럼 비교 가능한 값은
코드가 판단하고, 법령 단정·외부 실행·급여 계산근거는 Guardrail 결과를 함께 검사합니다.

## 오류 기준

| 오류 | 의미 | 처리 |
| --- | --- | --- |
| `CORE_VALUE_OMITTED` | 원문 핵심값이 생성문에서 누락 | 차단 후 HR 검토 |
| `CORE_VALUE_CHANGED` | 날짜·서류명·대상자 등이 변경 | 차단 후 HR 검토 |
| `UNSUPPORTED_VALUE_ADDED` | 입력 근거 없는 핵심값 추가 | 차단 후 HR 검토 |
| `LEGAL_CLAIM_UNSUPPORTED` | 공식 근거 없이 가능·의무를 단정 | 차단 후 HR 검토 |
| `EXTERNAL_ACTION_CLAIMED` | 실제 수행하지 않은 제출·발송을 완료로 표현 | 차단 |
| `CALCULATION_WITHOUT_TRACE` | 계산근거 없이 급여 차액 생성 | 차단 후 HR 검토 |

문장이 다소 어색해도 행동·날짜·대상·수량이 보존되면 품질 오류로 차단하지 않습니다.

## 실행

```bash
.venv/bin/python -m fowoco_knowledge check-notice-quality \
  fowoco-knowledge/examples/notice_quality_check.json
```

`source_slots`는 생성 전 HR 승인 값이고, `candidate_slots`는 생성문에서 다시 추출한 값입니다.
출력의 `gate`가 `BLOCK_AND_REVIEW`이면 근로자에게 발송할 수 없습니다.

## 평가 데이터 해석

`notice_quality_cases.jsonl` 12건 중 9건은 검사기를 시험하기 위해 오류를 의도적으로 넣은
적대적 사례입니다. 따라서 이 데이터에서 계산한 핵심값 보존율은 Language Agent의 성능이
아닙니다. `contract_accuracy`는 검사 코드가 예상 오류와 게이트를 정확히 재현했는지만 나타냅니다.

실제 Language Agent 성능은 모델 후보가 생성한 별도 평가 출력에 대해 다음 지표로 측정합니다.

- 핵심값 보존율
- 치명값 누락률
- 근거 없는 값 추가율
- 치명 오류 검수 통과율
- HR 핵심정보 수정률
