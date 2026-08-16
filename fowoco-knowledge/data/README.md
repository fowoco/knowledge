# 데이터 사용 안내

이 디렉터리는 FOWOCO Knowledge의 데이터 원본, 정규화 결과, 검수 자료와 평가 사례를
관리합니다. 실제 근로자·기업 개인정보는 저장하지 않습니다.

## Intent 데이터

| 파일 | 건수 | 용도 | 사용 기준 |
| --- | ---: | --- | --- |
| [`intent/hr_intent_dataset_final.jsonl`](intent/hr_intent_dataset_final.jsonl) | 1,340 | 최종 검수된 학습·검증 원본 | **현재 기준 파일** |
| [`intent/hr_intent_dataset.jsonl`](intent/hr_intent_dataset.jsonl) | 1,340 | 검수 전 라벨 원본 | 변경 이력 비교만 허용 |
| [`intent/splits/train_ids.txt`](intent/splits/train_ids.txt) | 1,072 | Train ID | 최종 JSONL에서 ID로 선택 |
| [`intent/splits/validation_ids.txt`](intent/splits/validation_ids.txt) | 268 | Validation ID | 모델 개발·비교용 |
| [`intent/manifest.yaml`](intent/manifest.yaml) | - | 최종 데이터 버전·해시·제한 | 데이터 사용 전 확인 |
| [`intent/splits/manifest.yaml`](intent/splits/manifest.yaml) | - | 분할 방식·해시·분포 | split 사용 전 확인 |

Train과 Validation 데이터는 별도 복사본을 만들지 않습니다. 최종 JSONL을 읽은 뒤 ID
파일로 레코드를 선택합니다. 두 ID 파일은 겹치지 않으며 전체 1,340개 ID를 한 번씩
포함합니다.

Validation 268건은 모델 개발용입니다. 학습 prompt, threshold와 routing 규칙을 이
Validation 결과에 맞춰 조정했으므로 독립 Test 성능이나 운영 성능으로 표현하지 않습니다.

## 나머지 디렉터리

| 경로 | 내용 |
| --- | --- |
| [`external/`](external) | 외부 공식자료 출처, 버전, SHA-256 |
| [`curated/`](curated) | 팀이 수동 정리한 원본성 자료 |
| [`processed/`](processed) | 검증 가능한 정규화 결과와 manifest |
| [`seed/`](seed) | Workflow·분기 개발용 초기 Seed |
| [`evaluation/`](evaluation) | Knowledge/Agent 동작을 확인하는 독립 사례 |
| [`review/`](review) | 라벨링·전문가 검수 템플릿 |

`evaluation/golden_cases.jsonl`은 Agent Workflow 검증 사례이며, Intent 모델의 잠긴
Gold Test 240건과 동일하지 않습니다. 현재 독립 Intent Gold Test는 저장소에 없습니다.

`evaluation/e2e_catalog_cases.jsonl`은 이름 변형·복합 요청·Intent 경계·외부 실행
차단·베트남어 안내를 함께 확인하는 대표 E2E 11건입니다. 현재는 독립 검수 전
**Gold 후보**이며, 검수 절차와 모델·서비스 팀 측정 항목은
[`../docs/E2E_CATALOG_REVIEW.md`](../docs/E2E_CATALOG_REVIEW.md)를 따릅니다.

## 변경 시 필수 확인

1. 원본과 최종본의 목적을 섞지 않습니다.
2. 데이터가 바뀌면 manifest의 version, record count, SHA-256을 함께 갱신합니다.
3. split ID의 중복·누락과 source ID 존재 여부를 확인합니다.
4. JSON Schema, evidence exact substring, Intent 순서와 `OUT_OF_SCOPE` 단독성을 검사합니다.
5. 외국인등록번호, 여권번호, 전화번호, 계좌번호 패턴이 없는지 확인합니다.
6. 독립 Test를 Train·Validation 또는 prompt 예시로 재사용하지 않습니다.

저장소 루트의 `make check`가 위 구조 검증의 기본 진입점입니다.
