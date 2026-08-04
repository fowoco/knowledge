# FOWOCO Knowledge & Intent Modeling

FOWOCO는 E-9 외국인근로자를 고용한 사업장의 반복 HR·행정업무를 구조화하고,
담당자가 다음 행동을 놓치지 않도록 지원하는 AI 업무보조 서비스입니다.

이 저장소는 Agent가 참고할 업무 지식과 공식 출처뿐 아니라, HR 발화문을
`Intent + evidence`로 분류하기 위한 데이터 계약·검수·평가 및 모델 실험 이력을
함께 관리합니다. 운영 앱과 모델 서버를 구현하는 저장소는 아닙니다.

## 목표

HR 담당자의 입력에서 다음 7개 Intent를 하나 이상 찾고, 판단 근거가 되는 원문의
연속 구간을 `evidence`로 반환합니다.

- `WORKER_ONBOARDING`: 신규 근로자 등록·초기 처리
- `EXPIRY_RENEWAL`: 체류·계약·고용허가 만료와 갱신 준비
- `DOCUMENT_REQUEST`: 서류 요청·수령·미제출 추적
- `PAYROLL_EXPLANATION`: 급여·수당·공제 설명
- `WORK_INSTRUCTION`: 작업·근무일정·현장 안내
- `EMPLOYMENT_CHANGE`: 퇴사·결근·사업장 변경 등 고용상태 변동
- `OUT_OF_SCOPE`: 지원 범위 밖 요청

모델은 Intent와 evidence까지만 판단합니다. Workflow 선택, 외부기관 제출, 법적
판단과 업무 완료는 규칙 검증과 HR 담당자 승인 이후에 처리합니다.

## 진행 과정

| 단계 | 내용 | 저장소 상태 |
| --- | --- | --- |
| 규칙·후보 데이터 | Intent 규칙 v1.1, evidence exact substring, HR 발화문 1,340건 | `main` 반영 |
| A/B 재검수 | 경계 사례 독립 검수와 consensus | [#31](https://github.com/fowoco/knowledge/pull/31), [#35](https://github.com/fowoco/knowledge/pull/35) 검토 중 |
| 모델링 계약 | 유사 템플릿 누수를 막은 Train 1,072건 / Validation 268건 분할 | [#33](https://github.com/fowoco/knowledge/pull/33) 검토 중 |
| 기준 실험 | 수정 전 라벨 baseline과 A.X 테스트 도구 | [#37](https://github.com/fowoco/knowledge/pull/37)이 #33 브랜치에 병합됨 |
| 모델 비교 | A.X-4.0-Light와 KLUE-RoBERTa 실험 | 산출물 반영 예정 |

## 모델 실험 요약

아래 수치는 팀의 최신 Validation 268건 실험 기록입니다. 독립적으로 잠긴 Test
성능이나 운영 성능을 의미하지 않습니다.

| 모델 | Intent Exact Match | 결론 |
| --- | ---: | --- |
| A.X-4.0-Light Few-shot | 0.7612 | 초기 기준선 |
| A.X-4.0-Light QLoRA | 0.9254 | 복잡한 입력의 보조 모델 후보 |
| KLUE-RoBERTa Full FT | 0.9590 | 메인 모델 후보, 약 186ms |
| KLUE-RoBERTa LoRA | 0.9104 | Full FT보다 낮아 기각 |

A.X QLoRA는 evidence exact match가 `0.7377`로 Few-shot의 `0.1667`보다 크게
개선됐습니다. BERT Full FT는 Intent 분류 성능과 응답속도가 가장 좋았습니다.

## 현재 모델 결론

```text
HR 입력
  -> BERT Intent 분류
  -> 복잡도·경계 패턴·예측 margin 검사
      -> 위험하거나 불확실함: A.X로 라우팅
      -> 그 외: BERT 결과 사용
  -> 출력 Schema 검증
  -> Workflow 선택과 HR 승인
```

A.X 라우팅 후보 조건은 다음과 같습니다.

- 활성 Intent가 3개 이상인 복잡한 문장
- 완료·상태보고, 급여계좌, 서류 확보 등 검증된 경계 패턴
- 선택·비선택 Intent 사이의 margin이 `0.76` 미만인 불확실한 예측

현재 Validation에서는 34.3%가 A.X 라우팅 대상으로 선택됐고, BERT 오답이 모두
라우팅 조건에 포함됐습니다. 이는 A.X가 모든 오답을 정정했다는 뜻이 아니며, 같은
Validation에서 만든 규칙이므로 별도 Test에서 다시 검증해야 합니다.

## 현재 데이터 상태

- `main`에는 HR 발화문 후보 데이터 1,340건과 Intent 규칙 v1.1이 있습니다.
- A/B consensus와 고정 split은 아직 `main`에 병합되지 않았습니다.
- consensus 또는 원본이 변경되면 split과 모델 평가는 다시 생성해야 합니다.
- Validation은 모델 개발용이며 최종 성능 주장을 위한 Gold Test가 아닙니다.
- 실제 개인정보와 기업정보는 학습·평가 데이터에 저장하지 않습니다.

최신 BERT·A.X 학습 checkpoint와 운영 서빙 코드는 아직 `main`에 포함하지 않습니다.

## 산출물 위치

- GitHub: 업무 지식, 라벨 규칙, 데이터 계약, 분할·평가 코드와 실험 기록
- [FOWOCO Hugging Face](https://huggingface.co/fowoco): 학습 checkpoint, adapter,
  tokenizer와 model card의 배포 위치

현재 Hugging Face 조직에는 공개된 모델·데이터셋이 없습니다. 산출물을 게시할 때는
학습 데이터 version·SHA-256, 평가 조건, 라이선스와 사용 한계를 model card에 함께
기록합니다.

## 남은 과제

- 최종 consensus 데이터·manifest와 모델 실험 산출물의 저장소 반영
- 독립 Gold Test에서 BERT·A.X·Cascade 재평가
- BERT 경로의 evidence 추출 방식 확정
- 다중 근로자·다중 지시 문장 보강
- A.X GPU 서빙과 실제 운영 환경의 속도·자원 측정
- 학습·서빙 코드는 최종적으로 `fowoco/ai`로 이전

## 저장소 구조

```text
fowoco-knowledge/
├── knowledge/        # Intent·Workflow·Guardrail·공식 링크
├── data/             # Seed·Intent·평가·공공 정규화 데이터
├── schemas/          # 데이터·모델 출력 계약
├── src/              # Knowledge 검증·조회 CLI
├── tests/            # Schema·누수·재현성 테스트
└── docs/             # 라벨·검수·모델링·출처 문서
```

## 실행

```bash
python3.11 -m venv .venv
make install
make check
```

세부 기준은 다음 문서를 참고합니다.

- [Intent 라벨 기준](fowoco-knowledge/docs/INTENT_DATA.md)
- [모델 계획](fowoco-knowledge/docs/MODEL_PLAN.md)
- [공식 데이터 파이프라인](fowoco-knowledge/docs/OFFICIAL_DATA_PIPELINE.md)

## 안전 원칙

- 모델 출력만으로 법률·체류·급여·신고 결론을 확정하지 않습니다.
- 외부기관 제출과 근로자 안내 발송은 HR 승인 후 수행합니다.
- 실제 외국인등록번호, 여권번호, 전화번호, 계좌번호를 저장하지 않습니다.
- 날짜·금액·서류명·제출처·대상자·기한의 누락과 변경을 중점 검증합니다.
