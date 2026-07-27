# Intent 경계 사례 A/B 독립 검수 가이드

- 규칙 기준: Intent 라벨 규칙 v1.1
- 원본 데이터: `data/intent/hr_intent_dataset.jsonl`
- 검수 상태: 시작 전
- 선행 작업: PR #29 승인 및 `main` 반영

이 검수팩은 1,340건 전체를 다시 펼치지 않고, 규칙 v1.1에서 합의가 필요한 경계
사례를 먼저 검수하기 위한 것이다. 현재 Intent나 evidence를 변경하지 않으며,
Reviewer A와 B의 독립 검수 결과가 모두 제출된 뒤 합의본을 만든다.

## 1. 검수 파일

| Reviewer | 파일 |
| --- | --- |
| A | `data/review/intent_boundary_review_a.csv` |
| B | `data/review/intent_boundary_review_b.csv` |

두 파일의 후보, 정렬, 현재 라벨은 동일하다. 검수자는 상대방 파일을 열거나 결과를
공유하지 않고 자신의 파일만 작성한다.

## 2. 후보 선정 기준

다음 조건 중 하나 이상을 만족하는 레코드를 추출한다.

| Boundary Flag | 선정 기준 | 검수 포인트 |
| --- | --- | --- |
| `PAYROLL_ACCOUNT` | 급여계좌, 통장사본, 계좌 개설·변경·등록·정보 | `PAYROLL_EXPLANATION` 오분류 여부 |
| `LEAVE_BOUNDARY` | 휴가, 연차, 병가 | `WORK_INSTRUCTION`, `EMPLOYMENT_CHANGE`, `OUT_OF_SCOPE` 경계 |
| `COMPLETED_STATUS` | 완료·처리됨·변경 없음 등 상태 표현 | 새 요청 없는 순수 상태 보고 여부 |
| `EXTERNAL_EXECUTION` | 접수·신고·기관·자동 실행 표현 | Intent와 `GRD-004` 실행 차단 경계 |
| `LONG_EVIDENCE` | evidence가 24자 이상 | 가장 짧고 완결된 exact substring인지 |

하나의 레코드가 여러 Flag를 가질 수 있다. `PAYROLL_ACCOUNT`, `COMPLETED_STATUS`,
`EXTERNAL_EXECUTION` 중 하나라도 포함하면 `HIGH`, 나머지는 `MEDIUM`이다.

## 3. 작성 필드

검수자는 다음 세 필드만 작성한다.

| 필드 | 허용 값 | 작성 방법 |
| --- | --- | --- |
| `decision` | `KEEP`, `CHANGE`, `EXCLUDE`, `NEEDS_DISCUSSION` | 현재 라벨 유지 여부 |
| `proposed_intents_json` | JSON 또는 빈 값 | `CHANGE`일 때 수정할 전체 `intents` 배열 |
| `review_note` | 자유 텍스트 | 변경 이유나 합의가 필요한 경계 |

`proposed_intents_json`의 evidence는 원문에 존재하는 연속 부분 문자열이어야 한다.
실명, 외국인등록번호, 여권번호, 전화번호, 계좌번호 등 실제 개인정보를 추가하지
않는다.

## 4. 독립 검수 절차

1. Reviewer A와 B에게 각각 다른 CSV를 전달한다.
2. `HIGH`를 먼저 검수하고 이후 `MEDIUM`을 검수한다.
3. 상대방의 결과를 확인하지 않은 상태로 각 파일을 제출한다.
4. 두 파일의 `decision`과 제안 JSON을 비교해 일치·불일치 목록을 만든다.
5. 불일치 항목만 합의 검수하고 최종 consensus 데이터를 만든다.
6. 합의 전에는 원본 1,340건과 원본 checksum을 변경하지 않는다.

## 5. 한계

- 키워드 기반 후보 추출이므로 모든 의미 오류를 보장하지 않는다.
- 후보로 선정됐다는 사실은 현재 라벨이 잘못됐다는 뜻이 아니다.
- 이 검수팩은 독립 Gold Test가 아니며 모델 성능 주장에 사용할 수 없다.
- PR #29의 규칙이 변경되면 후보 선정 규칙과 검수팩을 다시 생성해야 한다.

관련 작업은 [GitHub Issue #30](https://github.com/fowoco/knowledge/issues/30)에서
추적한다.
