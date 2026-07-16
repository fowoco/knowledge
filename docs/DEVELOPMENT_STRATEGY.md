# FOWOCO 개발 전략

## 1. 운영 모델

FOWOCO는 **GitHub Flow에 가까운 Trunk-based 방식**을 사용합니다.

- 배포 가능한 기준 브랜치는 `main` 하나
- `develop` 브랜치는 두지 않음
- 모든 작업은 Issue에서 시작
- 브랜치는 1~3일 안에 병합 가능한 크기로 유지
- 완성 전이라도 Draft PR을 먼저 열어 충돌과 설계 차이를 조기에 확인
- 실험 코드는 운영 경로와 분리하고, 검증된 결과만 제품 코드에 반영

7명 규모의 프로젝트에서 `main`과 `develop`을 함께 장기 운영하면 동기화 비용이 커지므로 사용하지 않습니다.

## 2. 표준 작업 흐름

```text
Issue 생성·범위 합의
  -> 기능 브랜치 생성
  -> 작은 기능 단위 커밋
  -> Draft PR 조기 생성
  -> CI와 교차 리뷰
  -> Ready for review 전환
  -> Rebase 또는 Squash 병합
  -> Issue 종료·브랜치 자동 삭제
```

### Issue

- 사용자 가치, 데이터 작업, 실험, 기술부채를 각각 별도 Issue로 관리
- 제목: `[영역] 한국어 작업명`
- 완료 조건, 범위 제외, 검증 방법을 반드시 작성
- 선행 작업이 있으면 `status:blocked`와 선행 Issue 링크 지정

### Branch

형식은 `<type>/issue-<번호>-<short-slug>`입니다.

| Type | 용도 | 예시 |
| --- | --- | --- |
| `feat` | 제품·Agent 기능 | `feat/issue-12-worker-upload` |
| `fix` | 버그 수정 | `fix/issue-18-date-normalization` |
| `data` | 라벨·Context·평가 데이터 | `data/issue-4-gold-seed` |
| `experiment` | 모델 비교 실험 | `experiment/issue-5-intent-baseline` |
| `docs` | 문서만 변경 | `docs/issue-9-development-strategy` |
| `chore` | 설정·도구·의존성 | `chore/issue-20-dependabot` |
| `hotfix` | 운영 중 긴급 수정 | `hotfix/issue-31-token-leak` |

자동화 도구가 만드는 브랜치는 `agent/<short-description>`을 허용합니다.

### Commit

```text
<type>(<scope>): <한국어 요약>
```

- 한 커밋은 되돌릴 수 있는 하나의 기능 단위
- 코드와 해당 테스트는 같은 커밋에 포함 가능
- 무관한 포맷팅·리팩터링을 기능 커밋에 섞지 않음
- 본문 마지막에 `Refs #이슈번호` 또는 `Closes #이슈번호` 사용

예시:

```text
feat(agent): 복합 요청 후보 업무카드 분리
data(knowledge): 체류업무 Gold 문장 20건 추가
fix(server): 만료일 기준일 계산 오류 수정
```

### Pull Request

- 제목도 Commit 형식과 동일하며 콜론 뒤에 한국어 포함
- 500줄 이상 변경은 생성 데이터와 스키마를 제외하고 분리 검토
- API·DB·보안 정책 변경은 영향 범위와 롤백 방식을 작성
- UI 변경은 화면 캡처 또는 Figma 링크 첨부
- 모델 변경은 데이터 버전, baseline, 지표, 오류 사례 첨부
- Ready 전환 전 작성자가 자체 체크리스트 완료

## 3. 병합 정책

| 상황 | 방식 |
| --- | --- |
| 하나의 Issue를 하나의 결과로 만든 일반 PR | Squash merge |
| 독립 가치가 있는 기능 커밋 여러 개를 의도적으로 보존 | Rebase merge |
| Merge commit | 사용하지 않음 |

- 병합 후 원격 브랜치 자동 삭제
- 현재 Draft PR은 기능 단위 커밋의 설계 이력을 보여주므로 Rebase merge 권장
- 팀원이 2명 이상 GitHub Collaborator로 등록되면 `main`에 승인 1명과 필수 CI를 적용

