# Seed 40건 독립 검수 사용설명서

## 1. 검수 목적

두 검수자가 동일한 Seed 40건을 서로 보지 않고 분류해 FOWOCO의 Intent·Domain 기준이
일관되게 적용되는지 확인합니다. 이번 검수의 핵심 정답은 `intents`와 `domains`이며,
Workflow·Slot·다음 행동은 Agent 설계를 위한 보조 라벨입니다.

검수자는 영어 태그를 CSV에 입력합니다. 한글은 의미를 확인하기 위한 설명이며 CSV에는
입력하지 않습니다.

## 2. 시작 전 확인

1. 검수자 A는 `FOWOCO_Seed40_독립검수_REV-A.xlsx`, 검수자 B는
   `FOWOCO_Seed40_독립검수_REV-B.xlsx`만 열기
2. 상대 검수 파일과 `gold_seed.csv`의 기존 제안 라벨은 열지 않기
3. `request_id`부터 `system_context`까지 수정하지 않기
4. 행을 추가·삭제·정렬하지 않기
5. 실제 이름·전화번호·외국인등록번호를 입력하지 않기
6. `검수작성` 시트의 노란 셀만 작성하기

라벨 전체 목록은 `data/review/label_reference.csv`에서도 확인할 수 있습니다.

### Excel 파일 구조

| 시트 | 용도 | 검수자 작업 |
| --- | --- | --- |
| `사용안내` | 작성 순서와 주의사항 확인 | 작업 전 1회 읽기 |
| `검수작성` | 40건의 라벨과 판단 근거 입력 | 노란 셀과 드롭다운 작성 |
| `CSV_EXPORT` | 시스템 제출 형식으로 자동 변환 | 수정하지 않고 CSV로 저장 |
| `라벨참조` | 영문 태그와 한글 의미 확인 | 판단이 어려울 때 조회 |
| `드롭다운목록` | Excel 선택 목록의 원본 | 수정 금지 |

드롭다운에는 `영문 태그 = 한글 의미`가 함께 표시되지만 `CSV_EXPORT` 시트에는 모델과
프로그램이 사용하는 영문 태그만 자동으로 출력됩니다.

## 3. 한 행을 검수하는 순서

### 1단계. 입력 상황 읽기

- `input_mode`: 입력 목적과 사용 화면
- `hr_utterance`: HR 담당자가 입력한 원문
- `system_context`: 선택된 근로자·파일·기준일 등 화면에서 이미 아는 정보

원문에 없는 값이라도 `system_context`에 있으면 Slot으로 추출할 수 있습니다.

### `WRK-DEMO-001`의 의미

`WRK-DEMO-001`은 실제 근로자 이름이나 외국인등록번호가 아니라 테스트용 내부 근로자
식별자입니다. `WRK`는 Worker, `DEMO`는 가상 데이터, `001`은 일련번호를 뜻합니다.

현재 Seed의 `WRK-DEMO-*` 표기는 모델이 근로자 식별자를 Slot으로 추출하고 업무카드와
연결할 수 있는지 확인하기 위한 기술 검증용 표현입니다. 실제 서비스에서는 HR 담당자가
근로자 검색·선택 UI에서 대상을 고르고, 화면이 내부 `worker_id`를 `system_context`로
전달합니다. 따라서 사용자가 식별자를 직접 외워 입력할 필요가 없습니다.

```text
화면 표시: 응웬 반 A 선택됨
HR 입력: 체류연장 준비해줘
시스템 전달: worker_id=WRK-000001
```

검수 중에는 원문과 `system_context`를 수정하지 않고 현재 Seed가 의도한 Slot 추출 여부만
판단합니다.

| 표시 태그 | 한글 의미 |
| --- | --- |
| `WORKER_MESSAGE` | 근로자에게 전달할 안내 작성 요청 |
| `AGENT_TASK` | Agent에게 업무 처리를 요청 |
| `INTERNAL_REQUEST` | 내부 자료 조회·작성 요청 |

