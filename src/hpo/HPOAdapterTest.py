import sys

# Prevent Python from generating .pyc files (compiled bytecode files)
sys.dont_write_bytecode = True

import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pytest
import pandas as pd
from pathlib import Path

from .HPOAdapter import HPOAdapter


@pytest.fixture
def adapter():
    """
    Build an HPOAdapter passing the path relative to the repo root.
    """
    return HPOAdapter(config="./config/config.yaml")


@pytest.fixture(scope="module")
def loaded_adapter():
    """
    Build an HPOAdapter and run the real load() once for the whole
    module - this parses the actual configured hp.owl file via
    owlready2 and runs the real HPOAdapterUtils extractors against it,
    with no mocking involved. Scoped to the module (rather than
    per-function) since re-parsing the full ontology for every test
    would be expensive and these tests only read the result, never
    mutate it.

    Requires owlready2 to be installed and the real ontology file to
    exist at the path configured in ./config/config.yaml.
    """
    a = HPOAdapter(config="./config/config.yaml")
    row_count = a.load()
    return a, row_count


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
        assert adapter.config.input_folder == "./data/input/hpo/"
        assert adapter.config.input_files == ["hp.owl"]

    def test_init_loads_output_settings_from_real_config(self, adapter):
        assert adapter.config.output_folder == "./data/output/transformed/hpo/"
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
    """
    Integration tests against the real hp.owl file - no mocking of
    get_ontology or HPOAdapterUtils. Assertions check the shape and
    general contents of the real output rather than exact row counts,
    since those depend on whatever the actual ontology file contains.
    """

    def test_load_returns_a_positive_row_count(self, loaded_adapter):
        _, row_count = loaded_adapter
        assert row_count > 0

    def test_load_populates_self_data(self, loaded_adapter):
        adapter, row_count = loaded_adapter
        assert adapter.data is not None
        assert len(adapter.data) == row_count

    def test_load_data_has_the_configured_eav_columns(self, loaded_adapter):
        adapter, _ = loaded_adapter
        expected_columns = {
            adapter.config.id_column,
            adapter.config.attribute_column,
            adapter.config.value_column,
            adapter.config.additional_column,
        }
        assert expected_columns.issubset(set(adapter.data.columns))

    def test_load_produces_every_known_attribute_type(self, loaded_adapter):
        adapter, _ = loaded_adapter
        found_attributes = set(adapter.data[adapter.config.attribute_column])
        expected_attributes = {
            "label", "definition", "comment", "child", "reference", "synonym"
        }
        assert expected_attributes.issubset(found_attributes)

    def test_load_removes_rows_without_an_id(self, loaded_adapter):
        adapter, _ = loaded_adapter
        id_column = adapter.data[adapter.config.id_column]
        assert id_column.notna().all()
        assert (id_column != "").all()

    def test_load_removes_rows_with_a_hash_in_the_id(self, loaded_adapter):
        adapter, _ = loaded_adapter
        id_column = adapter.data[adapter.config.id_column]
        assert not id_column.str.contains("#", na=False).any()

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))