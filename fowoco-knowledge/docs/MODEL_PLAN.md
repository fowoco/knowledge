# Intent 모델링 계획

- 현재 단계: A.X 기반 MVP baseline 준비
- 데이터 규칙: Intent 라벨 규칙 v1.1
- 데이터 상태: A/B consensus 대기 중인 provisional Train/Validation 후보
- 모델 코드 위치: `fowoco/ai`

이 문서는 knowledge 저장소가 제공할 데이터·출력 계약·평가 기준을 정의한다.
모델 호출, 프롬프트, 학습, 실험 추적 코드는 AI 저장소에서 관리한다.

## 1. MVP 모델 책임

입력은 HR 담당자의 원문 `hr_input` 하나이며 출력은 `Intent + evidence`로 제한한다.

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

정식 출력 계약은
[`schemas/intent-model-output.schema.json`](../schemas/intent-model-output.schema.json)이다.

모델이 담당하지 않는 항목:

- Domain, Workflow, Slot 결정
- `request_id`, `status`, 모델명, 생성 시각 envelope
- confidence를 이용한 최종 승인 또는 자동 실행
- 외부기관 신고·접수·제출
- 법률·체류·급여의 최종 판단

## 2. 데이터 단계

1. Intent 규칙 v1.1 고정
2. Reviewer A/B 독립 검수와 consensus 생성
3. consensus를 반영한 원본 1,340건의 version·SHA-256 고정
4. 그룹 기반 Train 80% / Validation 20% 분할
5. 독립 Gold Test 240건 수제 작성·이중 검수·잠금
6. Smoke Test와 Gold Test를 분리해 운영

현재 committed split은 4단계를 미리 검증하기 위한 provisional 산출물이다. source
SHA-256이나 consensus가 바뀌면 생성기를 다시 실행하고 최종 잠금 전 성능 주장에
사용하지 않는다.

## 3. 모델 비교 순서

1. A.X Structured Output zero-shot
2. A.X prompt·few-shot baseline
3. 오류 유형별 prompt 및 데이터 개선
4. 비용·지연시간·배포 제약이 확인된 경우에만 작은 Encoder 모델 비교

BERT 계열 다중분류 모델은 Intent를 예측할 수 있지만 exact evidence를 자동으로
생성하지 않는다. 동일한 출력 계약을 사용하려면 별도의 span/token classification
구조 또는 evidence 추출 단계가 필요하다. 따라서 BERT 증류는 MVP baseline 이후
별도 설계한다.

## 4. 평가

구조적 Gate는 100%를 요구한다.

- JSON Schema 유효성
- evidence exact substring
- Multi-Intent 원문 순서
- `OUT_OF_SCOPE` 단독성

모델 후보 비교에는 Intent Exact Match, Macro/Micro F1, Intent별 Recall과 오류
유형을 함께 사용한다. 초기 내부 목표는 baseline 비교를 위한 provisional 값이며
서비스 성능 보장을 뜻하지 않는다.

정식 기준은
[`knowledge/intent_evaluation_policy.yaml`](../knowledge/intent_evaluation_policy.yaml)을
따른다.

## 5. 운영 경계

confidence는 MVP 모델 출력 계약에 넣지 않는다. 형식 오류, evidence 오류, 알 수 없는
Intent, `OUT_OF_SCOPE` 혼합은 규칙 검증으로 차단한다. 체류·고용변동과 외부 실행은
confidence와 무관하게 HR 승인과 Guardrail 검사를 적용한다.

운영 로그를 학습에 사용할 때는 개인정보를 제거하고 두 명의 검수자가 합의한 사례만
새 버전에 포함한다. 이전 locked Gold Test로 회귀를 확인한다.
