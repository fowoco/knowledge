# FOWOCO

E-9 외국인근로자를 고용한 사업장의 반복 HR·행정업무를 구조화하고,
담당자가 다음 행동을 빠뜨리지 않도록 지원하는 업무보조 플랫폼입니다.

이 저장소는 서비스 구성요소를 하나의 저장소에서 관리하는 모노레포입니다.
현재는 Agent가 공통으로 참조할 업무 지식 패키지부터 구축합니다.

## Packages

| 디렉토리 | 역할 | 상태 |
| --- | --- | --- |
| `fowoco-knowledge` | Intent·Domain·Workflow·공식 출처·검증 데이터 | 개발 중 |
| `fowoco-client` | HR 웹과 근로자 모바일 웹 | 예정 |
| `fowoco-server` | 인증·업무카드·문서·알림 API | 예정 |
| `fowoco-ai` | 분류·추출·Agent 오케스트레이션 | 예정 |
| `fowoco-infra` | 배포·관측·보안 설정 | 예정 |

## Quick start

```bash
python3.11 -m venv .venv
make install
make validate
make test
```

자세한 사용법은 [`fowoco-knowledge/README.md`](fowoco-knowledge/README.md)를 참고합니다.

## 원칙

- 법정기한 계산, 필수값 확인, 상태 전이는 검증 가능한 규칙으로 처리
- AI는 자연어 분류·정보 추출·모호성 탐지·초안 생성에 사용
- MVP의 모든 외부 발송과 기관 제출은 HR 담당자 승인 후 수행
- 개인정보 원문은 학습·품질개선 데이터에 저장하지 않음
- 공식 절차와 서류 지식은 출처, 검증일, 버전을 함께 관리

## 협업

변경 전 [`CONTRIBUTING.md`](CONTRIBUTING.md)의 브랜치·커밋·데이터 검수 규칙을 확인합니다.
