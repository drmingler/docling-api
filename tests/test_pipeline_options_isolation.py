import unittest

from document_converter.service import DoclingDocumentConversion


class PipelineOptionsIsolationTests(unittest.TestCase):
    """Regression tests for shared-state bug where per-request Docling options
    (extract_tables_as_images, image_resolution_scale) mutated a converter-wide
    pipeline_options object and leaked across requests."""

    def test_build_does_not_mutate_shared_pipeline_options(self):
        converter = DoclingDocumentConversion()
        original_scale = converter.pipeline_options.images_scale
        original_generate_table_images = converter.pipeline_options.generate_table_images

        converter._build_pipeline_options(extract_tables=True, image_resolution_scale=2)

        self.assertEqual(converter.pipeline_options.images_scale, original_scale)
        self.assertEqual(converter.pipeline_options.generate_table_images, original_generate_table_images)

    def test_build_returns_a_new_options_instance_each_call(self):
        converter = DoclingDocumentConversion()

        first = converter._build_pipeline_options(extract_tables=True, image_resolution_scale=2)
        second = converter._build_pipeline_options(extract_tables=False, image_resolution_scale=4)

        self.assertIsNot(first, second)
        self.assertIsNot(first, converter.pipeline_options)
        self.assertIsNot(second, converter.pipeline_options)

    def test_options_do_not_leak_between_sequential_conversions(self):
        converter = DoclingDocumentConversion()

        request_a = converter._build_pipeline_options(extract_tables=True, image_resolution_scale=1)
        request_b = converter._build_pipeline_options(extract_tables=False, image_resolution_scale=4)

        self.assertTrue(request_a.generate_table_images)
        self.assertEqual(request_a.images_scale, 1)
        self.assertFalse(request_b.generate_table_images)
        self.assertEqual(request_b.images_scale, 4)

    def test_mutating_returned_options_does_not_affect_the_converter(self):
        converter = DoclingDocumentConversion()
        original_scale = converter.pipeline_options.images_scale

        built = converter._build_pipeline_options(extract_tables=True, image_resolution_scale=3)
        built.images_scale = 999
        built.generate_table_images = False

        self.assertEqual(converter.pipeline_options.images_scale, original_scale)


if __name__ == "__main__":
    unittest.main()
