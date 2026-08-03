import unittest
from unittest.mock import patch

from fastapi import HTTPException

from document_converter import route, upload_validation


class FakeUploadFile:
    def __init__(self, content: bytes, filename: str = "document.pdf", size=None):
        self.content = content
        self.filename = filename
        self.size = size
        self.read_sizes = []

    async def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return self.content if size < 0 else self.content[:size]


class UploadLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_file_limit_is_enforced_on_both_endpoints_with_bounded_reads(self):
        endpoints = (
            route.convert_single_document,
            route.create_single_document_conversion_job,
        )

        with (
            patch.object(upload_validation, "MAX_SIZE_PER_FILE_MB", 4),
            patch.object(upload_validation, "mb_to_bytes", side_effect=lambda value: value),
        ):
            for endpoint in endpoints:
                with self.subTest(endpoint=endpoint.__name__):
                    document = FakeUploadFile(b"12345")

                    with self.assertRaises(HTTPException) as context:
                        await endpoint(document=document, image_resolution_scale=4)

                    self.assertEqual(context.exception.status_code, 413)
                    self.assertIn("File size exceeds", context.exception.detail)
                    self.assertEqual(document.read_sizes, [5])

    async def test_batch_total_limit_is_enforced_on_both_endpoints_with_bounded_reads(self):
        endpoints = (
            route.convert_multiple_documents,
            route.create_batch_conversion_job,
        )

        with (
            patch.object(upload_validation, "MAX_SIZE_PER_FILE_MB", 10),
            patch.object(upload_validation, "MAX_BATCH_SIZE_MB", 6),
            patch.object(upload_validation, "mb_to_bytes", side_effect=lambda value: value),
        ):
            for endpoint in endpoints:
                with self.subTest(endpoint=endpoint.__name__):
                    first = FakeUploadFile(b"123", filename="first.pdf")
                    second = FakeUploadFile(b"4567", filename="second.pdf")

                    with self.assertRaises(HTTPException) as context:
                        await endpoint(
                            documents=[first, second],
                            image_resolution_scale=4,
                        )

                    self.assertEqual(context.exception.status_code, 413)
                    self.assertIn("Batch size exceeds", context.exception.detail)
                    self.assertEqual(first.read_sizes, [7])
                    self.assertEqual(second.read_sizes, [4])

    async def test_known_oversized_batch_is_rejected_before_any_file_is_read(self):
        documents = [
            FakeUploadFile(b"123", size=3),
            FakeUploadFile(b"4567", size=4),
        ]

        with (
            patch.object(upload_validation, "MAX_SIZE_PER_FILE_MB", 10),
            patch.object(upload_validation, "MAX_BATCH_SIZE_MB", 6),
            patch.object(upload_validation, "mb_to_bytes", side_effect=lambda value: value),
        ):
            with self.assertRaises(HTTPException) as context:
                await upload_validation.read_and_validate_batch(documents)

        self.assertEqual(context.exception.status_code, 413)
        self.assertEqual(documents[0].read_sizes, [])
        self.assertEqual(documents[1].read_sizes, [])

    async def test_files_at_the_configured_limits_are_accepted(self):
        documents = [
            FakeUploadFile(b"123", filename="first.pdf"),
            FakeUploadFile(b"456", filename="second.pdf"),
        ]

        with (
            patch.object(upload_validation, "MAX_SIZE_PER_FILE_MB", 3),
            patch.object(upload_validation, "MAX_BATCH_SIZE_MB", 6),
            patch.object(upload_validation, "mb_to_bytes", side_effect=lambda value: value),
            patch.object(upload_validation, "is_file_format_supported", return_value=True),
        ):
            document_data = await upload_validation.read_and_validate_batch(documents)

        self.assertEqual(document_data, [("first.pdf", b"123"), ("second.pdf", b"456")])


if __name__ == "__main__":
    unittest.main()
