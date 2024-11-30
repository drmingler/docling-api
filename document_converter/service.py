import base64
import logging
from abc import ABC, abstractmethod
from io import BytesIO
from typing import List, Tuple, Union

from celery.result import AsyncResult
from docling.datamodel.base_models import InputFormat, DocumentStream
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
from docling.document_converter import PdfFormatOption, DocumentConverter
from docling_core.types.doc import ImageRefMode, TableItem, PictureItem
from fastapi import HTTPException

from document_converter.schema import BatchConversionJobResult, ConversationJobResult, ConversionResult, ImageData

logging.basicConfig(level=logging.INFO)
IMAGE_RESOLUTION_SCALE = 4


class DocumentConversionBase(ABC):
    @abstractmethod
    def convert(self, document: Union[Tuple[str, BytesIO], str], **kwargs) -> ConversionResult:
        pass

    @abstractmethod
    def convert_batch(self, documents: List[Union[Tuple[str, BytesIO], str]], **kwargs) -> List[ConversionResult]:
        pass


class DoclingDocumentConversion(DocumentConversionBase):
    def _setup_pipeline_options(self, extract_tables: bool, image_resolution_scale: int) -> PdfPipelineOptions:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.images_scale = image_resolution_scale
        pipeline_options.generate_page_images = False
        pipeline_options.generate_table_images = extract_tables
        pipeline_options.generate_picture_images = True
        pipeline_options.ocr_options = EasyOcrOptions(lang=["fr", "de", "es", "en", "it", "pt"])

        return pipeline_options

    @staticmethod
    def _process_document_images(conv_res) -> Tuple[str, List[ImageData]]:
        images = []
        table_counter = 0
        picture_counter = 0
        content_md = conv_res.document.export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)

        for element, _level in conv_res.document.iterate_items():
            if isinstance(element, (TableItem, PictureItem)) and element.image:
                img_buffer = BytesIO()
                element.image.pil_image.save(img_buffer, format="PNG")

                if isinstance(element, TableItem):
                    table_counter += 1
                    image_name = f"table-{table_counter}.png"
                    image_type = "table"
                else:
                    picture_counter += 1
                    image_name = f"picture-{picture_counter}.png"
                    image_type = "picture"
                    content_md = content_md.replace("<!-- image -->", image_name, 1)

                image_bytes = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
                images.append(ImageData(type=image_type, filename=image_name, image=image_bytes))

        return content_md, images

    def convert(
        self,
        document: Union[Tuple[str, BytesIO], str],
        extract_tables: bool = False,
        image_resolution_scale: int = IMAGE_RESOLUTION_SCALE,
    ) -> ConversionResult:
        pipeline_options = self._setup_pipeline_options(extract_tables, image_resolution_scale)
        doc_converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )

        try:
            if isinstance(document, tuple):
                filename, file = document
                conv_res = doc_converter.convert(DocumentStream(name=filename, stream=file), raises_on_error=False)
                doc_filename = conv_res.input.file.stem
            else:
                # Handle URL or file path directly
                conv_res = doc_converter.convert(document, raises_on_error=False)
                doc_filename = document.split('/')[-1]  # Extract filename from URL or path

            if conv_res.errors:
                logging.error(f"Failed to convert {doc_filename}: {conv_res.errors[0].error_message}")
                return ConversionResult(filename=doc_filename, error=conv_res.errors[0].error_message)

            content_md, images = self._process_document_images(conv_res)
            return ConversionResult(filename=doc_filename, markdown=content_md, images=images)
        except Exception as e:
            error_msg = f"Failed to convert document: {str(e)}"
            logging.error(error_msg)
            return ConversionResult(filename=doc_filename if 'doc_filename' in locals() else "unknown", error=error_msg)

    def convert_batch(
        self,
        documents: List[Union[Tuple[str, BytesIO], str]],
        extract_tables: bool = False,
        image_resolution_scale: int = IMAGE_RESOLUTION_SCALE,
    ) -> List[ConversionResult]:
        pipeline_options = self._setup_pipeline_options(extract_tables, image_resolution_scale)
        doc_converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )

        results = []
        for doc in documents:
            try:
                if isinstance(doc, tuple):
                    filename, file = doc
                    conv_res = doc_converter.convert(DocumentStream(name=filename, stream=file), raises_on_error=False)
                    doc_filename = conv_res.input.file.stem
                else:
                    # Handle URL or file path directly
                    conv_res = doc_converter.convert(doc, raises_on_error=False)
                    doc_filename = doc.split('/')[-1]  # Extract filename from URL or path

                if conv_res.errors:
                    logging.error(f"Failed to convert {doc_filename}: {conv_res.errors[0].error_message}")
                    results.append(ConversionResult(filename=doc_filename, error=conv_res.errors[0].error_message))
                    continue

                content_md, images = self._process_document_images(conv_res)
                results.append(ConversionResult(filename=doc_filename, markdown=content_md, images=images))
            except Exception as e:
                error_msg = f"Failed to convert document: {str(e)}"
                logging.error(error_msg)
                results.append(ConversionResult(filename="unknown", error=error_msg))

        return results


