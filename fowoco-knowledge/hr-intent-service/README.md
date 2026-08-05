# HR Intent Classification model

BERT(Full FT) 메인 모델 + A.X-4.0-Light(QLoRA) 보조 모델 cascade 구조의 HR 업무 요청 문장 Intent 분류 모델

## 현재 상태 (2026-08-04 기준)

- ✅ 모델 학습·검증 완료 
- ✅ 로컬 FastAPI 서비스 구현 및 검증 완료
- ✅ Hugging Face Hub(private) 모델 저장소 연동 완료
- ✅ Colab GPU 환경에서 BERT + A.X 전체 cascade 실제 요청/응답 검증 완료


## 아키텍처

```text
[HR 입력 데이터 수신]
       │
       ▼
[1차 검증] 활성 라벨 수 ≥ 3개? (OOD) ────────► (YES) ──┐
       │                                              │
       ▼                                              │
[2차 검증] 고위험/오답 키워드 포함? ─────────► (YES) ──┼──► [A.X-4.0-Light (LLM) 호출]
       │                                              │
       ▼                                              │
[3차 검증] Margin Score < 0.76 ? ────────────► (YES) ──┘
       │
       └── (NO: 모든 안전망 통과) ──────────────────► [BERT 결과 최종 사용]
```

라우팅 규칙 및 모델 구조 선정 근거는 팀 노션 문서 참조

### 모델 구성

| 모델 | 역할 | 방식 | Validation 268건 정확도 |
|---|---|---|---|
| klue/roberta-base | 메인 | Full Fine-tuning | 95.5% |
| A.X-4.0-Light | 보조 | QLoRA (checkpoint-402) | 92.2% |
| Cascade 모델 | 최종 | 메인 모델 + 보조 모델 , 라우팅 조건 적용 | 93.2% |


## Hugging Face Hub 연동

https://huggingface.co/fowoco 

모델 학습 가중치는 `fowoco` 조직의 private repo에 저장되어 있다. GitHub에는 코드만 올리고, 모델 파일은 여기서 관리한다 .
```
fowoco/klue-roberta-base-intent-classifier  
fowoco/ax-intent-qlora                        
```

### 필요한 환경변수

```
BERT_MODEL_DIR=fowoco/klue-roberta-base-intent-classifier
AX_BASE_MODEL_NAME=skt/A.X-4.0-Light          # 공개 모델, 토큰 불필요
AX_ADAPTER_PATH=fowoco/ax-intent-qlora
HF_TOKEN=<fowoco 조직 접근 권한이 있는 개인 토큰 : intent 모델 담당자에 문의 바람 >
```

`HF_TOKEN`은 절대 코드나 `Dockerfile`에 하드코딩하지 않는다. `.env`(`.gitignore`로 제외됨) 또는 배포 시 Secret으로 주입한다.


## 로컬 실행 - 가상환경

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env   # 값 채우기 (HF_TOKEN 등)
uvicorn app.main:app --reload
```

GPU가 없는 로컬 환경에서는 `.env`에 `ENABLE_AX=False`로 두면 BERT만으로 서비스가 뜬다 (A.X 로드 실패 시에도 동일하게 자동으로 BERT-only degraded 모드로 전환됨, `pipeline.py` 참고).

## 로컬 실행 - Docker

```bash
docker build -t hr-intent-service:test .
docker run -p 8000:8000 --env-file .env hr-intent-service:test
```

로컬 환경에서는 `.env`에 `ENABLE_AX=False`로 둘 것을 권장함.