| 출처 태그 | 한글 의미 |
| --- | --- |
| `TEAM_SYNTHETIC` | 팀이 기획 기준에 따라 만든 합성 문장 |
| `INTERVIEW_DERIVED_ANON` | 인터뷰 내용을 식별 불가능하게 바꾼 파생 문장 |

### 2단계. Intent 선택

Intent는 사용자가 **무엇을 해 달라고 했는지**를 나타냅니다.

| 입력 태그 | 한글 의미 | 선택 기준 |
| --- | --- | --- |
| `WORKER_ONBOARDING` | 근로자 등록·정보변경 | 문서로 신규 등록 초안을 만들거나 기본정보 변경 |
| `EXPIRY_RENEWAL` | 체류·계약 만료 및 갱신 | 체류·계약 만료 확인 또는 갱신 준비 |
| `DOCUMENT_REQUEST` | 서류 요청·확인 | 서류 요청, 제출 여부 확인, 일반 증명서 준비 |
| `PAYROLL_EXPLANATION` | 급여·공제 설명 | 기존 명세서·근태 근거로 차이 설명 |
| `WORK_INSTRUCTION` | 업무·근무일정 안내 | 출근시간, 작업행동, 연락절차 안내 |
| `EMPLOYMENT_CHANGE` | 고용변동·이탈 후속조치 | 퇴사, 무단결근, 연락두절 등의 확인·후속업무 |
| `OUT_OF_SCOPE` | 서비스 범위 밖 | 법률 최종판단, 기관 자동제출, 영상감시, 생산예측 |

서로 독립된 결과물이 두 개 필요하면 `|`로 연결합니다.

```text
EXPIRY_RENEWAL|DOCUMENT_REQUEST
```

### 3단계. Domain 선택

Domain은 요청이 **어떤 업무 대상을 다루는지**를 나타냅니다.

| 입력 태그 | 한글 의미 |
| --- | --- |
| `WORKER_PROFILE` | 근로자 기본정보 |
| `STAY` | 체류기간·체류자격 |
| `CONTRACT` | 근로계약 |
| `DOCUMENT` | 증빙·제출서류 |
| `INSURANCE` | 보험·자격취득 |
| `PAYROLL` | 급여·수당·공제 |
| `ATTENDANCE` | 근태·결근·지각 |
| `WORK_SCHEDULE` | 근무일정·업무안내 |
| `EMPLOYMENT_STATUS` | 입사·퇴사·고용변동 |
| `GENERAL_ADMIN` | 일반 사무·증명서 |

복수 Domain은 `STAY|DOCUMENT`처럼 입력합니다. `OUT_OF_SCOPE` 요청에 업무 대상이
명확하지 않으면 비워둘 수 있습니다.

### 4단계. Workflow 선택

| 입력 태그 | 한글 의미 |
| --- | --- |
| `WF-WRK-001` | 문서 기반 근로자 등록 초안 |
| `WF-STY-001` | 체류기간 연장 준비·제출 추적 |
| `WF-CON-001` | 근로계약·고용허가기간 연장 준비 |
| `WF-DOC-001` | 근로자 서류 요청·제출 추적 |
| `WF-PAY-001` | 급여명세서 차이 설명 |
| `WF-INS-001` | 업무·근무일정 안내 |
| `WF-CHG-001` | 고용변동 사건 확인·신고 추적 |
| `WF-ADM-001` | 재직증명서 등 일반 증명서 요청 |

복합 업무는 `WF-STY-001|WF-DOC-001`처럼 입력합니다. `OUT_OF_SCOPE`이면 비워둡니다.
신고 의무·기한·필요서류의 사실 여부가 불확실해도 가장 가까운 Workflow 후보를 입력하고
`decision`을 `EXPERT_REVIEW`로 표시합니다.

### 5단계. Slot과 누락정보 입력

`slots_json`에는 원문과 시스템 상황에서 확인되는 값만 입력합니다. 키는 아래 고정 태그를
사용하고, 값이 없으면 `{}`를 입력합니다.

