# 현실적인 모델링 계획

## 1. Intent·Domain 다중분류

### 입력과 출력

- 입력: HR 자연어 + 입력 모드 + 선택된 화면 컨텍스트
- 출력: 하나 이상의 Intent, Domain, 후보 Workflow, confidence
- 복합 요청: Multi-label로 평가하고 후보 업무카드로 분리

### 비교 순서

1. 규칙/키워드 baseline
2. TF-IDF + Linear SVM 또는 Logistic Regression
3. 한국어 Encoder 모델(KLUE-RoBERTa·KoELECTRA 계열) 미세조정
4. 로컬 LLM Structured Output zero/few-shot

### 지표

- 단일 요청: Macro-F1, 클래스별 Recall
- 복합 요청: Micro-F1, Exact Match Ratio
- 운영 안전성: `OUT_OF_SCOPE` Recall, 낮은 확신도 검토 전환율
- 모델 선택: 정확도뿐 아니라 지연시간·메모리·호출비용 함께 비교

## 2. Slot Filling

초기에는 LLM의 JSON Structured Output과 필수 Slot 규칙을 사용합니다.
날짜·서류명·장소·금액 라벨이 충분히 쌓인 뒤 NER/Token Classification과 비교합니다.

| 단계 | 데이터 | 평가 |
| --- | --- | --- |
| MVP | 팀 Gold 문장 + Workflow Slot 정의 | Field-level Precision·Recall·F1 |
| 보조학습 | AIHub 시간표현, KLUE NER | 날짜·일반 개체 인식 초기화 |
| 도메인 고도화 | HR 수정 로그의 서류명·급여항목 Span | Slot별 F1, 날짜 정규화 정확도 |

공개 NER의 사람·장소 라벨만으로 여권 사본·급여항목 같은 FOWOCO Slot을 해결할 수 없습니다.

## 3. 근로자 응답 분류

버튼 응답은 모델이 아니라 코드로 처리합니다.
자유질문이 들어온 경우에만 다음 유형을 분류합니다.

- `QUESTION`
- `NOT_UNDERSTOOD`
- `IN_PROGRESS`
- `SUBMITTED`
- `CANNOT_COMPLETE`
- `SENSITIVE_ISSUE`

초기에는 LLM 분류를 사용하고, 익명·검수 로그가 약 200~400건 쌓이면 작은 분류모델과 비교합니다.
핵심 지표는 전체 Accuracy보다 `CANNOT_COMPLETE`와 `SENSITIVE_ISSUE` Recall입니다.

## 4. 별도 모델을 만들지 않는 영역

| 영역 | 구현 |
| --- | --- |
| D-day와 내부 업무일 | 날짜 규칙 + 공휴일 API |
| 필수서류 | Workflow Catalog + 공식자료 검수 |
| 급여 차이 계산 | Python/SQL 계산식 |
| OCR | 상용 또는 검증된 OCR API 사용 |
| 번역 | 상용 API 또는 다국어 LLM + 핵심값 검증 |
| 법령 근거 | 버전형 검색·출처 표시, 전문가 확인 |

모델을 만드는 것보다 정답이 정해진 영역을 정확한 코드로 처리하는 편이 서비스 신뢰도에 유리합니다.

## 5. Active Learning

1. 모델 confidence가 낮거나 HR이 수정한 사례를 후보 큐에 저장
2. 개인정보 제거
3. 두 명이 Intent·Slot을 교차 검수
4. 합의 사례만 다음 학습 버전에 포함
5. 이전 독립 평가셋으로 회귀 테스트

이는 운영 피드백으로 데이터를 효율적으로 고르는 방식이며, 강화학습과 동일하지 않습니다.