class DocumentConverterService:
    def __init__(self, document_converter: DocumentConversionBase):
        self.document_converter = document_converter

    def convert_document(self, document: Union[Tuple[str, BytesIO], str], **kwargs) -> ConversionResult:
        result = self.document_converter.convert(document, **kwargs)
        if result.error:
            logging.error(f"Failed to convert document: {result.error}")
            raise HTTPException(status_code=500, detail=result.error)
        return result

    def convert_documents(self, documents: List[Union[Tuple[str, BytesIO], str]], **kwargs) -> List[ConversionResult]:
        return self.document_converter.convert_batch(documents, **kwargs)

    def convert_document_task(
        self,
        document: Union[Tuple[str, bytes], str],
        **kwargs,
    ) -> ConversionResult:
        if isinstance(document, tuple):
            document = (document[0], BytesIO(document[1]))
        return self.document_converter.convert(document, **kwargs)

    def convert_documents_task(
        self,
        documents: List[Union[Tuple[str, bytes], str]],
        **kwargs,
    ) -> List[ConversionResult]:
        processed_docs = []
        for doc in documents:
            if isinstance(doc, tuple):
                processed_docs.append((doc[0], BytesIO(doc[1])))
            else:
                processed_docs.append(doc)
        return self.document_converter.convert_batch(processed_docs, **kwargs)

    def get_single_document_task_result(self, job_id: str) -> ConversationJobResult:
        """Get the status and result of a document conversion job.

        Returns:
        - IN_PROGRESS: When task is still running
        - SUCCESS: When conversion completed successfully
        - FAILURE: When task failed or conversion had errors
        """

        task = AsyncResult(job_id)
        if task.state == 'PENDING':
            return ConversationJobResult(job_id=job_id, status="IN_PROGRESS")

        elif task.state == 'SUCCESS':
            result = task.get()
            # Check if the conversion result contains an error
            if result.get('error'):
                return ConversationJobResult(job_id=job_id, status="FAILURE", error=result['error'])

            return ConversationJobResult(job_id=job_id, status="SUCCESS", result=ConversionResult(**result))

        else:
            return ConversationJobResult(job_id=job_id, status="FAILURE", error=str(task.result))

    def get_batch_conversion_task_result(self, job_id: str) -> BatchConversionJobResult:
        """Get the status and results of a batch conversion job.

        Returns:
        - IN_PROGRESS: When task is still running
        - SUCCESS: A batch is successful as long as the task is successful
        - FAILURE: When the task fails for any reason
        """

        task = AsyncResult(job_id)
        if task.state == 'PENDING':
            return BatchConversionJobResult(job_id=job_id, status="IN_PROGRESS")

        # Task completed successfully, but need to check individual conversion results
        if task.state == 'SUCCESS':
            conversion_results = task.get()
            job_results = []

            for result in conversion_results:
                if result.get('error'):
                    job_result = ConversationJobResult(status="FAILURE", error=result['error'])
                else:
                    job_result = ConversationJobResult(
                        status="SUCCESS", result=ConversionResult(**result).model_dump(exclude_unset=True)
                    )
                job_results.append(job_result)

            return BatchConversionJobResult(job_id=job_id, status="SUCCESS", conversion_results=job_results)

        return BatchConversionJobResult(job_id=job_id, status="FAILURE", error=str(task.result))
