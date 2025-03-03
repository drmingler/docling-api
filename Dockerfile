# Use a base image with CUDA support and the desired Python version
FROM python:3.12-slim-bookworm

ARG CPU_ONLY=false
WORKDIR /app

RUN apt-get update \
    && apt-get install -y redis-server libgl1 libglib2.0-0 curl wget git procps \
    && apt-get clean

# Install UV
RUN pip install uv

# Copy project files needed for installation
COPY pyproject.toml README.md ./

# Install dependencies before torch
RUN uv pip install --system -e .

# Install PyTorch separately based on CPU_ONLY flag
RUN if [ "$CPU_ONLY" = "true" ]; then \
    uv pip install --system --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu; \
    else \
    uv pip install --system torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121; \
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

CMD ["uvicorn", "--port", "8080", "--host", "0.0.0.0", "main:app"]
