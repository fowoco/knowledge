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

## 현재 결과

| 구분 | 현재 상태 | 기준 파일 |
| --- | --- | --- |
| Intent | 7개 Intent와 evidence exact substring 규칙 v1.1 | [`intents.yaml`](fowoco-knowledge/knowledge/intents.yaml), [`INTENT_DATA.md`](fowoco-knowledge/docs/INTENT_DATA.md) |
| 최종 검수 데이터 | HR 발화문 1,340건 | [`hr_intent_dataset_final.jsonl`](fowoco-knowledge/data/intent/hr_intent_dataset_final.jsonl) |
| 고정 분할 | Train 1,072건 / Validation 268건 | [`splits/`](fowoco-knowledge/data/intent/splits) |
| 업무 지식 | Intent·Workflow·필수 Slot·서류·공식 출처·Guardrail | [`knowledge/`](fowoco-knowledge/knowledge) |
| 모델 | KLUE-RoBERTa 메인 + A.X-4.0-Light 보조 cascade 참고 구현 | [`hr-intent-service/`](fowoco-knowledge/hr-intent-service) |

검수 전 데이터는 변경 이력 확인을 위해
[`hr_intent_dataset.jsonl`](fowoco-knowledge/data/intent/hr_intent_dataset.jsonl)에
보존합니다. 최종 학습·검증에는 `hr_intent_dataset_final.jsonl`과 split ID 파일을
함께 사용합니다.

Validation 268건에서 기록한 모델 결과는 BERT 95.5%, A.X QLoRA 92.2%, Cascade
93.2%입니다. 같은 데이터로 모델을 개발하고 비교한 **내부 Validation 결과**이며,
독립 Gold Test나 운영 성능을 뜻하지 않습니다. 현재 가중치는 데이터 구조 오류 3건을
수정하기 전 version 1.2.0 snapshot 기준이며, 자세한 SHA-256은 모델 README에 기록합니다.

## 저장소 구성

```text
.
├── fowoco-knowledge/
│   ├── knowledge/          # Agent가 참조하는 업무 지식 원본
│   ├── data/               # Intent·Seed·평가·공공 정규화 데이터
│   ├── schemas/            # 데이터와 Agent 출력 JSON Schema
│   ├── src/                # Knowledge 조회·검증 CLI
│   ├── tests/              # Schema·해시·교차참조 검증
│   ├── docs/               # 라벨·출처·검수·연동 기준
│   └── hr-intent-service/  # 모델 서빙 참고 구현과 제출용 스냅샷
├── Makefile
└── .github/workflows/      # PR 규칙과 Knowledge CI
```

`hr-intent-service/`는 모델 결과를 재현하고 인계하기 위한 참고 구현입니다. 운영 모델
서버의 장기 소유권은 `fowoco/ai`에 두고, 이 저장소는 데이터와 지식 계약을 기준으로
유지합니다.

## 빠른 검증

Python 3.11 이상이 필요합니다.

```bash
python3.11 -m venv .venv
make install
make check
```

`make check`는 Ruff, Knowledge/Intent manifest·Schema·SHA-256·분할 검증, 전체 테스트를
실행합니다. 모델 서버 실행 방법은
[`hr-intent-service/README.md`](fowoco-knowledge/hr-intent-service/README.md)를 확인합니다.

## 사용 경계

- Intent 모델의 책임은 `Intent + evidence` 추출까지입니다.
- Workflow 선택, Slot 확인, 완료 처리는 규칙과 HR 담당자의 책임입니다.
- 체류·계약·급여·신고 관련 내용은 모델 출력만으로 확정하지 않습니다.
- 외부기관 제출과 근로자 안내 발송은 자동 실행하지 않습니다.
- 실제 외국인등록번호, 여권번호, 전화번호, 계좌번호를 저장하지 않습니다.
- Validation 데이터는 독립 Gold Test가 아니므로 최종 성능 주장에 사용하지 않습니다.

## 주요 문서

- [데이터 사용 안내](fowoco-knowledge/data/README.md)
- [Intent 라벨 기준](fowoco-knowledge/docs/INTENT_DATA.md)
- [Agent 연동 계약](fowoco-knowledge/docs/AGENT_INTEGRATION.md)
- [공식 데이터 파이프라인](fowoco-knowledge/docs/OFFICIAL_DATA_PIPELINE.md)
- [E-9 신고·연장 Workflow](fowoco-knowledge/docs/E9_REPORTING_WORKFLOWS.md)
