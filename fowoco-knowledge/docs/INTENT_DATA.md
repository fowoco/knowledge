# Intent 라벨링 및 데이터 계약

- 규칙 버전: 1.1
- 갱신일: 2026-08-11
- 기준 파일: `data/intent/hr_intent_dataset_final.jsonl`
- 데이터 상태: 검수 완료 Train/Validation 데이터, 독립 Gold Test 아님

이 문서는 HR 담당자의 발화에서 FOWOCO MVP가 지원하는 Intent와 근거 문구를
라벨링하는 기준을 정의한다. Intent 모델의 책임은 `Intent + evidence` 추출까지다.
Workflow 선택, Slot 수집, 외부기관 제출, 법적 판단, 업무 실행 여부는 후속 규칙과
담당자 검토의 책임이다.

## 1. Intent 정의

| Intent Code | 적용 기준 |
| --- | --- |
| `WORK_INSTRUCTION` | 작업 지시, 근무 일정 변경, 현장 행동 또는 연락 절차 안내 |
| `DOCUMENT_REQUEST` | 특정 서류를 요청·수령하거나 미제출 상태를 추적하는 행위 |
| `PAYROLL_EXPLANATION` | 급여, 수당, 공제, 명세 차이 또는 근태 반영 내역 설명 |
| `WORKER_ONBOARDING` | 신규 근로자 등록 초안, 최초 보험 가입, 초기 프로필 처리 |
| `EMPLOYMENT_CHANGE` | 퇴사, 무단결근·연락두절, 사업장 변경 등 고용상태 변동 확인과 신고 준비 |
| `EXPIRY_RENEWAL` | 체류기간, 근로계약, 고용허가기간의 만료 확인과 연장·갱신 준비 |
| `OUT_OF_SCOPE` | 지원 Intent가 없거나 현재 Intent 모델의 입력 범위를 벗어난 요청 |

세부 설명의 기준 원본은 [`knowledge/intents.yaml`](../knowledge/intents.yaml)이다.
이 문서와 원본의 의미가 충돌하면 두 파일을 함께 수정하고 검수한다.

## 2. 학습·검증 데이터 스키마

현재 JSONL의 한 줄은 다음 구조만 사용한다.

