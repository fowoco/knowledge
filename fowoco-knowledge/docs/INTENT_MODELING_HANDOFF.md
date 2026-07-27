# Intent 모델링 Knowledge → AI 인계 계약

## 1. 인계 범위

knowledge 저장소는 다음 자료를 제공한다.

| 항목 | 경로 | 상태 |
| --- | --- | --- |
| 라벨 규칙 | `docs/INTENT_DATA.md` | v1.1 |
| 모델 계약 | `knowledge/intent_model_contract.yaml` | provisional |
| 모델 출력 Schema | `schemas/intent-model-output.schema.json` | provisional |
| 원본 후보 | `data/intent/hr_intent_dataset.jsonl` | A/B 재검수 필요 |
| 분할 manifest | `data/intent/splits/provisional-v1/manifest.yaml` | consensus 대기 |
| 평가 정책 | `knowledge/intent_evaluation_policy.yaml` | baseline 전 임시 목표 |
| Gold 계획 | `docs/INTENT_GOLD_TEST_PLAN.md` | 작성 전 |
| 임시 baseline 가이드 | `docs/INTENT_PROVISIONAL_BASELINE.md` | 수정 전 라벨 실험 |
| A.X 테스트 가이드 | `docs/INTENT_AX_TESTING.md` | zero-shot smoke 준비 |

AI 저장소는 프롬프트, 모델 어댑터, 추론·평가 코드와 실험 결과를 관리한다.

## 2. 입력과 출력

모델 입력:

```json
{
  "hr_input": "재계약 준비하면서 서명본도 받아서 첨부해줘"
}
```

모델 출력:

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

`request_id`, 입력 원문, 검증 상태, 모델명과 시각은 서버 envelope에서 추가한다.
학습 정답이나 모델 출력에 넣지 않는다.

## 3. split 소비 방식

Train/Validation 파일은 원본 JSONL을 복제하지 않고 ID만 제공한다. AI 저장소는
manifest의 다음 절차로 데이터를 읽는다.

1. 원본 JSONL의 SHA-256을 split manifest의 `source.sha256`과 비교한다.
2. `train_ids.txt`와 `validation_ids.txt`를 읽는다.
3. 원본 레코드를 `id`로 선택한다.
4. ID 누락·중복·교집합이 있으면 실험을 중단한다.
5. manifest가 `locked`가 아니면 결과를 provisional로 표시한다.

현재 분할:

- Train 1,072건
- Validation 268건
- Gold Test 미포함
- Reviewer A 변경 제안은 원본 JSONL에 아직 적용하지 않음

분할 재생성:

```bash
python -m fowoco_knowledge build-intent-splits
```

## 4. baseline 실험 순서

1. A.X zero-shot Structured Output
2. 동일 Validation에서 prompt v1 비교
3. Train에서만 few-shot 예시 선택
4. 오류 유형별 분석
5. prompt와 Knowledge 규칙·데이터 변경을 분리해 기록

Validation을 보고 prompt를 수정할 수 있지만 Gold Test는 최종 후보 비교 전까지
열람하지 않는다.

## 5. 필수 검증

모델 출력마다 다음 순서로 검증한다.

1. JSON 파싱
2. `intent-model-output.schema.json`
3. 중복 Intent 금지
4. evidence exact substring
5. evidence 원문 순서
6. `OUT_OF_SCOPE` 단독성

구조 검증 실패는 낮은 confidence로 대체하지 않고 실패 유형으로 기록한다.

## 6. 변경 대응

A/B consensus 결과가 현재 원본과 다르면 다음을 수행한다.

1. 원본 JSONL과 `data/intent/manifest.yaml` version·SHA-256 갱신
2. split 생성기 재실행
3. Train/Validation ID와 분포 diff 검토
4. AI 실험에서 새 데이터 version으로 다시 실행
5. 이전 version 결과와 직접 혼합하지 않음
