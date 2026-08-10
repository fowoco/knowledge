# FOWOCO Knowledge

FOWOCO는 E-9 외국인근로자를 고용한 사업장의 HR·총무 업무를 구조화하고,
담당자가 놓치기 쉬운 다음 행동을 업무카드로 관리하는 AI 업무보조 서비스입니다.

이 저장소는 FOWOCO Agent가 사용하는 **업무 지식, 공식자료 정규화 데이터, Intent
라벨, 데이터 계약과 검증 기준**의 기준 저장소입니다. 외부기관 제출이나 법적 판단을
자동화하지 않으며, 민감 업무는 HR 담당자의 승인 후 진행합니다.

> [!IMPORTANT]
> ## 🤗 [FOWOCO Hugging Face](https://huggingface.co/fowoco)
>
> 학습된 BERT 모델과 A.X adapter의 배포 기준 위치입니다. 저장소 접근 권한에 따라
> 일부 모델은 비공개일 수 있습니다. GitHub에는 재현에 필요한 데이터 기준·코드와
> 프로젝트 제출용 Git LFS 스냅샷을 관리합니다.

## 한눈에 보는 결과

| 영역 | 결과 | 검증 근거 |
| --- | --- | --- |
| 업무 지식 | 7개 Intent, 8개 MVP Workflow, 필수 Slot·서류·공식 출처·Guardrail 구조화 | [`knowledge/`](fowoco-knowledge/knowledge) |
| Intent 데이터 | 비식별 HR 발화문 1,340건, 규칙 v1.1 경계 재검수 후 124건 라벨 정정 | [`manifest.yaml`](fowoco-knowledge/data/intent/manifest.yaml) |
| 데이터 분할 | Train 1,072건 / Validation 268건, 정규화 템플릿 누수 0건 | [`splits/manifest.yaml`](fowoco-knowledge/data/intent/splits/manifest.yaml) |
| 공식자료 | 필요서류 187건 중 제조업·전업종 122건, 허용 세부업종 847건 중 제조업 569건 정규화 | [`processed/manifest.yaml`](fowoco-knowledge/data/processed/manifest.yaml) |
| 모델 비교 | KLUE-RoBERTa, A.X-4.0-Light QLoRA와 조건부 Cascade 비교 | [`hr-intent-service/`](fowoco-knowledge/hr-intent-service) |
| 품질 자동화 | Schema·SHA-256·중복·누락·개인정보 패턴·split 누수 검사와 CI 구축 | [`validation.py`](fowoco-knowledge/src/fowoco_knowledge/validation.py) |

## 해결 흐름

```text
HR 담당자 발화
  -> Intent + evidence 분류
  -> Workflow·필수 Slot·공식 출처 조회
  -> 누락 정보와 금지 실행 검증
  -> 업무카드·근로자 안내 초안 생성
  -> HR 담당자 검토와 승인
```

Intent 모델의 책임은 발화에서 `Intent + evidence`를 찾는 것까지입니다. Workflow
선택, 체류·계약·급여 관련 판단, 기관 제출과 업무 완료 처리는 Knowledge 규칙과 HR
담당자의 책임으로 분리했습니다.

## 데이터 설계와 검수

### 라벨을 만드는 규칙부터 관리

단순 문장 분류 데이터가 아니라, 사람이 같은 기준으로 검수하고 모델 출력까지 검사할
수 있도록 라벨 계약을 먼저 정의했습니다.

- `DOCUMENT_REQUEST`는 서류 요청·수령·미제출 추적이 명시된 경우에만 부여
- Multi-Intent는 근거 문구가 원문에 등장한 순서대로 기록
- `evidence`는 원문에서 한 글자도 바꾸지 않은 연속 부분 문자열
- `OUT_OF_SCOPE`는 다른 Intent와 함께 사용할 수 없고 evidence는 `null`
- 외부기관 접수·자동 실행 표현은 Intent가 아니라 Guardrail에서 차단

검수 전 원본은
[`hr_intent_dataset.jsonl`](fowoco-knowledge/data/intent/hr_intent_dataset.jsonl), 현재
학습·검증 기준은
[`hr_intent_dataset_final.jsonl`](fowoco-knowledge/data/intent/hr_intent_dataset_final.jsonl)에
분리해 보존했습니다. 두 파일은 ID와 입력 문장을 유지하면서 124건의 Intent/evidence
변경 이력을 추적할 수 있습니다.

### 재현 가능한 Train/Validation 분할

근로자 ID만 다른 유사 문장이 Train과 Validation에 나뉘어 들어가는 누수를 막기 위해
정규화된 문장 템플릿을 하나의 그룹으로 묶었습니다.

- 고정 seed: `20260727`
- 정규화 template group: 1,335개
- 중복 template group: 5개
- Train/Validation ID 교집합: 0개
- 전체 1,340개 ID 누락: 0개
- source와 split 파일의 SHA-256을 manifest에 고정

Validation은 모델 선택과 threshold 조정에 사용한 개발용 데이터입니다. 독립 Gold
Test가 아니므로 아래 수치를 최종 성능이나 운영 성능으로 주장하지 않습니다.