| 입력 태그 | 한글 의미 |
| --- | --- |
| `worker_id` | 내부 근로자 식별자 |
| `worker_name` | HR 검토용 표시 이름. 검수 중 실제 이름 추가 금지 |
| `source_document_id` | 선택된 원본 문서 ID |
| `document_type` | 요청·확인할 서류 유형 |
| `due_at` | 제출·조치 마감시각 |
| `stay_expiry_date` | 체류기간 만료일 |
| `contract_end_date` | 근로계약 종료일 |
| `submission_channel` | 제출 장소·경로 |
| `effective_at` | 변경·업무 시작시각 |
| `work_location` | 공장·라인·작업 위치 |
| `work_action` | 수행할 구체적인 행동 |
| `pay_period` | 설명 대상 급여 귀속월 |
| `pay_item` | 급여·수당·공제 항목 |
| `comparison_period` | 비교할 이전 급여 귀속월 |
| `change_type` | 고용변동 후보 유형 |
| `incident_at` | 사건 발생시각 |
| `awareness_at` | HR이 사건을 인지한 시각 |
| `reason` | 요청·변경·설명의 사유 |

`change_type` 값은 다음 고정 태그를 사용합니다.

| 입력 태그 | 한글 의미 |
| --- | --- |
| `RESIGNATION` | 퇴사 의사·퇴사 예정 |
| `ABSENCE` | 무단결근·미출근 |
| `UNREACHABLE` | 연락두절·소재 확인 필요 |
| `WORKPLACE_CHANGE` | 사업장 변경 관련 사건 |
| `OTHER` | 그 밖의 고용변동 후보 |

현재 Seed에 등장하는 대표 서류·제출경로 코드는 다음과 같습니다.

| 입력 태그 | 한글 의미 |
| --- | --- |
| `PASSPORT_COPY` | 여권 사본 |
| `ALIEN_REGISTRATION_CARD_COPY` | 외국인등록증 앞·뒷면 사본 |
| `EMPLOYMENT_CERTIFICATE` | 재직증명서 |
| `HR_OFFICE` | 인사·총무팀 직접 제출 |

```json
{"worker_id":"WRK-DEMO-020","document_type":"PASSPORT_COPY","due_at":"2026-08-01T17:00:00+09:00"}
```

`missing_slots`에는 해당 Workflow에 필요하지만 확인되지 않은 **Slot 태그명**만 입력합니다.

```text
worker_id|submission_channel
```

### 6단계. 모호표현 입력

모호한 원문 표현 자체가 아니라 아래 **모호성 유형 태그**를 입력합니다.

| 입력 태그 | 한글 의미 | 대표 표현 |
| --- | --- | --- |
| `TIME` | 시간 모호 | 오늘, 다음 주, 퇴근 전 |
| `LOCATION` | 장소 모호 | 저쪽, 거기, 현장 |
| `OBJECT` | 대상물·서류 모호 | 그 서류, 그거, 기계 |
| `TARGET` | 대상자 모호 | 외국인 직원, 그 사람 |
| `AMOUNT` | 금액 모호 | 조금, 비슷한 금액 |
| `ACTION` | 행동·산출물 모호 | 처리해줘, 알아서, 준비해줘 |

복수이면 `TIME|TARGET`처럼 입력하고, 모호성이 없으면 비워둡니다.

### 7단계. 민감도와 다음 행동 입력

| 입력 태그 | 한글 의미 |
| --- | --- |
| `low` | 일반 조회·낮은 위험 |
| `medium` | 외부 안내 전 확인 필요 |
| `high` | 개인정보·체류·계약·급여 등 HR 승인 필요 |
| `critical` | 고용변동·법률판단·영상감시·기관 자동제출 등 고위험 |

복합 Workflow는 가장 높은 민감도를 사용합니다.

