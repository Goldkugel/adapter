import sys

# Prevent Python from generating .pyc files
sys.dont_write_bytecode = True

import os
import unittest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)

from UMLSAdapter import UMLSAdapter


class UMLSAdapterTest(unittest.TestCase):
    """
    Tests for the UMLSAdapter.
    """

    def setUp(self):
        self.adapter = UMLSAdapter()

    def test_load(self):
        """
        Test that the configured UMLS files can be loaded.
        """

        count = self.adapter.load()

        self.assertIsNotNone(self.adapter.data)
        self.assertGreater(count, 0)
        self.assertEqual(count, len(self.adapter.data.index))

    def test_columns(self):
        """
        Test that the resulting DataFrame contains the configured columns.
        """

        self.adapter.load()

        self.assertIn(
            self.adapter.config.id_column,
            self.adapter.data.columns,
        )

        self.assertIn(
            self.adapter.config.attribute_column,
            self.adapter.data.columns,
        )

        self.assertIn(
            self.adapter.config.value_column,
            self.adapter.data.columns,
        )

        self.assertIn(
            self.adapter.config.additional_column,
            self.adapter.data.columns,
        )

    def test_no_missing_ids(self):
        """
        Every row should contain an identifier.
        """

        self.adapter.load()

        self.assertFalse(
            self.adapter.data[
                self.adapter.config.id_column
            ].isna().any()
        )

        self.assertFalse(
            (
                self.adapter.data[
                    self.adapter.config.id_column
                ] == ""
            ).any()
        )

    def test_to_csv(self):
        """
        Test that the adapter can write its output.
        """

        self.adapter.load()
        self.adapter.to_csv()

        output_file = os.path.join(
            self.adapter.config.output_folder,
            self.adapter.config.output_file,
        )

        self.assertTrue(os.path.isfile(output_file))


if __name__ == "__main__":
    unittest.main()