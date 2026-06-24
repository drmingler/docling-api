FROM python:3.12-slim-bookworm AS builder

ARG CPU_ONLY=true
ARG PRELOAD_MODELS=true
ARG POETRY_VERSION=1.8.4
ARG VIRTUAL_ENV=/opt/venv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    HF_HOME=/models/huggingface \
    TORCH_HOME=/models/torch \
    OMP_NUM_THREADS=4 \
    PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl git libgl1 libglib2.0-0 wget \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}" \
    && python -m venv "${VIRTUAL_ENV}"

COPY pyproject.toml poetry.lock ./

# Install locked application dependencies into the runtime virtual environment.
RUN poetry export --only main --without-hashes --format requirements.txt --output /tmp/requirements.txt \
    && "${VIRTUAL_ENV}/bin/pip" install --requirement /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# Install PyTorch separately based on the target runtime.
RUN if [ "$CPU_ONLY" = "true" ]; then \
    "${VIRTUAL_ENV}/bin/pip" install torch torchvision --index-url https://download.pytorch.org/whl/cpu; \
    else \
    "${VIRTUAL_ENV}/bin/pip" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121; \
    fi

RUN if [ "$CPU_ONLY" = "true" ]; then \
    packages="$("${VIRTUAL_ENV}/bin/python" -c 'import importlib.metadata as m; print(" ".join(d.metadata["Name"] for d in m.distributions() if d.metadata["Name"].startswith("nvidia-") or d.metadata["Name"] == "triton"))')"; \
    if [ -n "$packages" ]; then "${VIRTUAL_ENV}/bin/pip" uninstall --yes $packages; fi; \
    fi

RUN mkdir -p /models/huggingface /models/torch

RUN if [ "$PRELOAD_MODELS" = "true" ]; then \
    python -c 'from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline; StandardPdfPipeline.download_models_hf(force=True);'; \
    fi

RUN if [ "$PRELOAD_MODELS" = "true" ]; then \
    CPU_ONLY="$CPU_ONLY" python -c 'import os, easyocr; gpu = os.environ.get("CPU_ONLY", "true").lower() != "true"; easyocr.Reader(["fr", "de", "es", "en", "it", "pt"], gpu=gpu); print("EasyOCR models downloaded successfully")'; \
    fi

FROM python:3.12-slim-bookworm AS runtime

ARG VIRTUAL_ENV=/opt/venv
ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/models/huggingface \
    TORCH_HOME=/models/torch \
    OMP_NUM_THREADS=4 \
    PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid "${APP_GID}" docling \
    && useradd --system --uid "${APP_UID}" --gid docling --home-dir /app --shell /usr/sbin/nologin docling \
    && mkdir -p /models/huggingface /models/torch \
    && chown -R docling:docling /app /models

COPY --from=builder "${VIRTUAL_ENV}" "${VIRTUAL_ENV}"
COPY --from=builder --chown=docling:docling /models /models
COPY --chown=docling:docling . .

USER docling

EXPOSE 8080

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "--port", "8080", "--host", "0.0.0.0", "main:app"]
