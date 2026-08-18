# FOWOCO HR Intent models

## 목적

HR 담당자의 한국어 발화에서 FOWOCO의 지원 Intent를 분류한다. KLUE-RoBERTa를 빠른
기본 분류기로 사용하고, 경계 규칙 또는 낮은 margin에 해당하는 요청만 A.X QLoRA
adapter로 보낸다.

## 산출물

| ID | 배포 저장소 | 역할 |
| --- | --- | --- |
| `KLUE_ROBERTA_INTENT` | `fowoco/klue-roberta-base-intent-classifier` | 기본 분류 |
| `AX_INTENT_QLORA` | `fowoco/ax-intent-qlora` | 복잡·경계 요청 보조 |

두 저장소는 비공개다. 파일 무결성은 같은 디렉터리의 `artifact-manifest.yaml`을 기준으로
검증하고, 운영 배포에서는 HF commit SHA를 별도로 고정한다.

## 데이터 계보

- 학습·내부 Validation snapshot: Intent 데이터 `1.2.0`
- snapshot SHA-256: `447174a992e31bd44ec8abe658dc4082d3197bf284e0cc08b7ac5e3e6341a237`
- 현재 Knowledge 데이터: `1.2.1`
- 현재 가중치의 `1.2.1` 재학습 여부: 아니오
- 개인정보 원문 포함 여부: 아니오

## 내부 Validation 결과

| 경로 | 내부 Validation 268건 |
| --- | ---: |
| KLUE-RoBERTa | 95.5% |
| A.X-4.0-Light QLoRA | 92.2% |
| 조건부 Cascade | 93.2% |

동일 Validation으로 모델 선택과 routing 규칙을 조정했으므로 위 수치는 독립 Test 또는
운영 성능이 아니다.

## 사용 범위와 제한

- 허용: Intent 후보와 evidence 생성, 위험 요청을 보조 모델로 routing
- 금지: 법률·체류·계약 결론, Workflow 자동 승인, 근로자 안내 자동 발송, 외부기관 제출
- BERT가 evidence를 제공하지 못할 수 있으므로 evidence는 nullable 계약을 따른다.
- A.X가 분류 확률을 제공하지 않으면 confidence를 만들지 않고 `UNAVAILABLE`로 표현한다.
- 모델 실패 시 fallback 사용 여부와 실제 모델 버전을 응답 메타데이터에 명시한다.

## 재현

환경 구성과 실행은 상위 `README.md`, 보관·배포 절차는
`../../docs/MODEL_ARTIFACT_POLICY.md`를 따른다. `HF_TOKEN`은 환경변수 또는 Secret으로만
주입한다.
