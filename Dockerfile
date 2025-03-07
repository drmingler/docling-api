# Use a base image with CUDA support and the desired Python version
FROM python:3.12-slim-bookworm

ARG CPU_ONLY=false
WORKDIR /app

RUN apt-get update \
    && apt-get install -y redis-server libgl1 libglib2.0-0 curl wget git procps \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry and configure it
RUN pip install poetry \
    && poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./

# Install dependencies before torch
RUN poetry install --no-interaction --no-root

# Install PyTorch separately based on CPU_ONLY flag
RUN if [ "$CPU_ONLY" = "true" ]; then \
    pip install --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu; \
    else \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121; \
    fi

ENV HF_HOME=/tmp/ \
    TORCH_HOME=/tmp/ \
    OMP_NUM_THREADS=4

RUN python -c 'from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline; artifacts_path = StandardPdfPipeline.download_models_hf(force=True);'

# Pre-download EasyOCR models in compatible groups
RUN python -c 'import easyocr; \
    reader = easyocr.Reader(["fr", "de", "es", "en", "it", "pt"], gpu=True); \
    print("EasyOCR models downloaded successfully")'

COPY . .

EXPOSE 8080

CMD ["poetry", "run", "uvicorn", "--port", "8080", "--host", "0.0.0.0", "main:app"]
