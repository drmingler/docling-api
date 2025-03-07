from pydantic import BaseModel, Field, constr
from typing import List, Literal, Optional, Dict, Any
from enum import Enum


class JobStatus(str, Enum):
    """Enum for job processing status"""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class ImageType(str, Enum):
    """Enum for image types"""
    TABLE = "table"
    PICTURE = "picture"


class ImageData(BaseModel):
    """Schema for image data extracted from documents"""
    type: Optional[ImageType] = Field(
        None, 
        description="The type of the image (table or picture)"
    )
    filename: Optional[constr(min_length=1)] = Field(
        None, 
        description="The filename of the image with extension",
        example="table_1.png"
    )
    image: Optional[str] = Field(
        None, 
        description="Base64 encoded image data",
        example="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgA..."
    )


class ConversionResult(BaseModel):
    """Schema for document conversion result"""
    filename: constr(min_length=1) = Field(
        ...,
        description="The original filename of the converted document",
        example="document.pdf"
    )
    markdown: str = Field(
        ...,
        description="The markdown content extracted from the document",
        example="# Document Title\n\nContent here..."
    )
    images: List[ImageData] = Field(
        default_factory=list,
        description="List of images extracted from the document"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if conversion failed",
        example="Failed to process page 3: Invalid format"
    )


class BatchConversionResult(BaseModel):
    """Schema for batch document conversion results"""
    conversion_results: List[ConversionResult] = Field(
        default_factory=list,
        description="List of conversion results for each document in the batch"
    )


class ConversationJobResult(BaseModel):
    """Schema for single document conversion job result"""
    job_id: constr(min_length=1) = Field(
        ...,
        description="Unique identifier for the conversion job",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    result: Optional[ConversionResult] = Field(
        None,
        description="The conversion result when job is completed successfully"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if job failed",
        example="Document processing timed out"
    )
    status: JobStatus = Field(
        ...,
        description="Current status of the conversion job"
    )


class BatchConversionJobResult(BaseModel):
    """Schema for batch conversion job result"""
    job_id: constr(min_length=1) = Field(
        ...,
        description="Unique identifier for the batch conversion job",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    conversion_results: List[ConversationJobResult] = Field(
        default_factory=list,
        description="List of conversion job results for each document"
    )
    status: JobStatus = Field(
        ...,
        description="Overall status of the batch conversion job"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if the entire batch job failed",
        example="Failed to process batch: Queue is full"
    )


# Response Examples
class ResponseExamples:
    """Collection of response examples for API documentation"""
    
    @staticmethod
    def single_job_responses() -> Dict[int, Dict[str, Any]]:
        return {
            200: {
                "description": "Job completed (success or failure)",
                "content": {
                    "application/json": {
                        "examples": {
                            "success": {
                                "summary": "Successful conversion",
                                "value": {
                                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "status": JobStatus.SUCCESS,
                                    "result": {
                                        "filename": "document.pdf",
                                        "markdown": "# Document Title\n\nContent here...",
                                        "images": []
                                    }
                                }
                            },
                            "failure": {
                                "summary": "Failed conversion",
                                "value": {
                                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "status": JobStatus.FAILURE,
                                    "error": "Document processing failed"
                                }
                            }
                        }
                    }
                }
            },
            202: {
                "description": "Job is still in progress",
                "content": {
                    "application/json": {
                        "example": {
                            "job_id": "550e8400-e29b-41d4-a716-446655440000",
                            "status": JobStatus.PROCESSING
                        }
                    }
                }
            },
            404: {"description": "Job not found"},
            500: {"description": "Error retrieving job status"}
        }

    @staticmethod
    def batch_job_responses() -> Dict[int, Dict[str, Any]]:
        return {
            200: {
                "description": "Batch job completed (success or failure)",
                "content": {
                    "application/json": {
                        "examples": {
                            "success": {
                                "summary": "Successful batch conversion",
                                "value": {
                                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "status": JobStatus.SUCCESS,
                                    "conversion_results": [
                                        {
                                            "job_id": "sub-job-1",
                                            "status": JobStatus.SUCCESS,
                                            "result": {
                                                "filename": "document1.pdf",
                                                "markdown": "# Document 1\n\nContent here..."
                                            }
                                        }
                                    ]
                                }
                            },
                            "failure": {
                                "summary": "Failed batch conversion",
                                "value": {
                                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "status": JobStatus.FAILURE,
                                    "error": "Batch processing failed",
                                    "conversion_results": []
                                }
                            }
                        }
                    }
                }
            },
            202: {
                "description": "Batch job is still in progress",
                "content": {
                    "application/json": {
                        "example": {
                            "job_id": "550e8400-e29b-41d4-a716-446655440000",
                            "status": JobStatus.PROCESSING,
                            "conversion_results": [
                                {
                                    "job_id": "sub-job-1",
                                    "status": JobStatus.SUCCESS
                                },
                                {
                                    "job_id": "sub-job-2",
                                    "status": JobStatus.PROCESSING
                                }
                            ]
                        }
                    }
                }
            },
            404: {"description": "Batch job not found"},
            500: {"description": "Error retrieving batch job status"}
        }

    @staticmethod
    def health_check_responses() -> Dict[int, Dict[str, Any]]:
        return {
            200: {
                "description": "All services are healthy",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "healthy",
                            "services": {
                                "celery": "connected",
                                "redis": "connected",
                                "docling": "connected",
                                "document_converter": "connected"
                            }
                        }
                    }
                }
            },
            500: {
                "description": "One or more services are unhealthy",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "unhealthy",
                            "detail": "Celery/Redis connection test failed",
                            "services": {
                                "celery": "unknown",
                                "redis": "unknown",
                                "docling": "unknown",
                                "document_converter": "unknown"
                            }
                        }
                    }
                }
            }
        }
