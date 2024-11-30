from typing import Any, Dict, List, Tuple, Union
from document_converter.service import IMAGE_RESOLUTION_SCALE, DoclingDocumentConversion, DocumentConverterService
from worker.celery_config import celery_app


@celery_app.task(name="celery.ping")
def ping():
    print("Ping task received!")  # or use a logger
    return "pong"


@celery_app.task(bind=True, name="convert_document")
def convert_document_task(
    self,
    document: Union[Tuple[str, bytes], str],
    extract_tables: bool = False,
    image_resolution_scale: int = IMAGE_RESOLUTION_SCALE,
) -> Dict[str, Any]:
    document_service = DocumentConverterService(document_converter=DoclingDocumentConversion())
    result = document_service.convert_document_task(
        document, extract_tables=extract_tables, image_resolution_scale=image_resolution_scale
    )
    return result.model_dump(exclude_unset=True)


@celery_app.task(bind=True, name="convert_documents")
def convert_documents_task(
    self,
    documents: List[Union[Tuple[str, bytes], str]],
    extract_tables: bool = False,
    image_resolution_scale: int = IMAGE_RESOLUTION_SCALE,
) -> List[Dict[str, Any]]:
    document_service = DocumentConverterService(document_converter=DoclingDocumentConversion())
    results = document_service.convert_documents_task(
        documents, extract_tables=extract_tables, image_resolution_scale=image_resolution_scale
    )
    return [result.model_dump(exclude_unset=True) for result in results]
