# FOWOCO Knowledge

FOWOCO Agent가 공통으로 참조하는 **버전형 업무 지식 패키지**입니다.
Intent·Domain·필수정보·Workflow·공식 출처·Guardrail과 평가 데이터를 한곳에서 관리합니다.

이 패키지는 LLM 자체가 아닙니다. Agent가 매 요청마다 같은 업무 기준을 사용하도록
Context를 제공하고, 서로 맞지 않는 지식 변경을 CI에서 차단하는 역할을 합니다.

## MVP 범위

| 지원 업무 | 대표 Workflow |
| --- | --- |
| 근로자 등록 | 문서 OCR 결과를 등록 초안으로 변환 후 HR 승인 |
| 체류·계약 만료 | 내부 알림일에 업무 생성, 필요자료 확인, 수동 기관 제출 안내 |
| 서류 요청 | 대상·서류·기한·제출처 점검 후 근로자 안내와 제출 추적 |
| 급여 설명 | 전월·당월 명세 차이를 계산하고 설명 초안 생성 |
| 업무·일정 안내 | 시간·장소·대상·행동을 명확히 한 다국어 안내 |
| 고용변동 | 사건정보를 구조화하고 공식 신고 준비 업무 생성 |

기관 자동 제출, 법적 최종판단, 노무위반 확률예측은 포함하지 않습니다.

## 구조

```text
fowoco-knowledge/
├── knowledge/        # Agent Context Pack 원본
├── data/             # Seed와 독립 평가 데이터
├── schemas/          # 입력·Workflow·라벨 데이터 계약
├── src/              # 로더, 검증기, CLI
├── tests/            # 교차참조·동작 테스트
├── examples/         # 실행 가능한 요청 예시
└── docs/             # 데이터·Agent 연동·출처 정책
```

## 설치와 검증

저장소 루트에서 실행합니다.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e "./fowoco-knowledge[dev]"
.venv/bin/python -m fowoco_knowledge validate
.venv/bin/python -m pytest fowoco-knowledge/tests
```

## CLI 사용

```bash
# 지원 Workflow 목록
.venv/bin/python -m fowoco_knowledge list-workflows

# 데이터 분포·누수·개인정보·준비 상태 확인
.venv/bin/python -m fowoco_knowledge data-report

# Agent에 전달할 Context 묶음 확인
.venv/bin/python -m fowoco_knowledge compile-context WF-STY-001

# 분류·Slot Filling 결과가 Workflow를 실행할 수 있는지 확인
.venv/bin/python -m fowoco_knowledge check-request \
  fowoco-knowledge/examples/ambiguous_document_request.json

# 공식 원본 검증 후 제조업 Knowledge 스냅샷 재생성
.venv/bin/python -m fowoco_knowledge sync-official-data

# 신청서별 필요서류와 제조업 세부업종 조회
.venv/bin/python -m fowoco_knowledge \
  list-required-documents "외국인 고용변동 등 신고"
.venv/bin/python -m fowoco_knowledge search-industries "금속가공제품"

# 기존 제안 라벨을 숨긴 독립 검수 파일 생성
.venv/bin/python -m fowoco_knowledge \
  build-review-queue REV-A reviewer-a.csv

# 독립 검수 결과 비교와 불일치 큐 생성
.venv/bin/python -m fowoco_knowledge compare-reviews \
  reviewer-a.csv reviewer-b.csv --output disagreements.csv
```

`check-request`는 자연어 모델을 대신하지 않습니다. 모델이 출력한 Workflow와 Slot이
업무를 시작하기에 충분한지 규칙으로 검증합니다.

## Agent 연동 위치

```text
자연어/PDF/Excel
  -> Intent·Domain·Slot 추론
  -> 이 패키지로 Workflow·필수정보·공식출처 조회
  -> 누락·모호성 검증
  -> HR 업무카드와 안내문 초안 생성
  -> HR 승인
  -> 근로자 응답과 후속 티켓
```

## 데이터 상태

- `gold_seed.csv`: 프롬프트·분기 개발용 초기 Seed이며 모델 학습 완료 데이터가 아님
- `golden_cases.jsonl`: 코드와 모델 평가에만 사용하는 독립 사례
- `dataset_manifest.yaml`: 대표 모델, 데이터 역할, 평가 잠금, 증강 정책의 단일 기준
- 공개데이터: 절차·용어·분포 보조자료이며 FOWOCO Intent의 정답 라벨로 간주하지 않음
- 실제 운영 로그: 개인정보를 제거하고 별도 승인된 경우에만 Active Learning 후보로 사용

세부 기준은 [`docs/DATA_GUIDE.md`](docs/DATA_GUIDE.md), 실제 검수 순서는
[`docs/DATA_OPERATIONS.md`](docs/DATA_OPERATIONS.md)를 확인합니다.
Intent·Domain의 경계 사례는 [`docs/LABELING_GUIDE_V1.md`](docs/LABELING_GUIDE_V1.md)를
확인합니다.

공식 데이터 변환은 [`docs/OFFICIAL_DATA_PIPELINE.md`](docs/OFFICIAL_DATA_PIPELINE.md),
신고·연장 기능의 범위는 [`docs/E9_REPORTING_WORKFLOWS.md`](docs/E9_REPORTING_WORKFLOWS.md)를
확인합니다.
