"""서비스 설정. 모든 값은 환경변수로 주입.

로컬 개발: .env 파일 사용
운영 배포: 컨테이너 오케스트레이터 주입
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 모델 경로 - Hugging Face Hub repo ID 형식
    # BERT/A.X 어댑터는 fowoco 조직의 private repo이므로 hf_token 인증이 필요
    # A.X 베이스 모델(skt/A.X-4.0-Light)은 공개 모델이라 토큰 없이도 접근 가능

    bert_model_dir: str = "fowoco/klue-roberta-base-intent-classifier"
    ax_base_model_name: str = "skt/A.X-4.0-Light"
    ax_adapter_path: str = "fowoco/ax-intent-qlora"

    hf_token: str | None = None

    # 라우팅 규칙 파라미터
    margin_threshold: float = 0.76
    max_trained_labels: int = 3
    label_prob_threshold: float = 0.55

    # 입력 검증
    max_input_length: int = 150  

    # 생성 파라미터 (A.X)
    ax_max_new_tokens: int = 96

    # 런타임
    device: str = "auto"  # "auto" | "cuda" | "cpu"
    enable_ax: bool = True


@lru_cache
def get_settings() -> Settings:
    """설정을 한 번만 로드하고 재사용 (매 요청마다 다시 읽지 않음)."""
    return Settings()