# 기술 코치 피드백 반영표

## 구현 완료

| 피드백 | 결정 | 구현 위치 | 검증 방법 |
| --- | --- | --- | --- |
| 모호성의 기준이 주관적일 수 있음 | 주체·기한·장소·대상물·금액·행동·수량 누락으로 판단 | `required_slots.yaml`, `ambiguity_patterns.yaml`, `engine.py` | `test_quantity_ambiguity_requires_number_and_unit` 등 요청 검사 테스트 |
| 번역문이 원문의 핵심을 살렸는지 확인 필요 | 생성 전 Source Slot과 생성 후 Candidate Slot을 코드로 비교 | `output_quality_policy.yaml`, `quality.py` | 안내문 회귀평가 12건 계약 일치율 1.0 |
| 법령 할루시네이션은 검수에서 놓치면 위험 | 법령 무근거 단정·외부 실행·계산근거 부재를 critical 오류로 분리 | `output_quality_policy.yaml`, `notice_quality_cases.jsonl` | 치명 오류는 모두 `BLOCK_AND_REVIEW` |
| 신뢰도 몇 %라는 단일 기준이 부적절 | 확신도는 모델 라우팅과 HITL 강도에만 사용 | `guardrail_rules.yaml`, `output_quality_policy.yaml` | 낮은 확신도는 분류 재확인, 외부 발송은 항상 HR 승인 |
| 개인정보는 기본적인 보호 수준 필요 | 역할 분리·HTTPS·보호 DB·LLM 전달 최소화·마스킹 | `data_protection.yaml`, `privacy.py` | PII 예시 Payload에서 원본 문서와 직접식별자 제거 테스트 |
| 돈을 낼 문제인지 시간·돈·감정 확인 필요 | 직접 타깃과 인접 타깃 근거를 분리하고 미측정값도 저장 | `interview_findings.csv` | 데이터 리포트에서 인터뷰·정량 기준선 수 확인 |

## 의도적으로 보류

| 항목 | 보류 이유 | 재개 조건 |
| --- | --- | --- |
| 통계 가중치 기반 노무 리스크 점수 | 개별 사업장 결과 라벨이 없어 현재 검증 불가능 | 실제 파일럿 결과와 타당한 가중치 근거 확보 |
| EPS 용어사전 전체 크롤링 | 재배포 조건과 일부 정의의 현행성 검토 필요 | 이용조건 확인과 전문가 현행성 검수 |
| EPS 외국어 문장 DB 전체 적재 | 검색은 가능하나 전체 재배포 조건 불명확 | 기관 사용 허가 또는 명확한 이용조건 확인 |
| AIHub 민원 데이터를 FOWOCO 정답으로 사용 | Intent·Domain 정의가 달라 직접 전이 시 라벨 왜곡 | 보조 사전학습 실험과 자체 Gold 평가 분리 설계 |
| 실제 기관 자동 제출 | 인증·책임·오입력 위험이 학생 MVP 범위를 초과 | 정식 연동 계약과 감사·취소·복구 정책 확보 |

## 해석 주의

- 12건 안내문 데이터는 Language Agent 성능셋이 아니라 검사기 회귀평가
- 18건 `golden_cases.jsonl`은 모델 후보 Smoke Test이며 최종 성능 주장 금지
- 40건 Seed는 두 명 독립 검수 전까지 학습 데이터가 아님
- 13건 인터뷰 발견 중 구매·파일럿 의사는 인접 외국계 수출업 근거
- E-9 제조업 대기업 담당자의 1~2시간은 건당이 아니라 주간 전체 업무시간
