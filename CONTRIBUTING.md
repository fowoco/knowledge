# Contributing

전체 개발·리뷰·보안 기준은 [`docs/DEVELOPMENT_STRATEGY.md`](docs/DEVELOPMENT_STRATEGY.md)를 따릅니다.

## Standard workflow

1. 완료 조건이 있는 GitHub Issue 생성
2. `<type>/issue-<번호>-<short-slug>` 브랜치 생성
3. 되돌릴 수 있는 기능 단위로 커밋
4. 작업 초기에 Draft PR 생성
5. CI·자체 점검 후 Ready for review 전환
6. 리뷰 반영 후 Squash 또는 Rebase merge
7. Issue 종료와 원격 브랜치 삭제

## Branch

`<type>/<short-description>` 형식을 사용합니다.

- `feat/worker-document-workflow`
- `data/add-payroll-gold-cases`
- `fix/relative-date-validation`
- 자동화 도구가 만드는 브랜치는 `agent/<short-description>` 사용

## Commit

Conventional Commits를 따릅니다.

```text
<type>(<scope>): <한국어 요약>
```

- `type`과 `scope`는 자동화 도구와 변경 이력 분류를 위해 영문 유지
- 콜론 뒤 제목은 변경 결과가 바로 드러나는 간결한 한국어 사용
- 필요한 경우 본문에 변경 배경, 영향 범위, 연결 Issue를 한국어로 작성

| Type | 사용 시점 |
| --- | --- |
| `feat` | 사용자 또는 Agent 기능 추가 |
| `fix` | 동작 오류 수정 |
| `data` | Context Pack·라벨·출처 데이터 변경 |
| `docs` | 문서만 변경 |
| `test` | 테스트 추가·수정 |
| `refactor` | 동작 변경 없는 구조 개선 |
| `chore` | 도구·설정·의존성 변경 |

예시:

- `feat(knowledge): 체류연장 Workflow 추가`
- `data(knowledge): 평가 데이터 18건 추가`
- `fix(agent): 복합 요청 분리 오류 수정`
- `docs(repo): 커밋 메시지 한글 규칙 추가`

## Knowledge 변경 규칙

1. 공식 절차 변경은 `source_id`, URL, 검증일을 함께 갱신
2. 법령·행정 지식은 한 명 작성 후 다른 팀원 한 명 이상 검수
3. 인터뷰 기반 문장은 개인·회사 식별정보를 제거하고 `INTERVIEW_DERIVED_ANON`으로 표시
4. 합성 문장은 실제 사례로 표현하지 않고 `TEAM_SYNTHETIC`으로 표시
5. 평가 데이터는 학습·프롬프트 예시 데이터와 분리
6. `make check` 통과 후 Pull Request 생성

## Pull Request

- 한 PR은 하나의 Workflow 또는 하나의 기술 목적에 집중
- 데이터 변경 시 추가·수정·삭제 건수와 라벨 분포 기재
- 공식자료 변경 시 출처와 확인일 기재
- 개인정보·원본 인터뷰·원본 신분서류 업로드 금지
- 제목은 Commit 형식과 동일하게 작성하고 콜론 뒤에 한국어 포함
- 되돌리기 어려운 기술 결정은 `docs/adr`에 ADR 추가