| 입력 태그 | 한글 의미 | 선택 기준 |
| --- | --- | --- |
| `REQUEST_CLARIFICATION` | 누락·모호정보 추가질문 | 필요한 정보가 부족함 |
| `REQUEST_CLASSIFICATION_CONFIRMATION` | 업무유형 재확인 | Intent 후보를 하나로 정하기 어려움 |
| `CREATE_DRAFT_TASK` | 업무카드 초안 생성 | 정보가 충분하고 일반적인 업무 |
| `REQUIRE_HR_REVIEW` | HR 검토 요청 | 정보는 충분하지만 민감 업무 |
| `SPLIT_AND_CONFIRM` | 복합 업무 분리·확인 | 독립 업무가 두 개 이상 |
| `OUT_OF_SCOPE` | 지원 범위 안내 | 서비스가 수행하면 안 되는 요청 |

### 8단계. 검수 결과 기록

| 입력 태그 | 한글 의미 | 선택 기준 |
| --- | --- | --- |
| `APPROVE` | 승인 | 문장과 입력한 라벨을 그대로 사용할 수 있음 |
| `CORRECT` | 수정 필요 | 문장·상황 또는 라벨 기준에 수정할 점이 있음 |
| `REJECT` | 제외 | 중복·비현실·판단 불가능으로 데이터에서 제외 필요 |
| `EXPERT_REVIEW` | 전문가 검토 필요 | 법정기한·신고절차·필요서류·조치안 확인 필요 |

`OUT_OF_SCOPE`는 필요한 음성 사례이므로 자동으로 `REJECT`하지 않습니다. 정상적인 범위 밖
요청이면 `intents=OUT_OF_SCOPE`, `decision=APPROVE`로 기록합니다.

`notes`에는 한 문장 이상 판단 근거를 씁니다.

```text
체류연장 준비와 여권 사본 요청은 결과물이 달라 복합 Intent로 판단
```

`reviewed_at`은 Excel의 날짜 자동변환을 피할 수 있는 ISO 8601 기본형으로 입력합니다.

```text
20260716T153000+0900
```

## 4. 완료 전 체크리스트

- [ ] 40건 모두 `intents`, `decision`, `notes`, `reviewed_at` 작성
- [ ] 지원 범위 안 사례는 `domains`, `workflow_ids`, `sensitivity`, `next_action` 작성
- [ ] `slots_json`이 없을 때 빈칸이 아니라 `{}` 입력
- [ ] 복수 태그는 쉼표가 아닌 `|`로 구분
- [ ] 한글 설명을 라벨 셀에 입력하지 않음
- [ ] 실제 개인정보를 추가하지 않음
- [ ] 행 추가·삭제·정렬 없이 `CSV_EXPORT` 시트를 UTF-8 CSV로 저장

## 5. Excel에서 CSV로 제출하는 방법

1. 배정된 Excel 파일에서 `검수작성` 시트의 40건을 모두 작성
2. 상단 완료 건수가 `40 / 40`인지 확인
3. `CSV_EXPORT` 시트로 이동해 `#VALUE!`, `#REF!` 같은 오류가 없는지 확인
4. `파일 > 다른 이름으로 저장` 선택
5. 파일 형식을 `CSV UTF-8(쉼표로 분리)(*.csv)`로 선택
6. 검수자 A는 `reviewer_a.csv`, 검수자 B는 `reviewer_b.csv`로 저장
7. 현재 시트만 저장한다는 Excel 안내가 나오면 `CSV_EXPORT` 시트만 저장
8. 저장한 CSV를 다시 열어 한글 깨짐, 복수 태그의 `|`, `slots_json`의 중괄호를 확인

CSV를 바로 편집하지 않습니다. 수정할 내용이 있으면 Excel의 `검수작성` 시트에서 고친 뒤
`CSV_EXPORT` 시트를 다시 저장합니다.

## 6. 판단이 어려울 때

Intent·Domain이 애매하면 가장 타당한 후보를 입력하고 `notes`에 고민한 경계를 적습니다.
법령·행정 사실이 불확실하면 분류 라벨은 작성하되 `decision=EXPERT_REVIEW`로 표시합니다.
검수자끼리 답을 맞추지 않습니다. 불일치 자체가 라벨 가이드에서 보완할 부분을 찾는 자료입니다.
