"""서비스 진입점. uvicorn app.main:app 으로 실행."""

import logging

from fastapi import FastAPI

from .config import get_settings
from .pipeline import HybridIntentPipeline
from .schema import ClassifyRequest, ClassifyResponse

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="HR Intent Classification Service")
pipeline: HybridIntentPipeline | None = None


@app.on_event("startup")
def load_models() -> None:
    global pipeline
    settings = get_settings()
    pipeline = HybridIntentPipeline(settings)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if pipeline is not None else "loading",
        "ax_available": pipeline.ax_available if pipeline else False,
    }


@app.post("/api/v1/intents/classify", response_model=ClassifyResponse)
def classify(request: ClassifyRequest) -> ClassifyResponse:
    return pipeline.predict(request.instruction)