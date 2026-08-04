# Intent 수정 전 라벨 Provisional Baseline

## 목적

이 baseline은 A/B consensus 전 원본 1,340건으로 모델링 파이프라인이 정상적으로
작동하는지 확인하는 하한선이다. 최종 모델 또는 Gold Test 성능을 주장하지 않는다.

## 데이터

- Source: `data/intent/hr_intent_dataset.jsonl`
- 상태: `recheck_required`
- Train: 1,072건
- Validation: 268건
- Split: `data/intent/splits/provisional-v1/manifest.yaml`
- Reviewer A 제안: 원본에 미반영
- Reviewer B·Consensus: 대기

Validation ID는 모델 학습과 threshold 산정에 사용하지 않는다.

## 모델

외부 라이브러리와 API 없이 실행되는 문자 n-gram 다중라벨 Naive Bayes다. 각
Intent를 one-vs-rest 방식으로 학습하고 Train 내부 점수만으로 임시 threshold를
정한다. evidence는 해당 Intent에 양의 가중치를 갖는 연속 토큰 구간을 선택한다.

이 모델은 데이터·평가 파이프라인 검증용이며 A.X, BERT 또는 Transformer 후보를
대체하지 않는다.

실제 A.X zero-shot 테스트는
[`INTENT_AX_TESTING.md`](INTENT_AX_TESTING.md)를 따른다.

## 저장소 경계

AI 저장소의 작업 충돌을 피하기 위해 현재는 knowledge 저장소의 `model` 브랜치에서
임시로 실행한다. 이 브랜치의 모델 학습·추론 코드는 knowledge `main` 병합 대상이
아니며, 실험 구조가 확인되면 `fowoco/ai` 저장소로 이전한다. knowledge 저장소에는
최종적으로 데이터 계약, split, 평가 정책과 검증 리포트만 남긴다.

## 실행

```bash
python -m fowoco_knowledge run-intent-provisional-baseline
```

생성 파일:

- `data/experiments/intent/provisional-char-ngram-nb-v1/report.yaml`
- `data/experiments/intent/provisional-char-ngram-nb-v1/predictions.jsonl`

Report에는 source·split checksum, 모델 설정, Intent 지표, evidence 일치율, 구조적
Gate, 오류 유형과 금지 주장을 기록한다. 생성 시각은 넣지 않아 같은 입력과 코드에서
동일한 결과를 재생성할 수 있다.

## 결과 해석

- `intent_exact_match`, `macro_f1`, `micro_f1`: 수정 전 라벨과의 일치 정도
- `evidence_gold_exact_match`: 기존 evidence와 완전히 같은 구간을 예측한 비율
- `structural_gate_rates`: JSON Schema, exact substring, 순서, OUT_OF_SCOPE 단독성
- `error_case_counts`: Intent 누락·추가와 evidence 과다 범위 등의 오류 건수

Validation은 개발 중 확인용이므로 모델 선택을 반복하면 Validation에도 과적합될 수
있다. 최종 비교는 별도로 잠근 Gold Test 240건이 확보된 뒤 수행한다.

## Consensus 반영 후

1. 원본 JSONL과 `data/intent/manifest.yaml` version·checksum을 갱신한다.
2. PR #33의 split 생성기를 같은 seed로 다시 실행한다.
3. 이 baseline을 다시 실행한다.
4. 수정 전·후 결과를 다른 데이터 version으로 보관하고 직접 혼합하지 않는다.
