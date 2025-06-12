# Documents to Markdown Converter Server

> [!IMPORTANT]
> This backend server is a robust, scalable solution for effortlessly converting a wide range of document formats—including PDF, DOCX, PPTX, CSV, HTML, JPG, PNG, TIFF, BMP, AsciiDoc, and Markdown—into Markdown. Powered by [Docling](https://github.com/DS4SD/docling) (IBM's advanced document parser), this service is built with FastAPI, Celery, and Redis, ensuring fast, efficient processing. Optimized for both CPU and GPU modes, with GPU highly recommended for production environments, this solution offers high performance and flexibility, making it ideal for handling complex document processing at scale.

## Comparison to Other Parsing Libraries

| Original PDF |
|--------------|
| <img src="https://raw.githubusercontent.com/drmingler/docling-api/refs/heads/main/images/original.png" width="500"/> |

| Docling-API | Marker |
|-------------|--------|
| <img src="https://raw.githubusercontent.com/drmingler/docling-api/refs/heads/main/images/docling.png" width="500"/> | <img src="https://raw.githubusercontent.com/drmingler/docling-api/refs/heads/main/images/marker.png" width="500"/> |

| PyPDF | PyMuPDF4LLM |
|-------|-------------|
| <img src="https://raw.githubusercontent.com/drmingler/docling-api/refs/heads/main/images/pypdf.png" width="500"/> | <img src="https://raw.githubusercontent.com/drmingler/docling-api/refs/heads/main/images/pymupdf.png" width="500"/> |

## Features
- **Multiple Format Support**: Converts various document types including:
  - PDF files
  - Microsoft Word documents (DOCX)
  - PowerPoint presentations (PPTX)
  - HTML files
  - Images (JPG, PNG, TIFF, BMP)
  - AsciiDoc files
  - Markdown files
  - CSV files

- **Conversion Capabilities**:
  - Text extraction and formatting
  - Table detection, extraction and conversion
  - Image extraction and processing
  - Multi-language OCR support (French, German, Spanish, English, Italian, Portuguese etc)
  - Configurable image resolution scaling

- **API Endpoints**:
  - Synchronous single document conversion
  - Synchronous batch document conversion
  - Asynchronous single document conversion with job tracking
  - Asynchronous batch conversion with job tracking

- **Processing Modes**:
  - CPU-only processing for standard deployments
  - GPU-accelerated processing for improved performance
  - Distributed task processing using Celery
  - Task monitoring through Flower dashboard

## Environment Setup (Running Locally)

### Prerequisites
- Python 3.12 or higher
- Poetry (Python package manager)
- Redis server (for task queue)

### 1. Install Poetry (if not already installed)
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Clone and Setup Project
```bash
git clone https://github.com/drmingler/docling-api.git
cd docling-api
poetry install
```

### 3. Configure Environment
Create a `.env` file in the project root:
```bash
REDIS_HOST=redis://localhost:6379/0
ENV=development
MAX_SIZE_PER_FILE_MB=100
MAX_BATCH_SIZE_MB=500
```

### 4. Start Redis Server
Start Redis locally (install if not already installed):

#### For MacOS:
```bash
brew install redis
brew services start redis
```

#### For Ubuntu/Debian:
```bash
sudo apt-get install redis-server
sudo service redis-server start
```

### 5. Start the Application Components

1. Start the FastAPI server:
```bash
poetry run uvicorn main:app --reload --port 8080
```

2. Start Celery worker (in a new terminal):
```bash
poetry run celery -A worker.celery_config worker --pool=solo -n worker_primary --loglevel=info
```

3. Start Flower dashboard for monitoring (optional, in a new terminal):
```bash
poetry run celery -A worker.celery_config flower --port=5555
```

### 6. Verify Installation

1. Check if the API server is running:
```bash
curl http://localhost:8080/health
```

2. Test Celery worker:
```bash
curl -X POST "http://localhost:8080/documents/convert" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "document=@/path/to/test.pdf"
```

3. Access monitoring dashboard:
- Open http://localhost:5555 in your browser to view the Flower dashboard

### Development Notes

- The API documentation is available at http://localhost:8080/docs
- Redis is used as both message broker and result backend for Celery tasks
- The service supports both synchronous and asynchronous document conversion
- For development, the server runs with auto-reload enabled

## Environment Setup (Running in Docker)

For detailed Docker instructions, including CPU mode, GPU mode, service URLs, verification commands, configuration, and troubleshooting, see [docs/docker.md](docs/docker.md).

1. Clone the repository:
```bash
git clone https://github.com/drmingler/docling-api.git
cd docling-api
```

2. Optional: create a `.env` file if you need to override the default Docker Redis connection:
```bash
REDIS_HOST=redis://redis:6379/0
ENV=production
MAX_SIZE_PER_FILE_MB=100
MAX_BATCH_SIZE_MB=500
```

### CPU Mode
To start the service using CPU-only processing, use the following command. You can adjust the number of Celery workers by specifying the --scale option. In this example, 1 worker will be created:
```bash
docker compose up --build --scale celery_worker=1
```

### GPU Mode (Recommend for production)
For production, it is recommended to enable GPU acceleration, as it significantly improves performance. Use the command below to start the service with GPU support. You can also scale the number of Celery workers using the --scale option; here, 3 workers will be launched:
```bash
docker compose -f docker-compose.gpu.yml up --build --scale celery_worker=3
```

## Service Components

The service will start the following components:

- **API Server**: http://localhost:8080
- **Redis**: http://localhost:6379
- **Flower Dashboard**: http://localhost:5556

## API Usage

### Synchronous Conversion

Convert a single document immediately:

```bash
curl -X POST "http://localhost:8080/documents/convert" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "document=@/path/to/document.pdf" \
  -F "extract_tables_as_images=true" \
  -F "image_resolution_scale=4"
```

### Asynchronous Conversion

1. Submit a document for conversion:

```bash
curl -X POST "http://localhost:8080/conversion-jobs" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "document=@/path/to/document.pdf"
```

2. Check conversion status:

```bash
curl -X GET "http://localhost:8080/conversion-jobs/{job_id}" \
  -H "accept: application/json"
```

### Batch Processing

Convert multiple documents asynchronously:

```bash
curl -X POST "http://localhost:8080/batch-conversion-jobs" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "documents=@/path/to/document1.pdf" \
  -F "documents=@/path/to/document2.pdf"
```

## Configuration Options

- `image_resolution_scale`: Control the resolution of extracted images (1-4)
- `extract_tables_as_images`: Extract tables as images (true/false)
- `CPU_ONLY`: Build argument to switch between CPU/GPU modes
- `MAX_SIZE_PER_FILE_MB`: Maximum size of each uploaded file in MB (default: `100`)
- `MAX_BATCH_SIZE_MB`: Maximum combined size of files in a batch upload in MB (default: `500`)
- `CORS_ALLOW_ORIGINS`: Comma-separated list of allowed origins (default: `*`). Credentials are only sent when explicit origins are configured.
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`: Optional explicit Celery URLs. If unset, both fall back to `REDIS_HOST`.

## Health

- `GET /health` — liveness probe. Returns `200 {"status": "ok"}` when the API process is up.
- `GET /health/ready` — readiness probe. Reports whether the Celery broker connection is reachable.

The limits apply to both synchronous conversions and asynchronous conversion jobs. Uploads over either limit return `413 Payload Too Large`.

## Monitoring

- Access the Flower dashboard to monitor Celery tasks and workers
- View task status, success/failure rates, and worker performance
- Monitor resource usage and task queues

## Architecture

The service uses a distributed architecture with the following components:

1. FastAPI application serving the REST API
2. Celery workers for distributed task processing
3. Redis as message broker and result backend
4. Flower for task monitoring and management
5. Docling for the file conversion

## Performance Considerations

- GPU mode provides significantly faster processing for large documents
- CPU mode is suitable for smaller deployments or when GPU is not available
- Multiple workers can be scaled horizontally for increased throughput

## License
The codebase is under MIT license. See LICENSE for more information

## Acknowledgements
- [Docling](https://github.com/DS4SD/docling) the state-of-the-art document conversion library by IBM
- [FastAPI](https://fastapi.tiangolo.com/) the web framework
- [Celery](https://docs.celeryq.dev/en/stable/) for distributed task processing
- [Flower](https://flower.readthedocs.io/en/latest/) for monitoring and management