```json
{
  "id": 1,
  "hr_input": "재계약 준비하면서 서명본도 받아서 첨부해줘",
  "intents": [
    {
      "intent": "EXPIRY_RENEWAL",
      "evidence": "재계약 준비하면서"
    },
    {
      "intent": "DOCUMENT_REQUEST",
      "evidence": "서명본도 받아서"
    }
  ]
}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | integer | 파일 안에서 중복되지 않는 양의 정수 |
| `hr_input` | string | HR 담당자 원문 발화 |
| `intents` | array | 정답 Intent 1개 이상 |
| `intents[].intent` | string | 7개 Intent Code 중 하나 |
| `intents[].evidence` | string \| null | 원문의 연속된 부분 문자열. `OUT_OF_SCOPE`만 `null` |

`source`와 `split`은 레코드 필드가 아니다. 데이터 버전은
`data/intent/manifest.yaml`, Train/Validation 분할은
`data/intent/splits/manifest.yaml`과 ID 파일로 관리한다. 현재 1,340건과 Validation
268건을 독립 Gold Test 또는 최종 성능 주장에 사용하지 않는다.

정식 구조 검증 기준은
[`schemas/intent-training-case.schema.json`](../schemas/intent-training-case.schema.json)이다.

## 3. 모델 출력 스키마

Intent 모델은 다음 구조만 출력한다.

```json
{
  "intents": [
    {
      "intent": "EXPIRY_RENEWAL",
      "evidence": "재계약 준비하면서"
    },
    {
      "intent": "DOCUMENT_REQUEST",
      "evidence": "서명본도 받아서"
    }
  ]
}
```

`request_id`, 입력 원문, 모델명, 생성 시각, 검증 상태를 포함하는 최종 응답
envelope은 서버의 책임이다. 모델 학습 정답에 해당 값을 넣지 않는다.

## 4. 공통 라벨링 규칙

### 4.1 지금 요청된 행위를 기준으로 분류

최종 목적을 추정해 라벨을 추가하지 않는다. 발화에 명시된 요청·확인·준비 행위와
사건만 분류한다.

- `여권 사본 받아줘` → `DOCUMENT_REQUEST`
- `계약 만료가 다가오니 재계약 준비해줘` → `EXPIRY_RENEWAL`
- `첨부한 계약서로 신규 등록 초안 만들어줘` → `WORKER_ONBOARDING`

### 4.2 DOCUMENT_REQUEST는 서류 확보 행위가 명시된 경우만 추가

`받아줘`, `제출받아`, `요청해`, `미제출 확인`, `첨부해줘`처럼 서류 확보나 추적
행위가 명시되어야 한다.

- 이미 첨부·제공된 서류를 사용하는 경우에는 추가하지 않는다.
- 목적 업무만 `준비해줘`, `진행해줘`라고 한 경우에는 추가하지 않는다.
- 서류 확보와 목적 업무가 모두 명시되면 두 Intent를 모두 붙인다.

### 4.3 Multi-Intent는 원문 등장 순서로 기록

Intent 배열은 각 `evidence`가 원문에 처음 나타난 순서로 기록한다. 이 배열 순서는
Workflow 실행 순서나 우선순위를 뜻하지 않는다.

### 4.4 OUT_OF_SCOPE는 다른 Intent와 공존하지 않음

`OUT_OF_SCOPE`이면 Intent 배열에는 해당 값 하나만 두고 `evidence`는 `null`로
기록한다. 지원되는 업무와 범위 밖 문구가 함께 있으면 지원 Intent만 기록하고,
실행 제한은 Guardrail에서 처리한다.

## 5. evidence 작성 기준

`evidence`는 다음 조건을 모두 만족해야 한다.

1. `hr_input`에 토씨까지 동일하게 존재하는 연속 부분 문자열이다.
2. 해당 Intent를 판단할 수 있는 가장 짧고 완결된 표현을 선택한다.
3. 배경 설명, 다른 Intent의 근거, 외부 실행 명령은 포함하지 않는다.
4. 같은 Intent의 근거가 여러 곳이면 현재 요청 행위를 가장 직접적으로 나타내는
   첫 번째 표현을 사용한다.

예:

```text
WRK-653: 고용허가기간 만료 임박, 연장신청서 받아서 즉시 접수
```

```json
{
  "intents": [
    {
      "intent": "EXPIRY_RENEWAL",
      "evidence": "고용허가기간 만료 임박"
    },
    {
      "intent": "DOCUMENT_REQUEST",
      "evidence": "연장신청서 받아서"
    }
  ]
}
```

`즉시 접수`는 외부기관 실행 표현이므로 `DOCUMENT_REQUEST`의 evidence에 포함하지
않는다.

## 6. 주요 경계 규칙

### 6.1 외부기관 실행

Intent 분류와 실행 허용 여부를 분리한다.

| 입력 유형 | Intent 처리 | 실행 처리 |
| --- | --- | --- |
| `체류연장 준비하고 여권 받아줘` | `EXPIRY_RENEWAL`, `DOCUMENT_REQUEST` | 담당자 검토 후 준비 업무만 수행 |
| `체류연장 접수까지 해줘` | `EXPIRY_RENEWAL` | 기관 제출은 `GRD-004`로 차단 |
| `홈페이지 접수 버튼만 대신 눌러줘` | 지원 업무 단서가 없으므로 `OUT_OF_SCOPE` | 실행하지 않음 |

외부기관 사이트 제출, 계약 확정, 급여 지급, 메시지 외부 발송은
[`knowledge/guardrail_rules.yaml`](../knowledge/guardrail_rules.yaml)의 `GRD-004`를
적용한다. 범위 밖 실행 문구를 별도 Intent로 만들거나 `DOCUMENT_REQUEST`에
포함하지 않는다.

### 6.2 휴가·결근

| 표현 | Intent |
| --- | --- |
| 연차 일정 안내, 교대·대체근무 지시 | `WORK_INSTRUCTION` |
| 무단결근, 연락두절, 이탈·퇴사 후속조치 | `EMPLOYMENT_CHANGE` |
| 휴가 잔여일수 계산처럼 현재 6개 업무에 없는 요청 | `OUT_OF_SCOPE` |

단순 `휴가`라는 단어만으로 `EMPLOYMENT_CHANGE`를 붙이지 않는다.

### 6.3 급여계좌

통장사본 요청은 `DOCUMENT_REQUEST`다. 신규 입사 처리의 일부로 급여계좌 정보를
등록하는 경우에는 `WORKER_ONBOARDING`을 함께 붙일 수 있다. 계좌 개설·변경 자체는
급여액·수당·공제 설명이 아니므로 `PAYROLL_EXPLANATION`을 붙이지 않는다.

### 6.4 완료·상태 보고

새로운 요청, 확인, 설명, 준비 또는 후속조치가 없는 순수 완료·상태 보고는 현재
HR 요청 분류 데이터의 범위 밖이므로 `OUT_OF_SCOPE`로 처리한다.

- `급여 문의 답변 완료함` → `OUT_OF_SCOPE`
- `퇴사했으니 신고 준비 업무 만들어줘` → `EMPLOYMENT_CHANGE`
- `등록 완료 여부 확인해줘` → `WORKER_ONBOARDING`

## 7. 검수 결과와 변경 기준

`hr_intent_dataset_final.jsonl`은 규칙 v1.1 경계 사례 재검수를 반영한 현재 기준
파일이다. 검수 전 원본과 비교해 124건의 Intent/evidence 라벨이 바뀌었고, ID와
`hr_input`은 그대로 유지했다. 검수 전 파일은 감사와 비교를 위해
`hr_intent_dataset.jsonl`에 보존한다.

다음 항목은 라벨 규칙 또는 데이터를 변경할 때 다시 우선 검수한다.

- Multi-Intent 순서가 원문의 evidence 순서와 다른 레코드
- `급여계좌`를 `PAYROLL_EXPLANATION`으로 분류한 레코드
- 일반 휴가를 `EMPLOYMENT_CHANGE`로 분류한 레코드
- 완료·상태 보고만 있는데 지원 Intent가 붙은 레코드
- 외부기관 접수·자동 실행 문구가 evidence에 포함된 레코드
- evidence가 판단에 필요한 범위보다 길거나 다른 Intent까지 포함한 레코드

자동 검증은 JSON Schema, SHA-256, ID 중복, Intent Code, `OUT_OF_SCOPE` 단독성,
evidence 원문 포함 여부, Multi-Intent 순서와 Train/Validation 분할을 검사한다.
의미 경계는 자동으로 확정하지 않고 검수자 합의로 변경한다. 변경 시 final 데이터와
두 manifest의 version·통계·SHA-256을 함께 갱신한다.
