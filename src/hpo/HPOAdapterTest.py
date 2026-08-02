import sys

# Prevent Python from generating .pyc files (compiled bytecode files)
sys.dont_write_bytecode = True

import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from .HPOAdapter import HPOAdapter
from ..BaseAdapter import standard_directory

@pytest.fixture
def adapter():
    """
    Build an HPOAdapter from the project's real config file (BaseAdapter's
    default path, "../config/config.yaml"), rather than a synthetic one.
    Assumes the test process runs from a location where that relative
    path resolves to the actual config file.
    """
    return HPOAdapter()


def make_frame(config, attribute, n=1):
    """Build a small EAV-shaped DataFrame, as a real extractor would return."""
    return pd.DataFrame({
        config.id_column: [f"HP:000000{i}" for i in range(n)],
        config.attribute_column: [attribute] * n,
        config.value_column: [f"{attribute}-value-{i}" for i in range(n)],
        config.additional_column: [{} for _ in range(n)],
    })


ALL_EXTRACTOR_NAMES = [
    "getLabels",
    "getDefinitions",
    "getComments",
    "getChildren",
    "getReferences",
    "getSynonymsAndTypes",
]


class TestHPOAdapterInit:

    def test_init_loads_input_settings_from_real_config(self, adapter):
        assert adapter.config.input_folder == "../data/input/hpo/"
        assert adapter.config.input_files == ["hp.owl"]

    def test_init_loads_output_settings_from_real_config(self, adapter):
        assert adapter.config.output_folder == "../data/output/transformed/hpo/"
        assert adapter.config.output_file == "hpo.csv"

    def test_init_applies_defaults_for_fields_not_set_in_config(self, adapter):
        # delimiter, encoding, and the EAV column names aren't overridden
        # in config.yaml, so BaseAdapterConfig's own defaults apply.
        assert adapter.config.delimiter == ";"
        assert adapter.config.encoding == "utf-8"
        assert adapter.config.id_column == "id"
        assert adapter.config.attribute_column == "attribute"
        assert adapter.config.value_column == "value"
        assert adapter.config.additional_column == "additional"

    def test_data_is_unset_before_load(self, adapter):
        assert adapter.data is None


class TestHPOAdapterLoad:

    @patch("HPOAdapter.get_ontology")
    @patch("HPOAdapter.utils")
    def test_load_calls_get_ontology_with_input_folder_and_first_input_file(
        self, mock_utils, mock_get_ontology, adapter
    ):
        mock_get_ontology.return_value.load.return_value = MagicMock()
        for name in ALL_EXTRACTOR_NAMES:
            getattr(mock_utils, name).return_value = make_frame(adapter.config, "x", n=0)

        adapter.load()

        expected_path = adapter.config.input_folder + adapter.config.input_files[0]
        called_path = mock_get_ontology.call_args.args[0]
        assert called_path.replace("\\", "/") == expected_path.replace("\\", "/")

    @patch("HPOAdapter.get_ontology")
    @patch("HPOAdapter.utils")
    def test_load_passes_loaded_ontology_and_configured_column_names_to_every_extractor(
        self, mock_utils, mock_get_ontology, adapter
    ):
        mock_ontology = MagicMock()
        mock_get_ontology.return_value.load.return_value = mock_ontology
        for name in ALL_EXTRACTOR_NAMES:
            getattr(mock_utils, name).return_value = make_frame(adapter.config, "x", n=0)

        adapter.load()

        for name in ALL_EXTRACTOR_NAMES:
            getattr(mock_utils, name).assert_called_once_with(
                mock_ontology,
                adapter.config.id_column,
                adapter.config.attribute_column,
                adapter.config.value_column,
                adapter.config.additional_column,
            )

    @patch("HPOAdapter.get_ontology")
    @patch("HPOAdapter.utils")
    def test_load_concatenates_all_extractor_results_into_self_data(
        self, mock_utils, mock_get_ontology, adapter
    ):
        mock_get_ontology.return_value.load.return_value = MagicMock()
        mock_utils.getLabels.return_value = make_frame(adapter.config, "label", n=2)
        mock_utils.getDefinitions.return_value = make_frame(adapter.config, "definition", n=3)
        mock_utils.getComments.return_value = make_frame(adapter.config, "comment", n=1)
        mock_utils.getChildren.return_value = make_frame(adapter.config, "child", n=4)
        mock_utils.getReferences.return_value = make_frame(adapter.config, "reference", n=1)
        mock_utils.getSynonymsAndTypes.return_value = make_frame(adapter.config, "synonym", n=2)

        row_count = adapter.load()

        assert row_count == 13
        assert len(adapter.data) == 13
        assert set(adapter.data[adapter.config.attribute_column]) == {
            "label", "definition", "comment", "child", "reference", "synonym"
        }

    @patch("HPOAdapter.get_ontology")
    @patch("HPOAdapter.utils")
    def test_load_skips_extractors_that_return_none(
        self, mock_utils, mock_get_ontology, adapter
    ):
        mock_get_ontology.return_value.load.return_value = MagicMock()
        mock_utils.getLabels.return_value = make_frame(adapter.config, "label", n=2)
        mock_utils.getDefinitions.return_value = None
        mock_utils.getComments.return_value = None
        mock_utils.getChildren.return_value = None
        mock_utils.getReferences.return_value = None
        mock_utils.getSynonymsAndTypes.return_value = None

        row_count = adapter.load()

        assert row_count == 2
        assert list(adapter.data[adapter.config.attribute_column]) == ["label", "label"]

    @patch("HPOAdapter.get_ontology")
    @patch("HPOAdapter.utils")
    def test_load_returns_total_row_count_across_extractors(
        self, mock_utils, mock_get_ontology, adapter
    ):
        mock_get_ontology.return_value.load.return_value = MagicMock()
        for name in ALL_EXTRACTOR_NAMES:
            getattr(mock_utils, name).return_value = make_frame(adapter.config, "x", n=1)

        assert adapter.load() == len(ALL_EXTRACTOR_NAMES)


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))