# 데이터 작성 가이드

## 목적

`gold_seed.csv`는 당장 파인튜닝하기 위한 대규모 학습셋이 아닙니다.
팀이 같은 라벨 기준으로 문장을 만들고, Agent 분기와 모델 출력을 검증하기 위한 초기 기준입니다.

## 컬럼

| 컬럼 | 작성 기준 |
| --- | --- |
| `request_id` | `SEED-001` 형식의 고유 ID |
| `source` | `TEAM_SYNTHETIC` 또는 `INTERVIEW_DERIVED_ANON` |
| `input_mode` | 근로자 전달문 `WORKER_MESSAGE`, Agent 처리요청 `AGENT_TASK`, 내부 조회 `INTERNAL_REQUEST` |
| `hr_utterance` | HR 담당자가 실제 입력할 법한 한 문장 |
| `system_context` | 이미 선택된 근로자·문서·기준일 등 화면 상황 |
| `intents` | 복합요청은 `|`로 구분한 6개 Intent |
| `domains` | 체류·계약·급여 등 업무 대상 영역 |
| `workflow_ids` | 실행 후보 Workflow ID. 복합요청은 여러 개 가능 |
| `slots_json` | 문장에서 확정적으로 추출 가능한 값만 JSON 객체로 기록 |
| `missing_slots` | Workflow 실행에 필요하지만 문장·화면에 없는 값 |
| `ambiguities` | `TIME`, `LOCATION`, `OBJECT`, `TARGET`, `AMOUNT`, `ACTION` |
| `sensitivity` | `low`, `medium`, `high`, `critical` |
| `next_action` | 추가질문, HR 검토, 후보 분리 등 시스템의 다음 행동 |
| `expected_output` | 화면에 생성되어야 할 산출물 |
| `review_status` | `DRAFT` → `REVIEWED_ONCE` → `GOLD` |

## 작성·검수 순서

1. 작성자가 한 행 작성
2. 검수자 A가 Intent·Domain·Workflow 확인
3. 검수자 B가 Slot·누락·모호성 확인
4. 불일치는 회의에서 기준을 정하고 가이드 갱신
5. 합의된 행만 `GOLD`로 변경
6. 평가용 사례는 별도 파일로 이동하고 이후 프롬프트 예시에 사용하지 않음

## 현실적인 수량 단계

| 단계 | 목적 | 권장 규모 |
| --- | --- | ---: |
| Seed V1 | 라벨 체계와 Agent 분기 확인 | 60~80건 |
| 평가 V1 | 프롬프트·모델 비교 | 15~30건 |
| Baseline | 6개 Intent 분류 비교 | 클래스당 약 100건, 총 600건 수준 |
| 고도화 | 실제 운영 표현과 복합요청 반영 | 익명 운영 로그를 검수해 점진 확장 |

600건은 성능을 보장하는 숫자가 아니라, 작은 분류모델과 LLM baseline을 비교할 최소 프로젝트 목표입니다.
수량보다 클래스 균형, 표현 다양성, 독립 평가셋, 교차 검수 품질이 중요합니다.

## 금지사항

- 실명, 외국인등록번호, 여권번호, 계좌번호, 전화번호 입력
- 기관·기업 인터뷰 내용을 허락 없이 원문 그대로 저장
- 합성 문장을 실제 기업 데이터로 표기
- 평가 문장을 학습셋이나 Few-shot 예시에 재사용
- 공공 민원 Intent를 FOWOCO Intent 정답으로 그대로 치환
