from io import BytesIO
from multiprocessing.pool import AsyncResult
from typing import List
from fastapi import APIRouter, File, HTTPException, UploadFile, Query, Body
from pydantic import HttpUrl

from document_converter.schema import BatchConversionJobResult, ConversationJobResult, ConversionResult
from document_converter.service import DocumentConverterService, DoclingDocumentConversion
from document_converter.utils import is_file_format_supported
from worker.tasks import convert_document_task, convert_documents_task

router = APIRouter()

# Could be docling or another converter as long as it implements DocumentConversionBase
converter = DoclingDocumentConversion()
document_converter_service = DocumentConverterService(document_converter=converter)


# Document direct conversion endpoints
@router.post(
    '/documents/convert',
    response_model=ConversionResult,
    response_model_exclude_unset=True,
    description="Convert a single document synchronously",
)
async def convert_single_document(
    document: UploadFile = File(None),
    url: HttpUrl = Body(None),
    extract_tables_as_images: bool = False,
    image_resolution_scale: int = Query(4, ge=1, le=4),
):
    if document:
        file_bytes = await document.read()
        if not is_file_format_supported(file_bytes, document.filename):
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {document.filename}")
        doc_input = (document.filename, BytesIO(file_bytes))
    elif url:
        doc_input = str(url)
    else:
        raise HTTPException(status_code=400, detail="Either document or url must be provided")

    return document_converter_service.convert_document(
        doc_input,
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )


@router.post(
    '/documents/batch-convert',
    response_model=List[ConversionResult],
    response_model_exclude_unset=True,
    description="Convert multiple documents synchronously",
)
async def convert_multiple_documents(
    documents: List[UploadFile] = File(None),
    urls: List[HttpUrl] = Body(None),
    extract_tables_as_images: bool = False,
    image_resolution_scale: int = Query(4, ge=1, le=4),
):
    if documents:
        doc_inputs = []
        for document in documents:
            file_bytes = await document.read()
            if not is_file_format_supported(file_bytes, document.filename):
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {document.filename}")
            doc_inputs.append((document.filename, BytesIO(file_bytes)))
    elif urls:
        doc_inputs = [str(url) for url in urls]
    else:
        raise HTTPException(status_code=400, detail="Either documents or urls must be provided")

    return document_converter_service.convert_documents(
        doc_inputs,
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )


# Asynchronous conversion jobs endpoints
@router.post(
    '/conversion-jobs',
    response_model=ConversationJobResult,
    description="Create a conversion job for a single document",
)
async def create_single_document_conversion_job(
    document: UploadFile = File(None),
    url: HttpUrl = Body(None),
    extract_tables_as_images: bool = False,
    image_resolution_scale: int = Query(4, ge=1, le=4),
):
    if document:
        file_bytes = await document.read()
        if not is_file_format_supported(file_bytes, document.filename):
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {document.filename}")
        doc_input = (document.filename, file_bytes)
    elif url:
        doc_input = str(url)
    else:
        raise HTTPException(status_code=400, detail="Either document or url must be provided")

    task = convert_document_task.delay(
        doc_input,
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )

    return ConversationJobResult(job_id=task.id, status="IN_PROGRESS")


@router.get(
    '/conversion-jobs/{job_id}',
    response_model=ConversationJobResult,
    description="Get the status of a single document conversion job",
    response_model_exclude_unset=True,
)
async def get_conversion_job_status(job_id: str):
    return document_converter_service.get_single_document_task_result(job_id)


@router.post(
    '/batch-conversion-jobs',
    response_model=BatchConversionJobResult,
    response_model_exclude_unset=True,
    description="Create a conversion job for multiple documents",
)
async def create_batch_conversion_job(
    documents: List[UploadFile] = File(None),
    urls: List[HttpUrl] = Body(None),
    extract_tables_as_images: bool = False,
    image_resolution_scale: int = Query(4, ge=1, le=4),
):
    if documents:
        doc_inputs = []
        for document in documents:
            file_bytes = await document.read()
            if not is_file_format_supported(file_bytes, document.filename):
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {document.filename}")
            doc_inputs.append((document.filename, file_bytes))
    elif urls:
        doc_inputs = [str(url) for url in urls]
    else:
        raise HTTPException(status_code=400, detail="Either documents or urls must be provided")

    task = convert_documents_task.delay(
        doc_inputs,
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )

    return BatchConversionJobResult(job_id=task.id, status="IN_PROGRESS")


@router.get(
    '/batch-conversion-jobs/{job_id}',
    response_model=BatchConversionJobResult,
    response_model_exclude_unset=True,
    description="Get the status of a batch conversion job",
)
async def get_batch_conversion_job_status(job_id: str):
    """Get the status and results of a batch conversion job."""
    return document_converter_service.get_batch_conversion_task_result(job_id)
