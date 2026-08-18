# FOWOCO Knowledge Package

FOWOCO Agent가 공통으로 참조하는 버전형 업무 지식 패키지입니다. Intent·Workflow·필수
Slot·공식 출처·Guardrail을 조회하고, 데이터 계약과 교차참조가 맞는지 검증합니다.

이 패키지는 법적 판단이나 외부기관 제출을 수행하지 않습니다. 모델이 분류한 요청을
업무 지식과 연결하고 누락·모호성을 찾는 것이 핵심 책임입니다.

## 디렉터리

| 경로 | 내용 |
| --- | --- |
| [`knowledge/`](knowledge) | Agent Context Pack 원본 |
| [`data/`](data) | 최종 Intent 데이터, split ID, Seed·평가·공공 정규화 데이터 |
| [`schemas/`](schemas) | 입력·Workflow·Intent·분할 계약 |
| [`src/`](src) | 로더, 검증기, 조회 CLI |
| [`tests/`](tests) | Schema·SHA-256·교차참조·분할 테스트 |
| [`docs/`](docs) | 라벨링, 출처, 검수, Agent 연동 기준 |
| [`hr-intent-service/`](hr-intent-service) | BERT + A.X cascade 모델의 참고 서빙 구현 |

모델 가중치의 배포 기준 위치는 [FOWOCO Hugging Face](https://huggingface.co/fowoco)입니다.
`hr-intent-service/`는 프로젝트 결과 재현과 AI 저장소 인계를 위한 스냅샷입니다.
파일 SHA·학습 데이터 계보·Secret 관리 기준은
[`docs/MODEL_ARTIFACT_POLICY.md`](docs/MODEL_ARTIFACT_POLICY.md)를 따릅니다.
여섯 대표 업무의 단계 의존성·완료 증빙·HR 승인 계약은
[`docs/WORKFLOW_RUNTIME.md`](docs/WORKFLOW_RUNTIME.md)를 기준으로 공유합니다.
문서 Parser와 OCR이 공통으로 반환할 IR, Template 격리, Excel 정규화 기준은
[`docs/DOCUMENT_PROCESSING_CONTRACT.md`](docs/DOCUMENT_PROCESSING_CONTRACT.md)를 따릅니다.

## 데이터 기준

- 최종 학습·검증 원본: `data/intent/hr_intent_dataset_final.jsonl` 1,340건
- Train ID: `data/intent/splits/train_ids.txt` 1,072건
- Validation ID: `data/intent/splits/validation_ids.txt` 268건
- 검수 전 원본: `data/intent/hr_intent_dataset.jsonl` — 감사·비교용, 신규 학습 금지
- 독립 Gold Test: 아직 없음

자세한 사용 기준은 [`data/README.md`](data/README.md)를 확인합니다.

## 설치와 검증

Git 저장소 루트에서 실행합니다.

```bash
python3.11 -m venv .venv
make install
make check
```

패키지 디렉터리에서 직접 실행할 때는 다음 명령을 사용할 수 있습니다.

```bash
../.venv/bin/python -m pip install -e ".[dev]"
../.venv/bin/python -m fowoco_knowledge validate
../.venv/bin/python -m pytest tests
```

## CLI 예시

```bash
# 지원 Workflow 목록
.venv/bin/python -m fowoco_knowledge list-workflows

# Workflow에 필요한 Context 확인
.venv/bin/python -m fowoco_knowledge compile-context WF-STY-001

# 분류·Slot Filling 결과 검증
.venv/bin/python -m fowoco_knowledge check-request \
  fowoco-knowledge/examples/ambiguous_document_request.json

# 신청 업무별 정규화 필요서류 조회
.venv/bin/python -m fowoco_knowledge \
  list-required-documents "외국인 고용변동 등 신고"
```

`check-request`는 자연어 모델을 대신하지 않습니다. 모델 출력이 Workflow를 시작하기에
충분한지 규칙으로 검사합니다.

## 업무 경계

```text
HR 입력
  -> Intent + evidence 분류
  -> Workflow·필수 Slot·공식 출처 조회
  -> 누락·모호성·금지 실행 검증
  -> 업무카드와 안내문 초안
  -> HR 승인
```

기관 자동 제출, 법적 최종 판단, 노무위반 확률 예측은 MVP 범위가 아닙니다.
