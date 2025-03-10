# Variables
PYTHON = poetry run
DOCKER_CPU_COMPOSE = docker-compose -f docker-compose.cpu.yml
DOCKER_GPU_COMPOSE = docker-compose -f docker-compose.gpu.yml
DOCKER_IMAGE = docling-api
PORT = 8080
WORKERS = 4

.PHONY: help install dev-setup start stop clean docker-* test lint format

help:
	@echo "Available commands:"
	@echo "Development:"
	@echo "  install         - Install project dependencies using Poetry"
	@echo "  dev-setup      - Setup development environment (install Redis, etc.)"
	@echo "  start          - Start all development services locally"
	@echo "  stop           - Stop all development services"
	@echo "  clean          - Clean up temporary files and caches"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build-cpu   - Build Docker image (CPU version)"
	@echo "  docker-build-gpu   - Build Docker image (GPU version)"
	@echo "  docker-start       - Auto-detect system and start appropriate container (CPU/GPU)"
	@echo "  docker-start-cpu   - Start services in CPU mode"
	@echo "  docker-start-gpu   - Start services in GPU mode"
	@echo "  docker-stop        - Stop all Docker services"
	@echo "  docker-clean       - Clean Docker resources"
	@echo ""
	@echo "Code Quality:"
	@echo "  format         - Format code using black"
	@echo "  lint           - Run linter"
	@echo "  test           - Run tests"

# Development commands
install:
	curl -sSL https://install.python-poetry.org | python3 -
	poetry install

dev-setup:
	@echo "Setting up development environment..."
	@if [ "$(shell uname)" = "Darwin" ]; then \
		brew install redis; \
		brew services start redis; \
	elif [ -f /etc/debian_version ]; then \
		sudo apt-get update && sudo apt-get install -y redis-server; \
		sudo service redis-server start; \
	fi
	@echo "Creating .env file..."
	@echo "REDIS_HOST=redis://localhost:6379/0" > .env
	@echo "ENV=development" >> .env

start:
	@echo "Starting FastAPI server..."
	$(PYTHON) uvicorn main:app --reload --port $(PORT) & \
	echo "Starting Celery worker..." && \
	$(PYTHON) celery -A worker.celery_config worker --pool=solo -n worker_primary --loglevel=info & \
	echo "Starting Flower dashboard..." && \
	$(PYTHON) celery -A worker.celery_config flower --port=5555

stop:
	@echo "Stopping services..."
	@pkill -f "uvicorn main:app" || true
	@pkill -f "celery" || true
	@if [ "$(shell uname)" = "Darwin" ]; then \
		brew services stop redis; \
	elif [ -f /etc/debian_version ]; then \
		sudo service redis-server stop; \
	fi

# Docker commands
docker-build-cpu:
	docker build --build-arg CPU_ONLY=true -t $(DOCKER_IMAGE):cpu .

docker-build-gpu:
	docker build -t $(DOCKER_IMAGE):gpu .

docker-start-cpu:
	$(DOCKER_CPU_COMPOSE) up --build --scale celery_worker=1

docker-start-gpu:
	$(DOCKER_GPU_COMPOSE) up --build --scale celery_worker=3

# Auto-detect architecture and start appropriate container
docker-start:
	@echo "Auto-detecting system architecture..."
	@if [ "$(shell uname -m)" = "arm64" ] || [ "$(shell uname -m)" = "aarch64" ] || ! command -v nvidia-smi >/dev/null 2>&1; then \
		echo "ARM architecture or NVIDIA drivers not detected. Using CPU mode."; \
		$(MAKE) docker-start-cpu; \
	else \
		echo "NVIDIA GPU detected. Using GPU mode."; \
		$(MAKE) docker-start-gpu; \
	fi

docker-stop:
	$(DOCKER_CPU_COMPOSE) down
	$(DOCKER_GPU_COMPOSE) down

docker-clean:
	docker system prune -f
	docker volume prune -f

# Code quality commands
format:
	$(PYTHON) black .

lint:
	$(PYTHON) flake8 .
	$(PYTHON) mypy .

test:
	$(PYTHON) pytest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".tox" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} + 