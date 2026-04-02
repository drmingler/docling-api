from io import BytesIO
from typing import List

from fastapi import APIRouter, File, Query, UploadFile

from document_converter.schema import (
    BatchConversionJobResult,
    ConversationJobResult,
    ConversionResult,
)
from document_converter.service import (
    MAX_IMAGE_RESOLUTION_SCALE,
    MIN_IMAGE_RESOLUTION_SCALE,
    DocumentConverterService,
    DoclingDocumentConversion,
)
from document_converter.upload_validation import read_and_validate_batch, read_and_validate_document
from worker.tasks import convert_document_task, convert_documents_task

router = APIRouter()

# Could be docling or another converter as long as it implements DocumentConversionBase.
# Options are copied per-request inside DoclingDocumentConversion, so this is safe to share.
converter = DoclingDocumentConversion()
document_converter_service = DocumentConverterService(document_converter=converter)


def _image_resolution_scale_query() -> int:
    return Query(
        MAX_IMAGE_RESOLUTION_SCALE,
        ge=MIN_IMAGE_RESOLUTION_SCALE,
        le=MAX_IMAGE_RESOLUTION_SCALE,
        description="Resolution scale applied to extracted images.",
    )


# Document direct conversion endpoints
@router.post(
    "/documents/convert",
    response_model=ConversionResult,
    response_model_exclude_unset=True,
    description="Convert a single document synchronously.",
)
async def convert_single_document(
    document: UploadFile = File(...),
    extract_tables_as_images: bool = False,
    image_resolution_scale: int = Query(
        MAX_IMAGE_RESOLUTION_SCALE,
        ge=MIN_IMAGE_RESOLUTION_SCALE,
        le=MAX_IMAGE_RESOLUTION_SCALE,
    ),
):
    filename, file_bytes = await read_and_validate_document(document)

    return document_converter_service.convert_document(
        (filename, BytesIO(file_bytes)),
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )


@router.post(
    "/documents/batch-convert",
    response_model=List[ConversionResult],
    response_model_exclude_unset=True,
    description="Convert multiple documents synchronously.",
)
async def convert_multiple_documents(
    documents: List[UploadFile] = File(...),
    extract_tables_as_images: bool = False,
    image_resolution_scale: int = Query(
        MAX_IMAGE_RESOLUTION_SCALE,
        ge=MIN_IMAGE_RESOLUTION_SCALE,
        le=MAX_IMAGE_RESOLUTION_SCALE,
    ),
):
    document_data = await read_and_validate_batch(documents)
    doc_streams = [(filename, BytesIO(file_bytes)) for filename, file_bytes in document_data]

    return document_converter_service.convert_documents(
        doc_streams,
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )


# Asynchronous conversion jobs endpoints
@router.post(
    "/conversion-jobs",
    response_model=ConversationJobResult,
    description="Create a conversion job for a single document.",
)
async def create_single_document_conversion_job(
    document: UploadFile = File(...),
    extract_tables_as_images: bool = False,
    image_resolution_scale: int = Query(
        MAX_IMAGE_RESOLUTION_SCALE,
        ge=MIN_IMAGE_RESOLUTION_SCALE,
        le=MAX_IMAGE_RESOLUTION_SCALE,
    ),
):
    filename, file_bytes = await read_and_validate_document(document)

    task = convert_document_task.delay(
        (filename, file_bytes),
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )

    return ConversationJobResult(job_id=task.id, status="IN_PROGRESS")


@router.get(
    "/conversion-jobs/{job_id}",
    response_model=ConversationJobResult,
    description="Get the status of a single document conversion job.",
    response_model_exclude_unset=True,
)
async def get_conversion_job_status(job_id: str):
    return document_converter_service.get_single_document_task_result(job_id)


@router.post(
    "/batch-conversion-jobs",
    response_model=BatchConversionJobResult,
    response_model_exclude_unset=True,
    description="Create a conversion job for multiple documents.",
)
async def create_batch_conversion_job(
    documents: List[UploadFile] = File(...),
    extract_tables_as_images: bool = False,
    image_resolution_scale: int = Query(
        MAX_IMAGE_RESOLUTION_SCALE,
        ge=MIN_IMAGE_RESOLUTION_SCALE,
        le=MAX_IMAGE_RESOLUTION_SCALE,
    ),
):
    doc_data = await read_and_validate_batch(documents)

    task = convert_documents_task.delay(
        doc_data,
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )

    return BatchConversionJobResult(job_id=task.id, status="IN_PROGRESS")


@router.get(
    "/batch-conversion-jobs/{job_id}",
    response_model=BatchConversionJobResult,
    response_model_exclude_unset=True,
    description="Get the status of a batch conversion job.",
)
async def get_batch_conversion_job_status(job_id: str):
    return document_converter_service.get_batch_conversion_task_result(job_id)
