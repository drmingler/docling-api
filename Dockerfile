FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ARG CPU_ONLY=false

WORKDIR /app

# Install both build- and runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends redis-server libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables for cache directories
ENV HF_HOME=/app/.cache/huggingface \
    TORCH_HOME=/app/.cache/torch  \
    PYTHONPATH=/app \
    OMP_NUM_THREADS=4 \
    PATH="/app/.venv/bin:$PATH"
# Copy dependency files and README
COPY pyproject.toml uv.lock README.md ./

# Create a virtual environment and install the project in editable mode
RUN python -m venv /app/.venv && \
    /app/.venv/bin/pip install --upgrade pip && \
    uv pip install --python /app/.venv/bin/python -e .

# Create a non-root user and adjust permissions
RUN useradd --create-home app && \
    mkdir -p /app && \
    chown -R app:app /app /tmp


# PyTorch installation with architecture detection
RUN ARCH=$(uname -m) && \
    /app/.venv/bin/pip uninstall -y torch torchvision torchaudio || true && \
    if [ "$CPU_ONLY" = "true" ] || [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
    # For CPU or ARM architectures (which don't support CUDA)
    echo "Installing PyTorch for CPU" && \
    /app/.venv/bin/pip install --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu; \
    else \
    # For x86_64 with GPU support
    echo "Installing PyTorch with CUDA support" && \
    /app/.venv/bin/pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121; \
    fi

RUN python -c 'from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline; artifacts_path = StandardPdfPipeline.download_models_hf(force=True);'

# Pre-download EasyOCR models in compatible groups
RUN ARCH=$(uname -m) && \
    if [ "$CPU_ONLY" = "true" ] || [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
    python -c 'import easyocr; reader = easyocr.Reader(["fr", "de", "es", "en", "it", "pt"], gpu=False); print("EasyOCR CPU models downloaded successfully")'; \
    else \
    python -c 'import easyocr; reader = easyocr.Reader(["fr", "de", "es", "en", "it", "pt"], gpu=True); print("EasyOCR GPU models downloaded successfully")'; \
    fi


# Switch to non-root user
USER app

# Copy all project files (including your source code and directories)
COPY --chown=app:app . .

EXPOSE 8080
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "main:app", "--port", "8080", "--host", "0.0.0.0"]