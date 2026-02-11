import os
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile

from document_converter.utils import is_file_format_supported, mb_to_bytes

load_dotenv()


def _read_upload_limit(name: str, default: int) -> int:
    limit = int(os.getenv(name, str(default)))
    if limit < 0:
        raise ValueError(f"{name} must be zero or greater")
    return limit


MAX_SIZE_PER_FILE_MB = _read_upload_limit("MAX_SIZE_PER_FILE_MB", 100)
MAX_BATCH_SIZE_MB = _read_upload_limit("MAX_BATCH_SIZE_MB", 500)


def _file_too_large_error() -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=f"File size exceeds the maximum allowed size of {MAX_SIZE_PER_FILE_MB} MB",
    )


def _batch_too_large_error() -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=f"Batch size exceeds the maximum allowed total size of {MAX_BATCH_SIZE_MB} MB",
    )


def _unsupported_format_error(filename: str) -> HTTPException:
    return HTTPException(status_code=400, detail=f"Unsupported file format: {filename}")


async def _read_document_with_limit(
    document: UploadFile,
    remaining_batch_bytes: Optional[int] = None,
) -> bytes:
    """Read no more than the configured limit plus one detection byte."""
    max_file_bytes = mb_to_bytes(MAX_SIZE_PER_FILE_MB)
    if document.size is not None:
        if document.size > max_file_bytes:
            raise _file_too_large_error()
        if remaining_batch_bytes is not None and document.size > remaining_batch_bytes:
            raise _batch_too_large_error()

    read_limit = max_file_bytes
    if remaining_batch_bytes is not None:
        read_limit = min(read_limit, remaining_batch_bytes)

    file_bytes = await document.read(read_limit + 1)
    if len(file_bytes) > max_file_bytes:
        raise _file_too_large_error()
    if remaining_batch_bytes is not None and len(file_bytes) > remaining_batch_bytes:
        raise _batch_too_large_error()

    return file_bytes


async def read_and_validate_document(document: UploadFile) -> Tuple[str, bytes]:
    file_bytes = await _read_document_with_limit(document)
    filename = document.filename or "unnamed"

    if not is_file_format_supported(file_bytes, filename):
        raise _unsupported_format_error(filename)

    return filename, file_bytes


async def read_and_validate_batch(documents: List[UploadFile]) -> List[Tuple[str, bytes]]:
    max_file_bytes = mb_to_bytes(MAX_SIZE_PER_FILE_MB)
    remaining_batch_bytes = mb_to_bytes(MAX_BATCH_SIZE_MB)
    known_sizes = [document.size for document in documents]

    if any(size is not None and size > max_file_bytes for size in known_sizes):
        raise _file_too_large_error()
    if all(size is not None for size in known_sizes) and sum(size or 0 for size in known_sizes) > remaining_batch_bytes:
        raise _batch_too_large_error()

    document_data = []
    for document in documents:
        file_bytes = await _read_document_with_limit(document, remaining_batch_bytes)
        filename = document.filename or "unnamed"
        document_data.append((filename, file_bytes))
        remaining_batch_bytes -= len(file_bytes)

    for filename, file_bytes in document_data:
        if not is_file_format_supported(file_bytes, filename):
            raise _unsupported_format_error(filename)

    return document_data
