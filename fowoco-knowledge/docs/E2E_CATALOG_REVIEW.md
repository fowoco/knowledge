# 실행 Catalog E2E 검수와 모델팀 인계

## 목적

`data/evaluation/e2e_catalog_cases.jsonl`은 이름 변형, 복합 요청, Intent 경계,
`OUT_OF_SCOPE`, 외부 실행 차단과 베트남어 안내를 한 요청 흐름에서 검증하기 위한
대표 11건이다. 현재 상태는 **Gold 후보**이며 독립 검수와 합의 전에는 Gold 또는
모델 성능 근거로 표현하지 않는다.

## Knowledge가 제공하는 계약

각 사례에는 다음 기대값이 있다.

- HR 입력과 합성 근로자 디렉터리
- Intent와 Workflow
- 이름·별칭 기반 대상 탐색 결과와 확인 필요 여부
- Workflow Slot 값과 후속 행동
- 결정적으로 기대되는 BERT→A.X routing rule category
- 외부기관 제출·근로자 메시지 발송·자동 완료 차단
- 쉬운 한국어 및 베트남어 안내의 핵심 보존값

`expected_routing_triggers`가 비어 있는 사례는 A.X 전환을 금지한다는 뜻이 아니다.
텍스트 규칙만으로 미리 확정할 category가 없다는 뜻이며, 실제 BERT margin과 활성
label 수에 따라 `Low_Margin` 또는 `OOD_Label_Count`가 기록될 수 있다.

## 모델·서비스 팀이 측정할 항목

동일한 11건을 BERT 단독과 BERT→A.X 보조 경로에 각각 실행하고 다음을 비교한다.

| 항목 | 기록 기준 |
| --- | --- |
| Intent 정확도 | Multi-label Exact Match와 Intent별 오류 |
| evidence | 원문 exact substring 일치 여부. BERT가 제공하지 않으면 미지원으로 분리 |
| 지연시간 | 경로별 p50·p95와 사례별 `latency_ms` |
| fallback 비율 | A.X로 실제 전환된 건수 / 전체 건수 |
| routing 사유 | `selected_model`, `routing_category`, `routing_reason`, `degraded` |
| 안전성 | 오분류가 자동 제출·자동 발송·자동 완료로 이어진 건수 |

confidence 숫자만 전달하지 않는다. 어떤 조건으로 A.X가 선택됐는지와 A.X 호출 실패로
BERT 결과를 사용했는지를 응답 metadata와 평가 리포트에 함께 남긴다.

## Reviewer A/B 독립 검수

1. 같은 원본 JSONL과 `data/review/e2e_catalog_review_template.csv` 사본을 A와 B에게
   각각 전달한다.
2. 두 검수자는 서로의 결과를 보지 않고 다음 네 항목을 판정한다.
   - `subject_lookup_decision`: 이름 변형이 한 명을 안전하게 가리키는지
   - `intent_workflow_decision`: Intent와 Workflow 경계가 맞는지
   - `notice_core_value_decision`: 대상자·날짜·시간·서류명·제출처가 보존됐는지
   - `guardrail_decision`: 오분류가 발생해도 자동 실행이 차단되는지
3. 판정값은 `AGREE`, `CHANGE`, `NOT_APPLICABLE` 중 하나를 사용한다.
4. 변경 제안은 `proposed_changes_json`, 이유는 `review_note`에 기록한다.
5. A/B가 다른 행만 합의하고 변경한 뒤 manifest version과 SHA-256을 갱신한다.
6. 고용변동·체류·기관 실행 사례는 팀 합의 후에도 전문가 검수를 거친다.

## Gold 승격 조건

- 11건 모두 Reviewer A/B 판정 완료
- 불일치 합의 완료 및 변경 사유 보존
- 베트남어 사례의 핵심값 보존 확인
- high·critical 및 기관 실행 사례의 전문가 확인
- Schema·내부 키 노출·개인정보·SHA-256 검사 통과

승격 전 manifest 상태는 `pending_independent_review`로 유지한다.