## 모델링 판단

| 모델 | 역할 | 내부 Validation 268건 |
| --- | --- | ---: |
| KLUE-RoBERTa Full Fine-tuning | 빠른 기본 분류기 | 95.5% |
| A.X-4.0-Light QLoRA | 복잡·경계 요청 보조 | 92.2% |
| 조건부 Cascade | BERT 결과를 검사해 일부 요청만 A.X로 전달 | 93.2% |

단일 Validation 정확도는 BERT가 가장 높았습니다. 따라서 모든 요청을 큰 모델로 처리하지
않고, BERT를 기본 경로로 선택했습니다. A.X는 다음 조건처럼 분류 위험이 높은 요청에만
사용하는 보조 경로로 설계했습니다.

- 활성 Intent가 3개 이상인 복합 요청
- 완료·상태보고, 급여계좌, 서류 확보 등 경계 패턴 포함
- 선택·비선택 Intent 사이의 margin이 `0.76` 미만

Cascade의 목적은 단순 정확도 상승이 아니라 **응답속도와 자원 사용을 유지하면서 복잡한
요청을 별도 경로로 관찰·검토할 수 있게 하는 것**입니다. 현재 가중치는 데이터 구조 오류
3건을 수정하기 전 version 1.2.0 snapshot 기준이며, 데이터와 가중치의 SHA-256 차이를
manifest에 명시했습니다.

## 공식자료를 Agent Knowledge로 만드는 과정

```text
정부·공공기관 원본
  -> 출처 URL·수집일·버전·SHA-256 고정
  -> 제조업과 전업종 범위 정규화
  -> Schema·건수·중복·필수값 검사
  -> Workflow·필수서류·제출 경로와 연결
  -> Agent Context Pack으로 제공
```

공개 CSV의 `샘플서식제공여부`를 실제 서식 보유로 해석하지 않습니다. 공식 빈 서식,
작성 안내, 사용자가 보유해야 하는 증빙, 출처 미확인 항목을 구분하며 최신성이나 법적
필수 여부를 Agent가 임의로 확정하지 않도록 했습니다.

## 자동 검증과 재현

Python 3.11 이상 환경에서 다음 명령으로 동일한 검증을 실행할 수 있습니다.

```bash
python3.11 -m venv .venv
make install
make check
```

`make check`에서 확인하는 항목은 다음과 같습니다.

- Ruff format·lint
- Workflow와 Intent JSON Schema
- Knowledge 파일 간 ID·출처·체크리스트 교차참조
- 데이터 record count와 SHA-256
- Intent ID·입력 중복, evidence exact substring과 순서
- Train/Validation 중복·누락과 template leakage
- 외국인등록번호·여권번호·전화번호 형태의 개인정보 패턴
- 전체 자동화 테스트 18개

## 저장소 구성

```text
.
├── fowoco-knowledge/
│   ├── knowledge/          # Intent·Workflow·Slot·공식 출처·Guardrail
│   ├── data/               # Intent·Seed·평가·공공 정규화 데이터
│   ├── schemas/            # 데이터와 Agent 출력 JSON Schema
│   ├── src/                # Knowledge 조회·검증 CLI
│   ├── tests/              # Schema·해시·교차참조·분할 테스트
│   ├── docs/               # 라벨·출처·검수·연동 기준
│   └── hr-intent-service/  # BERT + A.X 모델 서빙 참고 구현
├── Makefile
└── .github/workflows/      # PR 규칙과 Knowledge CI
```

`hr-intent-service/`는 프로젝트 결과 재현과 인계를 위한 참고 구현입니다. 모델 배포의
기준 위치는 [FOWOCO Hugging Face](https://huggingface.co/fowoco)이며, 운영 서빙 코드의
장기 소유권은 `fowoco/ai`에 둡니다.

## 안전 원칙과 현재 한계

- 모델 출력만으로 법률·체류·계약·급여·신고 결론을 확정하지 않습니다.
- 외부기관 제출, 계약 확정, 급여 지급과 근로자 안내 발송을 자동 실행하지 않습니다.
- 실제 외국인등록번호, 여권번호, 전화번호, 계좌번호를 저장하지 않습니다.
- Validation 268건은 독립 Test가 아니며 별도의 잠긴 Gold Test가 필요합니다.
- 현재 모델 가중치는 Intent 데이터 version 1.2.1로 재학습되지 않았습니다.
- 공식자료의 최신 버전과 적용 여부는 실제 업무 처리 전 담당자가 다시 확인해야 합니다.

## 주요 문서

- [데이터 사용 안내](fowoco-knowledge/data/README.md)
- [Intent 라벨 기준](fowoco-knowledge/docs/INTENT_DATA.md)
- [Agent 연동 계약](fowoco-knowledge/docs/AGENT_INTEGRATION.md)
- [공식 데이터 파이프라인](fowoco-knowledge/docs/OFFICIAL_DATA_PIPELINE.md)
- [E-9 신고·연장 Workflow](fowoco-knowledge/docs/E9_REPORTING_WORKFLOWS.md)
- [모델 서빙 실행 방법](fowoco-knowledge/hr-intent-service/README.md)
