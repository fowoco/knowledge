# 6대 Workflow 공통 실행 계약

## 목적

Intent와 업무 설명만으로는 Server가 어떤 단계를 먼저 열고, 무엇을 기다리고, 언제
완료할지 알 수 없다. `knowledge/workflow_runtime.yaml`은 기존 Catalog를 바꾸지 않고
여섯 대표 업무를 같은 상태·이벤트·의존성 규칙으로 실행하기 위한 계약이다.

## 실행 방법

```text
자연어·기한·OCR·근로자 응답 이벤트
  → Intent별 Runtime Profile 선택
  → 필수 Slot 확인
  → 의존성이 충족된 Stage를 READY로 전환
  → 완료 증빙 저장
  → HR 승인 또는 직접 기관 처리
  → 다음 Stage 개방
```

`depends_on`이 모두 끝난 Stage는 같은 `parallel_group` 안에서 병렬로 열 수 있다.
완료는 결과 문구만으로 확정하지 않고 `completion_evidence`와 `human_gate`를 함께
검사한다.

## 여섯 Profile

| Profile | 종류 | 재사용 관계 |
| --- | --- | --- |
| `RUN-EXPIRY-RENEWAL` | Master | 계약·공통 서류 요청·체류 연장을 연결 |
| `RUN-WORKER-ONBOARDING` | Master | 필요 시 공통 서류 요청 Subflow 사용 |
| `RUN-EMPLOYMENT-CHANGE` | Master | 증빙 보완 시 공통 서류 요청 Subflow 사용 |
| `RUN-DOCUMENT-REQUEST` | Subflow | 다른 Master가 재사용 가능 |
| `RUN-PAYROLL-EXPLANATION` | Master | 급여 계산과 설명 검토 분리 |
| `RUN-WORK-INSTRUCTION` | Master | 안내 승인과 근로자 응답 추적 분리 |

복합 발화는 evidence가 먼저 등장한 Intent를 대표로 표시하되 여러 Workflow 후보로
분리하고, 실행 전 HR 확인을 받는다.

## 안전 기준

- 외부기관 제출·법적 상태·퇴사 확정은 HR 승인 없이 완료하지 않는다.
- 근로자 메시지와 번역문은 HR 승인 뒤에만 전달한다.
- 이벤트 재처리는 같은 멱등성 키로 중복 Task·문서를 만들지 않는다.
- `OUT_OF_SCOPE`는 Runtime Profile이 아니라 수동 처리 분기다.

정상·필수정보 누락·수동 검토 경로는
`data/evaluation/workflow_runtime_cases.jsonl`의 18개 Fixture로 고정한다.
