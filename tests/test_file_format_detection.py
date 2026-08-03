import unittest
from io import BytesIO

from document_converter.utils import InputFormat, guess_format, handle_csv_file, is_file_format_supported


class FileFormatDetectionTests(unittest.TestCase):
    def test_csv_is_detected_by_filename(self):
        for filename in ("records.csv", "RECORDS.CSV"):
            with self.subTest(filename=filename):
                self.assertEqual(guess_format(b"name,value\nexample,1", filename), InputFormat.CSV)
                self.assertTrue(is_file_format_supported(b"name,value\nexample,1", filename))

    def test_html_and_xhtml_are_detected_from_content(self):
        samples = (
            (b"<!-- leading comment --><!doctype html><html><body></body></html>", InputFormat.HTML),
            (
                b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"></html>',
                InputFormat.HTML,
            ),
        )

        for content, expected_format in samples:
            with self.subTest(content=content):
                self.assertEqual(guess_format(content, "document.unknown"), expected_format)

    def test_markdown_and_asciidoc_use_extension_fallback(self):
        samples = (
            ("README.md", InputFormat.MD),
            ("guide.adoc", InputFormat.ASCIIDOC),
            ("guide.asciidoc", InputFormat.ASCIIDOC),
            ("guide.asc", InputFormat.ASCIIDOC),
        )

        for filename, expected_format in samples:
            with self.subTest(filename=filename):
                self.assertEqual(guess_format(b"A plain-text document", filename), expected_format)

    def test_unknown_binary_format_is_not_supported(self):
        content = b"unrecognized file content"

        self.assertIsNone(guess_format(content, "document.unknown"))
        self.assertFalse(is_file_format_supported(content, "document.unknown"))

    def test_csv_content_is_transcoded_to_utf8(self):
        samples = (
            ("name\nCaf\u00e9\n", "utf-8"),
            ("name\nCaf\u00e9\n", "latin1"),
            ("quote\n\u201cHello\u201d\n", "cp1252"),
        )

        for content, encoding in samples:
            with self.subTest(encoding=encoding):
                converted, error = handle_csv_file(BytesIO(content.encode(encoding)))

                self.assertIsNone(error)
                self.assertEqual(converted.read().decode("utf-8"), content)


if __name__ == "__main__":
    unittest.main()
