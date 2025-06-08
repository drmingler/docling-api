from io import BytesIO
import re
from enum import Enum
from typing import Dict, List, Optional, Tuple

import filetype

import openpyxl


class InputFormat(str, Enum):
    DOCX = "docx"
    PPTX = "pptx"
    HTML = "html"
    IMAGE = "image"
    PDF = "pdf"
    ASCIIDOC = "asciidoc"
    MD = "md"
    CSV = "csv"
    XLSX = "xlsx"


class OutputFormat(str, Enum):
    MARKDOWN = "md"
    JSON = "json"
    TEXT = "text"
    DOCTAGS = "doctags"


FormatToExtensions: Dict[InputFormat, List[str]] = {
    InputFormat.DOCX: ["docx", "dotx", "docm", "dotm"],
    InputFormat.PPTX: ["pptx", "potx", "ppsx", "pptm", "potm", "ppsm"],
    InputFormat.PDF: ["pdf"],
    InputFormat.MD: ["md"],
    InputFormat.HTML: ["html", "htm", "xhtml"],
    InputFormat.IMAGE: ["jpg", "jpeg", "png", "tif", "tiff", "bmp"],
    InputFormat.ASCIIDOC: ["adoc", "asciidoc", "asc"],
    InputFormat.CSV: ["csv"],
    InputFormat.XLSX: ["xlsx"], # "xltx", "xlsm", "xltm", "xlam", "xlsb"
}

FormatToMimeType: Dict[InputFormat, List[str]] = {
    InputFormat.DOCX: [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    ],
    InputFormat.PPTX: [
        "application/vnd.openxmlformats-officedocument.presentationml.template",
        "application/vnd.openxmlformats-officedocument.presentationml.slideshow",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ],
    InputFormat.HTML: ["text/html", "application/xhtml+xml"],
    InputFormat.IMAGE: [
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/gif",
        "image/bmp",
    ],
    InputFormat.PDF: ["application/pdf"],
    InputFormat.ASCIIDOC: ["text/asciidoc"],
    InputFormat.MD: ["text/markdown", "text/x-markdown"],
    InputFormat.CSV: ["text/csv"],
    InputFormat.XLSX: ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
}
MimeTypeToFormat = {mime: fmt for fmt, mimes in FormatToMimeType.items() for mime in mimes}


def detect_html_xhtml(content):
    content_str = content.decode("ascii", errors="ignore").lower()
    # Remove XML comments
    content_str = re.sub(r"<!--(.*?)-->", "", content_str, flags=re.DOTALL)
    content_str = content_str.lstrip()

    if re.match(r"<\?xml", content_str):
        if "xhtml" in content_str[:1000]:
            return "application/xhtml+xml"

    if re.match(r"<!doctype\s+html|<html|<head|<body", content_str):
        return "text/html"

    return None


def is_csv_file(filename: str) -> bool:
    """Check if a file is a CSV based on its extension."""
    return filename and filename.lower().endswith('.csv')


def guess_format(obj: bytes, filename: str = None):
    content = b""
    mime = None

    if isinstance(obj, bytes):
        content = obj
        # Special handling for CSV files
        if is_csv_file(filename):
            return InputFormat.CSV

        mime = filetype.guess_mime(content)
        if mime is None: # mime type is not found
            ext = filename.rsplit(".", 1)[-1] if ("." in filename and not filename.startswith(".")) else ""
            mime = mime_from_extension(ext)

    mime = mime or detect_html_xhtml(content)
    mime = mime or "text/plain"
    return MimeTypeToFormat.get(mime)


def handle_csv_file(file: BytesIO) -> Tuple[BytesIO, Optional[str]]:
    """Handle CSV file encoding by trying multiple encodings.

    Returns:
        Tuple[BytesIO, Optional[str]]: (processed file, error message if any)
    """
    SUPPORTED_CSV_ENCODINGS = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
    for encoding in SUPPORTED_CSV_ENCODINGS:
        try:
            file.seek(0)
            content = file.read().decode(encoding)
            return BytesIO(content.encode('utf-8')), None
        except UnicodeDecodeError:
            continue
    return file, f"Could not decode CSV file. Supported encodings: {', '.join(SUPPORTED_CSV_ENCODINGS)}"

def handle_xlsx_file(file: BytesIO) -> Tuple[BytesIO, Optional[str]]:
    """Handle XLSX file. reads the cell value, not the formula.

    Returns:
        Tuple[BytesIO, Optional[str]]: (processed file, error message if any)
    """
    err_msg = None

    newFile = BytesIO() # var to place converted .xlsx
    try:
        wb = openpyxl.load_workbook(filename=file, data_only=True) # create .xlsx from bytesio, converting formulas into values
        wb.save(newFile)
    except Exception as err:
        err_msg = str(err)

    newFile.seek(0)

    return newFile, err_msg



def mime_from_extension(ext):
    mime = None
    if ext in FormatToExtensions[InputFormat.ASCIIDOC]:
        mime = FormatToMimeType[InputFormat.ASCIIDOC][0]
    elif ext in FormatToExtensions[InputFormat.HTML]:
        mime = FormatToMimeType[InputFormat.HTML][0]
    elif ext in FormatToExtensions[InputFormat.MD]:
        mime = FormatToMimeType[InputFormat.MD][0]
    elif ext in FormatToExtensions[InputFormat.CSV]:
        mime = FormatToMimeType[InputFormat.CSV][0]

    return mime


def is_file_format_supported(file_bytes: bytes, filename: str) -> bool:
    return guess_format(file_bytes, filename) in FormatToExtensions.keys()
