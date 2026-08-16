# Agent 연동 설계

## 실행 경계

```text
입력 수집
  자연어 / PDF·이미지 / Excel / D-day 이벤트
        |
AI 이해 계층
  Intent·Domain 분류 + Slot Filling
        |
Knowledge·Workflow 계층
  필수정보 검사 + 공식 출처 + 체크리스트 + 상태 전이
        |
생성·검증 계층
  쉬운 한국어·다국어 초안 + 핵심값 검증 + HR 승인
        |
실행·회수 계층
  업무카드 + 근로자 보안 링크 + 응답·제출 + 후속 티켓
```

## 논리 Agent와 실제 호출

| 논리 역할 | 구현 방식 | 별도 LLM 호출 |
| --- | --- | ---: |
| Coordinator | 상태머신·분기 코드 | 없음 |
| Intent/Domain Agent | 분류모델 또는 LLM Structured Output | 1회 |
| Slot Filling Agent | Intent와 함께 JSON 추출 | 위 호출에 통합 |
| Ambiguity Agent | 필수 Slot 규칙 + 모호표현 사전 | 원칙적으로 없음 |
| Workflow Agent | 이 패키지의 Catalog·체크리스트 조회 | 없음 |
| Guardrail/Language Agent | 검증 후 안내문 생성 | 1회 |
| Response/Ticket Agent | 버튼 응답은 규칙, 자유질문만 분류 | 필요 시 1회 |

7개 논리 역할이 7번의 LLM 호출을 의미하지 않습니다. 일반 요청은 2회 내외의 모델 호출을 목표로 합니다.

## Context Pack 사용

```python
from fowoco_knowledge import KnowledgeRepository, RequestEvaluator

repository = KnowledgeRepository()
context = repository.compile_context("WF-STY-001")
result = RequestEvaluator(repository).evaluate(classified_request)
```

`compile_context` 결과에는 해당 Workflow에 필요한 Intent 설명, 필수 Slot, Guardrail,
체크리스트, 공식 출처만 포함됩니다. 전체 지식 파일을 매번 프롬프트에 넣지 않습니다.

### UI·Agent 공용 Slot 계약

`context["slot_policy"]["slot_contracts"]`는 내부 Slot 키와 사용자 표현을 분리한다.

```json
{
  "worker_id": {
    "display_name_ko": "요청 대상 근로자",
    "worker_prompt_easy_ko": "누구에게 서류를 요청할지 선택해 주세요.",
    "source_priority": [
      "HR_CONFIRMED_PROFILE",
      "SELECTED_UI_CONTEXT",
      "SYSTEM_RECORD",
      "HR_INPUT",
      "MODEL_EXTRACTION"
    ],
    "responsible_actor": "HR",
    "required": true,
    "validation_rules": [
      "NON_EMPTY",
      "KNOWN_WORKER_ID",
      "UNIQUE_SUBJECT_MATCH"
    ]
  }
}
```

- UI는 `display_name_ko`를 HR 입력 폼에 사용한다.
- 근로자에게 되물을 때는 내부 키 대신 `worker_prompt_easy_ko`를 사용한다.
- Agent는 `source_priority` 순서대로 확인된 값을 우선하고 모델 추출값은 후보로만 둔다.
- `responsible_actor`는 최종 확인 책임을 나타내며 AI를 담당 주체로 두지 않는다.
- `required`와 기존 `required` 배열은 CI에서 일치 여부를 검사한다.
- `validation_rules`는 `required_slots.yaml`의 규칙 정의를 참조한다.

내부 Slot·Intent·Workflow 키가 렌더링된 근로자 문장에 포함되면 Knowledge validation이
실패한다.

### 계약 원본과 소비 순서

필드 이름, 필수 여부, Workflow 연결과 실행 시나리오의 원본은 이 저장소의 버전형
Context Pack이다. AI나 Server에서 먼저 필드를 하드코딩한 뒤 Knowledge에 역으로
맞추지 않는다.

```text
Knowledge 변경·검증
  -> 버전형 Context Pack
  -> AI가 Intent·Workflow·필수 Slot 조회
  -> Server가 허용된 Context Slot만 tenant 범위에서 조회
  -> Client가 HR·근로자 입력이 필요한 항목만 표시
```

- 새로운 필드가 필요하면 `required_slots.yaml`에 의미·타입·출처·책임·검증 규칙을 먼저 추가한다.
- `resolvable_from_context`는 Server가 임의 SQL이 아니라 고정 Resolver로 조회할 수 있는 key다.
- `passport_status`, `arc_status`는 개인정보 원문이 아니라 문서 제출 상태만 전달하는 조회형 Context Slot이다.
- Server projection과 AI 내장 fallback은 Context Pack에서 생성하거나 같은 version으로 고정한다.
- 데모·운영에서 Knowledge를 읽지 못하면 오래된 내장 규칙으로 조용히 실행하지 않고 계약 오류로 중단한다.

### 재계약·체류연장 대표 시나리오

`EXPIRY_RENEWAL` 하나는 발화 의미를 나타내며, 실제 업무는 두 Workflow로 나뉠 수 있다.

```text
EXPIRY_RENEWAL
  -> WF-CON-001 근로계약 갱신·고용허가기간 연장 준비
  -> WF-STY-001 체류기간 연장 준비·제출 추적
```

발화가 두 업무를 모두 명시하면 두 후보를 순서대로 제시하고 HR이 각각 승인·삭제한다.
이는 복수 Intent를 강제하는 계약이 아니라, 하나의 Intent가 여러 독립 Workflow로
구체화되는 경우다. 각 Workflow는 별도 상태와 완료 증빙을 유지한다.

현재 구현은 **버전형 Context Pack**입니다. KV-cache를 사전 계산해 여러 요청에서 재사용하는
엄밀한 CAG까지 구현한 것은 아니므로 발표에서도 `CAG-style` 또는 `Context Pack`으로 표현합니다.

## 상태 전이

```text
DRAFT
  -> NEEDS_INFO
  -> READY_FOR_REVIEW
  -> APPROVED
  -> IN_PROGRESS
  -> WAITING_WORKER / WAITING_EXTERNAL
  -> COMPLETED
```

- `NEEDS_INFO`: 필수 Slot 또는 명확한 대상이 없음
- `READY_FOR_REVIEW`: 초안과 검증 결과가 준비됨
- `APPROVED`: HR이 외부 전달 또는 후속 실행 승인
- `WAITING_WORKER`: 근로자 확인·질문·제출 대기
- `WAITING_EXTERNAL`: 고용센터·출입국 등 외부 처리 대기
- `COMPLETED`: Workflow별 완료 증빙 존재

## 복합 요청

“체류연장 준비하고 여권 사본도 요청해줘”를 오류로 반환하지 않습니다.

1. 모델이 `EXPIRY_RENEWAL`, `DOCUMENT_REQUEST` 두 후보 반환
2. Coordinator가 `WF-STY-001`, `WF-DOC-001` 후보카드 생성
3. 공통 Slot인 `worker_id` 재사용
4. HR이 각 카드 승인 또는 삭제
5. 승인된 Workflow만 독립 상태로 진행

## 보안

- 원본 문서는 암호화 저장소에 두고 Agent에는 `source_document_id`와 필요한 필드만 전달
- 품질개선 로그에는 마스킹된 문장, 모델 결과, HR 수정 차이만 저장
- 급여·체류·고용변동은 확신도가 높아도 HR 승인 생략 금지
- 기관 사이트 자동 로그인·제출 금지
