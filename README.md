# FOWOCO Knowledge

FOWOCO Agent가 E-9 외국인근로자 관련 HR·행정업무를 일관된 기준으로 처리하도록
업무 지식, 공식 근거, 데이터 계약과 검증 도구를 버전으로 관리하는 저장소입니다.

## 저장소 책임

이 저장소가 직접 관리하는 범위는 다음과 같습니다.

- Intent·Domain·필수 Slot과 Workflow Catalog
- 공식자료 출처, 정규화 결과와 provenance
- Seed·평가·독립 검수 데이터의 스키마와 품질 기준
- Agent 입출력 및 Workflow 계약용 JSON Schema
- 지식팩의 참조·누락·개인정보 패턴을 검사하는 CLI와 테스트
- AI·Server가 지식팩을 안전하게 소비하기 위한 연동 문서

다음 구현은 각 전용 저장소에서 관리합니다.

| 범위 | 담당 저장소 |
| --- | --- |
| 모델 학습·추론, Agent 오케스트레이션 | [`fowoco/ai`](https://github.com/fowoco/ai) |
| 인증·업무카드·문서·알림 API와 운영 DB | [`fowoco/server`](https://github.com/fowoco/server) |
| HR 대시보드와 근로자 모바일 화면 | [`fowoco/client`](https://github.com/fowoco/client) |
| 배포·Secret·관측·네트워크 | [`fowoco/infra`](https://github.com/fowoco/infra) |

모델 성능 실험이나 제품 기능은 이 저장소에 구현하지 않습니다. 다만 학습·평가 데이터
계약과 Knowledge 소비 인터페이스는 재현성과 호환성 검증을 위해 이곳에 유지합니다.

## 구성

| 경로 | 역할 |
| --- | --- |
| `fowoco-knowledge/knowledge` | Context Pack과 Workflow Catalog |
| `fowoco-knowledge/data` | Seed·평가·검수·공식 정규화 데이터 |
| `fowoco-knowledge/schemas` | Agent·Workflow·Dataset 계약 |
| `fowoco-knowledge/src` | 지식 조회·검증·정규화 CLI |
| `fowoco-knowledge/tests` | 스키마·참조·데이터 품질 회귀검사 |
| `fowoco-knowledge/docs` | 출처·검수·연동·운영 기준 |

## Quick start

```bash
python3.11 -m venv .venv
make install
make validate
make test
```

명령과 데이터 구조의 상세 설명은
[`fowoco-knowledge/README.md`](fowoco-knowledge/README.md)를 참고합니다.

## 원칙

- 법정기한 계산, 필수값 확인, 상태 전이는 검증 가능한 규칙으로 처리
- AI는 자연어 분류·정보 추출·모호성 탐지·초안 생성에 사용
- MVP의 모든 외부 발송과 기관 제출은 HR 담당자 승인 후 수행
- 개인정보 원문은 학습·품질개선 데이터에 저장하지 않음
- 공식 절차와 서류 지식은 출처, 검증일, 버전을 함께 관리

## 변경 원칙

변경 전 [`CONTRIBUTING.md`](CONTRIBUTING.md)의 브랜치·커밋·데이터 검수 규칙을 확인합니다.