## 4. 모노레포 경계

| Package | 소유 책임 | 직접 접근 금지 |
| --- | --- | --- |
| `fowoco-client` | HR 웹·근로자 모바일 UI | DB·모델 내부 구현 |
| `fowoco-server` | 인증·업무카드·문서·알림 API | 모델 프롬프트 직접 관리 |
| `fowoco-ai` | 분류·추출·Agent Workflow | 원본 개인정보 장기 저장 |
| `fowoco-knowledge` | Intent·Slot·Workflow·출처·평가셋 | 운영 DB 상태 변경 |
| `fowoco-infra` | 배포·Secret·관측·네트워크 | 제품 업무 규칙 정의 |

패키지 간 연결은 OpenAPI, JSON Schema, 이벤트 스키마 등 명시적인 계약으로 수행합니다.
공통 계약이 바뀌면 소비 패키지 테스트도 같은 PR에서 갱신합니다.

## 5. 코드 기준

### Python

- Python 3.12
- Ruff lint·format
- 타입 힌트 필수, 공개 함수는 반환형 명시
- pytest로 정상·오류·경계 사례 검증
- 파일·네트워크·모델 호출은 테스트에서 교체 가능하도록 경계 분리

### TypeScript

- Node.js LTS와 TypeScript strict mode
- ESLint·Prettier·Vitest 적용
- 서버 응답을 `any`로 우회하지 않고 계약 타입으로 검증
- React Query는 서버 상태, 화면 전용 상태만 로컬 또는 경량 Store 사용

### API·DB

- API 우선 계약과 명시적인 버전 관리
- DB 변경은 migration 파일로만 수행
- 날짜는 DB·API에서 ISO 8601과 timezone을 보존
- 멱등성·재시도·중복 업무카드 생성 조건을 테스트

## 6. AI·데이터 기준

- 학습·검증·평가 데이터를 물리적으로 분리
- 평가셋을 Few-shot 예시나 학습 데이터로 재사용 금지
- 모델 실험은 데이터 버전, seed, 파라미터, 지표를 기록
- 모델 정확도만으로 배포하지 않고 중요 클래스 Recall과 실패 사례 검토
- 날짜·금액 계산과 상태 전이는 모델이 아닌 코드로 처리
- LLM 출력은 Structured Output과 Schema Validation 통과 후 사용
- Prompt·Context Pack·Model 버전을 Agent 실행 로그에 기록
- 합성 데이터는 실제 운영 데이터로 표현하지 않음

## 7. 보안 기준

- Secret과 `.env` 커밋 금지
- 원본 여권·외국인등록증·급여명세서는 암호화 저장소 사용
- Agent에는 원본 대신 필요한 마스킹 필드와 `document_id`만 전달
- 품질개선 로그에는 실명·등록번호·여권번호·전화번호·계좌번호 저장 금지
- 외부 발송·기관 제출·계약 확정은 MVP에서 HR 승인 필수
- 보안 관련 PR에는 `security:privacy` 라벨 지정

## 8. CI 기준

패키지 경로별로 필요한 검사만 실행합니다.

```text
PR 제목 형식
  -> lint / format
  -> schema / contract validation
  -> unit test
  -> package build
  -> security check
```

실패한 CI를 건너뛰어 병합하지 않습니다. 외부 서비스 문제로 우회할 경우 Issue와 사유를 남깁니다.

## 9. ADR

다음 변경은 `docs/adr`에 Architecture Decision Record를 작성합니다.

- 패키지 추가·분리
- 주요 Framework·DB·모델 변경
- 인증·개인정보·암호화 정책 변경
- Agent 실행 구조와 외부 연동 방식 변경
- 되돌리기 어려운 데이터 스키마 결정

## 10. Definition of Done

- [ ] 연결 Issue와 수용 기준 충족
- [ ] 기능·오류·경계 테스트 작성
- [ ] lint·format·test·schema CI 통과
- [ ] 개인정보·Secret·로그 점검
- [ ] API·DB·Context 변경 문서화
- [ ] 사용자 화면 또는 실행 예시 검증
- [ ] 후속 작업이 있으면 별도 Issue 생성
- [ ] PR 리뷰 반영 후 병합 방식 선택
