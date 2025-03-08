# First, build the application and install dependencies
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Download models in builder stage
RUN apt-get update && \
    apt-get install -y libgl1 libglib2.0-0 && \
    apt-get clean

# Copy only dependency files and README (required for package installation)
COPY pyproject.toml uv.lock README.md ./

# Create venv and install project for model downloads
RUN python -m venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv pip install -e .

# Set up cache directories and download models
ENV HF_HOME=/app/.cache/huggingface \
    TORCH_HOME=/app/.cache/torch

# Download models
RUN . /app/.venv/bin/activate && \
    mkdir -p /app/.cache && \
    python -c 'from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline; artifacts_path = StandardPdfPipeline.download_models_hf(force=True);' && \
    python -c 'import easyocr; reader = easyocr.Reader(["fr", "de", "es", "en", "it", "pt"], gpu=True); print("EasyOCR models downloaded successfully")'

# Final stage with CUDA support
FROM python:3.12-slim-bookworm AS runtime

ARG CPU_ONLY=false
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y redis-server libgl1 libglib2.0-0 && \
    apt-get clean

# Copy dependency files and models from builder
COPY --from=builder --chown=app:app /app/.cache /app/.cache/
COPY --from=builder --chown=app:app /app/.venv /app/.venv/

# Copy project files from disk
COPY --chown=app:app pyproject.toml uv.lock README.md ./
COPY --chown=app:app document_converter/ ./document_converter/
COPY --chown=app:app worker/ ./worker/
COPY --chown=app:app main.py ./

# Set up Python environment
ENV PYTHONPATH=/app \
    HF_HOME=/app/.cache/huggingface \
    TORCH_HOME=/app/.cache/torch \
    OMP_NUM_THREADS=4

# Create app user
RUN useradd -m app && \
    chown -R app:app /app /tmp && \
    python -m venv /app/.venv && \
    chown -R app:app /app/.venv

USER app

# Install dependencies and project
RUN . /app/.venv/bin/activate && \
    cd /app && \
    pip install -e .

# Install PyTorch with CUDA support
RUN . /app/.venv/bin/activate && \
    if [ "$CPU_ONLY" = "true" ]; then \
    pip install --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu; \
    else \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121; \
    fi

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "--port", "8080", "--host", "0.0.0.0", "main:app"]