FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y python3.11 python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 모델은  HF Hub에서 받아온다.
ENV BERT_MODEL_DIR=fowoco/klue-roberta-base-intent-classifier
ENV AX_BASE_MODEL_NAME=skt/A.X-4.0-Light
ENV AX_ADAPTER_PATH=fowoco/ax-intent-qlora

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]