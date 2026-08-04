# A.X Intent 분류 테스트 가이드

## 1. 목적

Intent 규칙 v1.1 프롬프트를 A.X에 보내 `Intent + evidence` 출력과 오류 유형을
확인한다. 현재 원본 라벨과 Validation은 `recheck_required` 상태이므로 결과를 최종
모델 또는 Gold Test 성능으로 주장하지 않는다.

공식 자료:

- [skt/A.X-4.0-Light 모델 카드](https://huggingface.co/skt/A.X-4.0-Light)
- [SKT A.X 4.0 API 문서](https://github.com/SKT-AI/A.X-4.0/blob/main/apis/README.md)

공식 모델 카드는 A.X 4.0 Light가 7B 모델이며 Transformers와 vLLM 실행 방법을
제공한다. 무료 guest API 문서는 모델명을 `ax4`로만 안내하므로, 해당 API 결과를
A.X 4.0 Light 결과라고 단정하지 않는다.

## 2. 현재 공식 guest API 상태

2026-07-27 확인 결과, 공식 API 문서에 기재된
`https://guest-api.sktax.chat/v1`은 HTTP 연결에는 성공하지만 다음 종료 안내만
반환한다.

```text
Guest 용 API Endpoint 서비스는 종료되었습니다.
```

따라서 문서에 적힌 공개 key와 guest endpoint로는 현재 모델 추론을 시험할 수 없다.
테스트하려면 팀에서 사용할 수 있는 A.X API endpoint와 key를 받거나, 아래 5절처럼
공식 Light 모델을 로컬에서 실행해야 한다. 이 저장소는 종료된 guest 주소를 작동하는
기본값으로 사용하지 않는다.

## 3. 팀 A.X API 설정

API key는 코드, `.env.example`, 명령행 인자 또는 결과 파일에 기록하지 않는다.
사용하는 A.X 제공자에서 OpenAI 호환 endpoint와 key를 확인해 환경변수로만 설정한다.

```bash
export AX_API_KEY="팀에서 발급받은 키"
export AX_BASE_URL="팀에서 전달받은 OpenAI 호환 base URL"
export AX_MODEL="팀에서 전달받은 모델명"
```

`ADOTX_API_KEY`도 호환한다. `.env` 파일은 Git에서 제외되지만 셸이 자동으로 읽지는
않으므로 직접 `source .env` 하거나 환경변수를 내보내야 한다.

## 4. API로 한 문장 테스트

실제 개인정보 대신 `WRK-001` 같은 더미 식별자를 사용한다.

```bash
python -m fowoco_knowledge test-intent-ax \
  "WRK-001 체류기간 만료가 다가오니 여권 사본 받아줘" \
  --confirm-external
```

출력에서 다음 항목을 확인한다.

- `requested_model`, `returned_model`: 요청·응답 모델명
- `raw_content`: A.X 원문 응답
- `parsed_output`: 추출된 JSON
- `parse_strategy`: 직접 JSON, 코드 펜스, 부가설명 속 JSON 여부
- `issues`: Schema, evidence substring, 순서, 중복, OUT_OF_SCOPE 오류

구조 오류가 있으면 명령은 종료 코드 1을 반환한다. 모델 응답을 정답처럼 자동
수정하지 않는다.

## 5. API로 소량 Smoke Evaluation

Validation 앞부분 5건:

```bash
python -m fowoco_knowledge run-intent-ax-evaluation \
  --limit 5 \
  --delay-seconds 1 \
  --confirm-external
```

특정 원본 ID:

```bash
python -m fowoco_knowledge run-intent-ax-evaluation \
  --ids 20,74,198,653,1206 \
  --delay-seconds 1 \
  --confirm-external
```

전체 Validation 268건은 제공자의 호출 제한과 비용을 확인한 뒤에만 실행한다.

```bash
python -m fowoco_knowledge run-intent-ax-evaluation \
  --all-validation \
  --delay-seconds 1 \
  --confirm-external
```

결과는 기본적으로 Git에서 제외되는 다음 로컬 경로에 저장된다.

```text
local-data/experiments/intent/ax-zero-shot-v1/
├── predictions.jsonl
└── report.yaml
```

Report는 Intent Exact Match, Macro/Micro F1, evidence 정답 완전일치, 구조 Gate,
오류 건수와 token usage를 분리해 기록한다.

## 6. 공식 A.X 4.0 Light를 로컬에서 직접 테스트

최초 1회 로컬 실행 의존성을 설치한다.

```bash
pip install -e ".[ax-local]"
```

Apple Silicon Mac에서는 다음처럼 한 문장을 테스트한다.

```bash
python -m fowoco_knowledge test-intent-ax-local \
  "WRK-001 체류기간 만료가 다가오니 여권 사본 받아줘" \
  --device mps \
  --confirm-model-download
```

`--confirm-model-download`는 공식 `skt/A.X-4.0-Light` 모델을 Hugging Face에서
처음 내려받고 메모리에 올리는 작업을 명시적으로 허용한다. 7B BF16 원본 가중치는
대용량이며, 24GB Mac에서도 다른 앱의 메모리 사용량에 따라 로딩에 실패할 수 있다.
CI에서는 이 명령을 실행하지 않는다.

로컬 명령도 API 명령과 동일한 `raw_content`, `parsed_output`, `issues` 구조를
출력하므로 Intent와 evidence 결과를 그대로 비교할 수 있다.

## 7. GPU 서버의 A.X 4.0 Light에 연결

공식 모델 카드의 vLLM 예시처럼 GPU 서버에서 Light 모델을 OpenAI 호환 endpoint로
실행한 경우 다음처럼 연결한다.

```bash
vllm serve skt/A.X-4.0-Light

export AX_BASE_URL="http://localhost:8000/v1"
export AX_MODEL="skt/A.X-4.0-Light"
export AX_API_KEY="local"

python -m fowoco_knowledge test-intent-ax \
  "WRK-001 체류기간 연장 준비해줘" \
  --confirm-external
```

현재 개발 Mac은 Apple Silicon이므로 CUDA 기반 vLLM 서버를 직접 실행하는 환경과는
다르다. Mac에서 quantized 모델을 별도로 구동할 경우에도 OpenAI 호환 endpoint만
제공하면 같은 테스트 명령을 사용할 수 있다.

## 8. 개인정보와 해석 제한

- 실제 외국인등록번호, 여권번호, 전화번호, 계좌번호를 전송하지 않는다.
- 코드의 기본 개인정보 패턴 검사는 보조 장치이며 사람 이름과 모든 식별자를 완전히
  탐지하지 못한다.
- 종료된 guest API 연결 성공을 모델 추론 성공으로 표현하지 않는다.
- API의 `ax4` 결과를 `A.X-4.0-Light` 결과로 바꿔 표현하지 않는다.
- 수정 전 라벨로 얻은 점수는 consensus 반영 후 같은 prompt로 다시 측정한다.
