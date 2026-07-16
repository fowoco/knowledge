# 데이터 담당 운영 기준

## 1. 이번 단계의 결정

FOWOCO의 대표 모델은 **HR 요청 Intent·Domain 다중라벨 분류 모델**로 고정합니다.

- 입력: `input_mode`, `hr_utterance`, `system_context`
- 정답: 하나 이상의 `intents`, `domains`
- 보조 정답: `workflow_ids`, Slot, 누락정보, 모호표현, 다음 행동
- 복합 요청: 한 문장을 반려하지 않고 Intent별 후보 업무카드로 분리
- Language Agent: 대표 학습모델이 아니라 검증된 업무정보를 안내문으로 바꾸는 생성 모듈

이 결정의 목적은 데이터 담당자와 모델 담당자가 서로 다른 정답을 만들지 않도록
학습 문제와 Agent 실행 문제를 분리하는 것입니다.

## 2. 현재 데이터의 정확한 상태

| 데이터 | 현재 용도 | 현재 상태 | 금지 사항 |
| --- | --- | --- | --- |
| `gold_seed.csv` | 라벨 기준·Agent 분기 개발 | 40건 모두 DRAFT | 바로 학습 데이터라고 표현하지 않음 |
| `golden_cases.jsonl` | 후보 모델 Smoke Test | 18건, checksum 잠금 | 학습·Few-shot·증강 원본으로 재사용 금지 |
| 공공 필요서류 122건 | Workflow 체크리스트 | 제조업 행 정규화 완료 | Intent 정답 라벨로 변환 금지 |
| 제조업 업종 569건 | 업종 검색·표준화 | 제조업 행 정규화 완료 | 발화문 학습 데이터라고 표현 금지 |

`dataset_manifest.yaml`이 대표 모델, 데이터 역할, 평가 잠금, 증강 정책의 단일 기준입니다.

## 3. 데이터 담당 작업 순서

### 단계 A. 독립 검수

두 검수자에게 서로 다른 코드와 파일을 배정합니다. 검수자는 기존 제안 라벨을 보지 않고
Intent·Domain·Workflow·Slot을 입력합니다.

```bash
python -m fowoco_knowledge build-review-queue REV-A reviewer-a.csv
python -m fowoco_knowledge build-review-queue REV-B reviewer-b.csv
```

검수 파일은 다음 규칙을 따릅니다.

1. 검수자는 서로의 파일을 열어보지 않음
2. `APPROVE`, `CORRECT`, `REJECT`, `EXPERT_REVIEW` 중 하나를 `decision`에 기록
3. 판단 근거를 `notes`에 한 문장 이상 기록
4. 실제 이름·전화번호·외국인등록번호를 추가하지 않음
5. 법령·신고·급여·체류 정답이 포함되면 `EXPERT_REVIEW` 선택 가능

### 단계 B. 합의와 Gold 승격

- Intent·Domain·Workflow가 일치하면 Slot 차이를 확인
- 불일치는 데이터 담당자가 근거와 함께 합의
- Intent·Domain은 민감도와 무관하게 두 팀원 합의 후 분류용 `GOLD_TEAM` 승격 가능
- `high`, `critical`의 Workflow·필수정보·조치안은 전문가 확인 전 정답으로 사용하지 않음
- 전문가 확인까지 끝난 전체 사례만 `GOLD_EXPERT`로 승격
- 수정·거절률이 10%를 넘은 Intent는 해당 유형 전체 재검수

두 검수 파일을 회수한 뒤 다음 명령으로 일치도와 합의 대상을 생성합니다.

```bash
python -m fowoco_knowledge compare-reviews \
  reviewer-a.csv reviewer-b.csv \
  --output disagreements.csv
```

출력에는 Intent·Domain·Workflow Exact Match, 라벨별 Cohen's Kappa의 Macro 평균,
미완료 행 수와 불일치 행이 포함됩니다. Kappa가 0.70 미만이면 문장을 늘리기 전에
라벨 가이드와 경계 사례를 먼저 수정합니다.

### 단계 C. 데이터 품질 확인

```bash
python -m fowoco_knowledge data-report
python -m fowoco_knowledge data-report --json
python -m fowoco_knowledge validate
```

`data-report`는 다음 항목을 자동 확인합니다.

- Intent·Domain·입력모드·출처·민감도 분포
- 문장 중복
- Seed와 평가셋 문장 누수
- 주민·외국인등록번호, 전화번호, 이메일 패턴
- Smoke Test, Gold V1, 분류 Baseline 준비 여부

## 4. 모델팀 전달 조건

| 전달 단계 | 데이터 조건 | 허용되는 실험 |
| --- | --- | --- |
| Smoke | 잠긴 평가 15건 이상, 누수·PII 0건 | 파이프라인 작동 여부와 후보 모델 오류 관찰 |
| Gold V1 | 합의된 60건 이상 | Few-shot 예시와 Agent 분기 비교 |
| Baseline | 총 600건 목표, Intent별 최소 80건 | TF-IDF, 한국어 Encoder, LLM 분류 성능 비교 |

18건 Smoke 결과로 최종 정확도를 주장하지 않습니다. 모델 계열을 빠르게 좁힌 뒤 Gold V1을
확보하고, 라벨 기준이 안정된 다음 학습용 데이터를 확장합니다.

## 5. 증강 정책

1. 실제 평가셋을 먼저 잠금
2. 원본 Gold 데이터만 Train·Validation·Test로 분리
3. 증강은 Train 분할에만 적용
4. 같은 원문에서 파생된 문장은 반드시 같은 분할에 배치
5. LLM 생성 문장은 `TEAM_SYNTHETIC`과 생성 모델·프롬프트 버전을 기록
6. 두 명 검수와 필요한 전문가 검수를 통과한 문장만 학습에 사용

이는 합성 문장이 평가셋으로 흘러 들어가 성능이 부풀려지는 것을 막기 위한 기준입니다.

### 문체 다양성 기준

현재 Seed 40건은 라벨 체계와 Agent 분기를 먼저 검증하기 위한 개발용 문장입니다. 다수 문장이
`해줘` 형태의 직접 명령문이므로 그대로 학습·최종평가 데이터로 사용하지 않습니다.

Gold V1 이후 문장을 확장할 때는 Intent별로 다음 표현을 고르게 포함합니다.

- 직접 명령: `확인해줘`, `안내해 주세요`
- 질문: `누가 이번 달에 만료되나요?`, `어떻게 처리해야 하나요?`
- 상황 진술: `어제부터 출근하지 않고 있어요`, `급여가 지난달보다 적습니다`
- 짧은 업무 메모: `7월 체류만료자 목록`, `여권 사본 미제출 확인`
- 간접 요청: `연장 준비가 필요합니다`, `근로자에게 설명 부탁드립니다`
- 실제 입력 변형: 띄어쓰기 오류, 구어체, 주어 생략, 상대시간, 복합 요청

동일한 원문의 표현만 바꾼 파생 문장은 `source_parent_id`로 묶고 같은 Train 분할에 배치합니다.
평가셋은 실제·인터뷰 파생 문장을 우선하며 `해줘` 같은 특정 종결 표현이 한 Intent의 지름길이
되지 않도록 분포를 점검합니다.

## 6. 데이터 담당자의 다음 완료 기준

- Seed 40건에 대한 독립 검수 2세트 회수
- 불일치표와 라벨 가이드 V1 작성
- Gold V1 60건 확보 계획 확정
- 고위험·신고·체류·급여 사례의 전문가 검수 목록 분리
- 모델팀에 `dataset_manifest.yaml`, Gold 파일, 잠긴 평가셋, 품질 리포트 전달
