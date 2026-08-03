import unittest
from types import SimpleNamespace

from PIL import Image
from docling_core.types.doc import (
    DoclingDocument,
    ImageRef,
    ImageRefMode,
    TableCell,
    TableData,
    TableItem,
)

from document_converter.service import DoclingDocumentConversion


def create_image(color: str) -> ImageRef:
    return ImageRef.from_pil(Image.new("RGB", (2, 2), color), dpi=72)


def add_table(document: DoclingDocument, heading: str, value: str, color: str):
    cells = [
        TableCell(
            start_row_offset_idx=0,
            end_row_offset_idx=1,
            start_col_offset_idx=0,
            end_col_offset_idx=1,
            text=heading,
            column_header=True,
        ),
        TableCell(
            start_row_offset_idx=1,
            end_row_offset_idx=2,
            start_col_offset_idx=0,
            end_col_offset_idx=1,
            text=value,
        ),
    ]
    table = document.add_table(TableData(table_cells=cells, num_rows=2, num_cols=1))
    table.image = create_image(color)
    return table


class DocumentImageTests(unittest.TestCase):
    def test_table_and_picture_references_follow_document_order(self):
        document = DoclingDocument(name="mixed-images")
        add_table(document, "First_heading", "First", "red")
        document.add_picture(image=create_image("blue"))
        add_table(document, "Second heading", "Second", "green")
        document.add_picture(image=create_image("yellow"))
        original_markdown = document.export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)

        markdown, images = DoclingDocumentConversion._process_document_images(SimpleNamespace(document=document))

        expected_markdown = original_markdown
        table_references = []
        for element_index, (element, _level) in enumerate(document.iterate_items(with_groups=True)):
            if isinstance(element, TableItem):
                table_references.append(
                    document.export_to_markdown(
                        from_element=element_index,
                        to_element=element_index + 1,
                        image_mode=ImageRefMode.PLACEHOLDER,
                    )
                )

        expected_markdown = expected_markdown.replace(table_references[0], f"{table_references[0]}\n\ntable-1.png", 1)
        expected_markdown = expected_markdown.replace("<!-- image -->", "picture-1.png", 1)
        expected_markdown = expected_markdown.replace(table_references[1], f"{table_references[1]}\n\ntable-2.png", 1)
        expected_markdown = expected_markdown.replace("<!-- image -->", "picture-2.png", 1)

        self.assertEqual(markdown, expected_markdown)
        self.assertEqual(
            [(image.type, image.filename) for image in images],
            [
                ("table", "table-1.png"),
                ("picture", "picture-1.png"),
                ("table", "table-2.png"),
                ("picture", "picture-2.png"),
            ],
        )

    def test_picture_without_image_does_not_consume_a_later_picture_reference(self):
        document = DoclingDocument(name="missing-picture")
        document.add_picture()
        document.add_picture(image=create_image("blue"))

        markdown, images = DoclingDocumentConversion._process_document_images(SimpleNamespace(document=document))

        self.assertEqual(markdown, "<!-- image -->\n\npicture-1.png")
        self.assertEqual([image.filename for image in images], ["picture-1.png"])


if __name__ == "__main__":
    unittest.main()
