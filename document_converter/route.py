from io import BytesIO
from typing import List
from fastapi import APIRouter, File, HTTPException, UploadFile, Query, status
from fastapi.responses import JSONResponse

from document_converter.schema import (
    BatchConversionJobResult,
    ConversationJobResult,
    ConversionResult,
    JobStatus,
    ResponseExamples
)
from document_converter.service import DocumentConverterService, DoclingDocumentConversion
from document_converter.utils import is_file_format_supported
from worker.tasks import convert_document_task, convert_documents_task, ping

router = APIRouter()

# Could be docling or another converter as long as it implements DocumentConversionBase
converter = DoclingDocumentConversion()
document_converter_service = DocumentConverterService(document_converter=converter)


# Document direct conversion endpoints
@router.post(
    '/documents/convert',
    response_model=ConversionResult,
    response_model_exclude_unset=True,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Document successfully converted"},
        400: {"description": "Invalid request or unsupported file format"},
        500: {"description": "Internal server error during conversion"}
    },
    description="Convert a single document synchronously",
)
async def convert_single_document(
    document: UploadFile = File(..., description="The document file to convert"),
    extract_tables_as_images: bool = Query(
        False,
        description="Whether to extract tables as images"
    ),
    image_resolution_scale: int = Query(
        4,
        ge=1,
        le=4,
        description="Scale factor for image resolution (1-4)"
    ),
):
    file_bytes = await document.read()
    if not is_file_format_supported(file_bytes, document.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {document.filename}"
        )

    return document_converter_service.convert_document(
        (document.filename, BytesIO(file_bytes)),
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )


@router.post(
    '/documents/batch-convert',
    response_model=List[ConversionResult],
    response_model_exclude_unset=True,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "All documents successfully converted"},
        400: {"description": "Invalid request or unsupported file format"},
        500: {"description": "Internal server error during conversion"}
    },
    description="Convert multiple documents synchronously",
)
async def convert_multiple_documents(
    documents: List[UploadFile] = File(..., description="List of document files to convert"),
    extract_tables_as_images: bool = Query(
        False,
        description="Whether to extract tables as images"
    ),
    image_resolution_scale: int = Query(
        4,
        ge=1,
        le=4,
        description="Scale factor for image resolution (1-4)"
    ),
):
    doc_streams = []
    for document in documents:
        file_bytes = await document.read()
        if not is_file_format_supported(file_bytes, document.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: {document.filename}"
            )
        doc_streams.append((document.filename, BytesIO(file_bytes)))

    return document_converter_service.convert_documents(
        doc_streams,
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )


# Asynchronous conversion jobs endpoints
@router.post(
    '/conversion-jobs',
    response_model=ConversationJobResult,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Conversion job accepted and queued"},
        400: {"description": "Invalid request or unsupported file format"},
        500: {"description": "Failed to queue conversion job"}
    },
    description="Create an asynchronous conversion job for a single document",
)
async def create_single_document_conversion_job(
    document: UploadFile = File(..., description="The document file to convert"),
    extract_tables_as_images: bool = Query(
        False,
        description="Whether to extract tables as images"
    ),
    image_resolution_scale: int = Query(
        4,
        ge=1,
        le=4,
        description="Scale factor for image resolution (1-4)"
    ),
):
    file_bytes = await document.read()
    if not is_file_format_supported(file_bytes, document.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {document.filename}"
        )

    task = convert_document_task.delay(
        (document.filename, file_bytes),
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )

    return ConversationJobResult(
        job_id=task.id,
        status=JobStatus.QUEUED
    )


@router.get(
    '/conversion-jobs/{job_id}',
    response_model=ConversationJobResult,
    responses=ResponseExamples.single_job_responses(),
    description="Get the status and result of a single document conversion job",
)
async def get_conversion_job_status(job_id: str):
    try:
        result = document_converter_service.get_single_document_task_result(job_id)
        
        # Return 202 Accepted if job is still in progress
        if result.status in [JobStatus.QUEUED, JobStatus.PROCESSING]:
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content=result.dict(exclude_none=True)
            )
            
        # Return 200 OK for completed jobs (success or failure)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=result.dict(exclude_none=True)
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )


@router.post(
    '/batch-conversion-jobs',
    response_model=BatchConversionJobResult,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Batch conversion job accepted and queued"},
        400: {"description": "Invalid request or unsupported file format"},
        500: {"description": "Failed to queue batch conversion job"}
    },
    description="Create an asynchronous conversion job for multiple documents",
)
async def create_batch_conversion_job(
    documents: List[UploadFile] = File(..., description="List of document files to convert"),
    extract_tables_as_images: bool = Query(
        False,
        description="Whether to extract tables as images"
    ),
    image_resolution_scale: int = Query(
        4,
        ge=1,
        le=4,
        description="Scale factor for image resolution (1-4)"
    ),
):
    doc_data = []
    for document in documents:
        file_bytes = await document.read()
        if not is_file_format_supported(file_bytes, document.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: {document.filename}"
            )
        doc_data.append((document.filename, file_bytes))

    task = convert_documents_task.delay(
        doc_data,
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
    )

    return BatchConversionJobResult(
        job_id=task.id,
        status=JobStatus.QUEUED
    )


@router.get(
    '/batch-conversion-jobs/{job_id}',
    response_model=BatchConversionJobResult,
    responses=ResponseExamples.batch_job_responses(),
    description="Get the status and results of a batch conversion job",
)
async def get_batch_conversion_job_status(job_id: str):
    try:
        result = document_converter_service.get_batch_conversion_task_result(job_id)
        
        # Return 202 Accepted if the batch job or any sub-job is still in progress
        if result.status in [JobStatus.QUEUED, JobStatus.PROCESSING] or any(
            job.status in [JobStatus.QUEUED, JobStatus.PROCESSING]
            for job in result.conversion_results
        ):
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content=result.dict(exclude_none=True)
            )
            
        # Return 200 OK for completed batch jobs (all success or some failures)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=result.dict(exclude_none=True)
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch job not found: {job_id}"
        )


@router.get(
    "/health",
    responses=ResponseExamples.health_check_responses(),
    description="Check the health status of all dependent services"
)
async def health_check():
    try:
        # Check Celery/Redis connection by sending a ping task
        result = ping.delay()
        response = result.get(timeout=3)  # Wait up to 3 seconds for response
        
        if response != "pong":
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "unhealthy",
                    "detail": "Celery/Redis connection test failed"
                }
            )
            
        return {
            "status": "healthy",
            "services": {
                "celery": "connected",
                "redis": "connected",
                "docling": "connected",
                "document_converter": "connected",
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "unhealthy",
                "detail": str(e),
                "services": {
                    "celery": "unknown",
                    "redis": "unknown",
                    "docling": "unknown",
                    "document_converter": "unknown",
                }
            }
        )