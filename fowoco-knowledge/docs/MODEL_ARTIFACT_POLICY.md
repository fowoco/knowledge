# Intent 모델 산출물 보관·배포 정책

## 한 줄 기준

학습 데이터와 검증 기준은 `fowoco/knowledge`, 배포 가중치는 비공개 Hugging Face,
운영 추론 코드는 `fowoco/ai`가 소유한다. 배포는 모델 이름의 `latest`가 아니라
Hugging Face commit SHA를 고정해서 수행한다.

## 저장 위치와 책임

| 대상 | 기준 위치 | 책임 |
| --- | --- | --- |
| Intent 라벨·학습/검증 데이터 | `fowoco/knowledge` | 데이터 버전·SHA·검수 기준 |
| 제출·재현용 가중치 스냅샷 | Knowledge Git LFS | 파일 무결성과 인계 |
| 배포용 가중치 | `fowoco` Hugging Face private repo | 접근 제어·배포 revision |
| 운영 추론 코드 | `fowoco/ai` | 모델 로딩·fallback·응답 계약 |
| `HF_TOKEN` | 로컬 `.env` 또는 배포 Secret | 배포 운영자 |

Knowledge Git LFS 파일은 HF 장애나 권한 인계 시 결과를 재현하기 위한 스냅샷이다.
운영 서비스가 GitHub의 대용량 파일을 직접 내려받아 실행하는 경로로 사용하지 않는다.

## 배포 전 확인 순서

1. `python -m fowoco_knowledge validate`로 데이터와 로컬 스냅샷의 SHA·크기를 확인한다.
2. 권한이 있는 계정으로 HF repo의 commit SHA를 조회한다.
3. AI 배포 환경의 모델 경로를 `repo@commit_sha`로 고정한다.
4. `HF_TOKEN`을 저장소가 아닌 Secret으로 주입한다.
5. 같은 문장으로 BERT 기본 경로와 A.X fallback 경로를 각각 Smoke Test한다.
6. 응답의 `modelVersion`, Knowledge 데이터 version·SHA, AI commit을 실행 기록에 남긴다.

비공개 저장소이므로 인증하지 않은 HF API가 `401`을 반환하는 것은 정상이다. 이때
revision을 추측하거나 `main`으로 대체하지 않고, 배포 담당자가 인증 후 SHA를 확인한다.

## 재현 기준

- 모델 파일 목록·SHA-256·크기: `hr-intent-service/models/artifact-manifest.yaml`
- 모델 목적·평가·한계: `hr-intent-service/models/MODEL_CARD.md`
- 학습 데이터 기준: `data/intent/manifest.yaml`의 `known_model_training_snapshot`
- 라이브러리 범위: `hr-intent-service/requirements.txt`

현재 가중치는 Intent 데이터 `1.2.0` snapshot으로 학습됐다. 현재 데이터 `1.2.1`과
일치하지 않으므로, `1.2.1` 성능으로 표현하거나 재학습된 가중치처럼 배포하면 안 된다.

## Token 관리

- 개인 Read token 또는 배포 전용 최소 권한 token만 사용한다.
- `.env`, GitHub Actions Secret, Kubernetes Secret 이외의 위치에 기록하지 않는다.
- README, Issue, PR, 로그, Docker image layer에 실제 token을 넣지 않는다.
- 유출이 의심되면 즉시 폐기·재발급하고 실행 환경의 Secret을 교체한다.

## 최소 Smoke Test

AI 저장소에서 실제 모델을 켠 뒤 다음을 확인한다.

```text
입력: 응웬반안 체류연장 준비해줘
기대 Intent: EXPIRY_RENEWAL
기대 Workflow: WF-STY-001
금지: modelProvider/modelVersion이 stub으로 표시되는 응답
```

정확도 수치는 내부 Validation 268건의 개발 결과다. 독립 Gold Test 또는 운영 성능으로
표현하지 않으며 법률 판단, Workflow 실행, 외부기관 제출은 모델의 책임이 아니다.
