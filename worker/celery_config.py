import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv(".env")

_broker_url = os.environ.get("CELERY_BROKER_URL") or os.environ.get("REDIS_HOST", "redis://localhost:6379/0")
_backend_url = os.environ.get("CELERY_RESULT_BACKEND") or os.environ.get("REDIS_HOST", "redis://localhost:6379/0")

celery_app = Celery(
    "document_converter",
    broker=_broker_url,
    backend=_backend_url,
    include=["worker.tasks"],
)
