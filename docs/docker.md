# Running Docling API with Docker

This guide runs the FastAPI app, a Celery worker, Redis, and the Flower dashboard with Docker Compose.

The application image uses a multi-stage Docker build. Python dependencies and optional model downloads are prepared in a builder stage, while the final runtime image contains only the virtual environment, application code, runtime system libraries, and a non-root `docling` user. Compose also runs the app containers with `no-new-privileges` enabled and an API healthcheck.

## Prerequisites

- Docker Engine with Docker Compose v2.
- At least 8 GB RAM available to Docker for CPU mode.
- For GPU mode, install the NVIDIA driver and NVIDIA Container Toolkit on the host.

## Services

| Service | URL | Purpose |
| --- | --- | --- |
| API | http://localhost:8080 | FastAPI document conversion API |
| API docs | http://localhost:8080/docs | Interactive OpenAPI documentation |
| Redis | localhost:6379 | Celery broker and result backend |
| Flower | http://localhost:5556 | Celery worker monitoring |

## CPU mode

1. Clone the repository.

```bash
git clone https://github.com/drmingler/docling-api.git
cd docling-api
```

2. Build and start the stack.

```bash
docker compose up --build
```

The default `docker-compose.yml` is CPU-only. It builds the app image, starts Redis, starts one Celery worker, and exposes the API on port `8080`.

3. Scale workers when needed.

```bash
docker compose up --build --scale celery_worker=2
```

4. Stop the stack.

```bash
docker compose down
```

## GPU mode

1. Confirm Docker can access the GPU.

```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

2. Build and start the GPU stack.

```bash
docker compose -f docker-compose.gpu.yml up --build
```

3. Scale GPU workers if the host has enough GPU memory.

```bash
docker compose -f docker-compose.gpu.yml up --build --scale celery_worker=3
```

## Existing CPU compose file

The repository also includes `docker-compose.cpu.yml`. It is equivalent to the default compose file and can be used explicitly:

```bash
docker compose -f docker-compose.cpu.yml up --build
```

## Verify the API

1. Open the API docs:

```bash
curl http://localhost:8080/docs
```

2. Convert one document synchronously:

```bash
curl -X POST "http://localhost:8080/documents/convert" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "document=@/path/to/document.pdf" \
  -F "extract_tables_as_images=true" \
  -F "image_resolution_scale=4"
```

3. Submit one document asynchronously:

```bash
curl -X POST "http://localhost:8080/conversion-jobs" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "document=@/path/to/document.pdf"
```

4. Check the asynchronous job status. Replace `{job_id}` with the returned job id.

```bash
curl -X GET "http://localhost:8080/conversion-jobs/{job_id}" \
  -H "accept: application/json"
```

## Configuration

The Compose files set `REDIS_HOST=redis://redis:6379/0` for the API, worker, and Flower containers. Use a `.env` file only when you need to override values for a custom deployment.

The Docker image accepts these build arguments:

| Argument | Default | Description |
| --- | --- | --- |
| `CPU_ONLY` | `true` | Installs CPU PyTorch wheels when `true`; installs CUDA wheels when `false`. |
| `PRELOAD_MODELS` | `true` | Downloads Docling and EasyOCR model files during image build. |
| `POETRY_VERSION` | `1.8.4` | Poetry version used only in the builder stage. |
| `APP_UID` | `10001` | Runtime user id for the non-root `docling` user. |
| `APP_GID` | `10001` | Runtime group id for the non-root `docling` group. |

Example without preloading models:

```bash
docker compose build --build-arg PRELOAD_MODELS=false
docker compose up
```

Model caches are stored in the `model_cache` Docker volume and mounted at `/models` in the app, worker, and Flower containers.

## Troubleshooting

- If port `8080`, `5556`, or `6379` is already in use, update the host-side port in the compose file.
- The first build can take several minutes because PyTorch, Docling, and OCR model dependencies are large.
- If GPU containers cannot see the GPU, reinstall or reconfigure the NVIDIA Container Toolkit and rerun the `nvidia-smi` Docker test above.
- To remove containers and cached model volume data, run:

```bash
docker compose down -v
```
