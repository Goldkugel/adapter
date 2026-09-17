"""
Tests for UMLSAdapter and UMLSAdapterUtils.

Contains three test classes:
- TestUMLSAdapterInit: unit tests for configuration loading via __init__.
- TestUMLSAdapterLoadSkipping: tests for the skip-if-present and
  no-input-files early-exit paths.
- TestUMLSAdapterLoad: tests for file reading, merging, cleaning, and
  the row count returned by load().
"""

from __future__ import annotations

import os

from unittest.mock  import MagicMock, patch
from .UMLSAdapter   import UMLSAdapter
import pandas       as pd
import yaml
import pytest

# unittest.mock patches names where they are looked up, not where they
# are defined. UMLSAdapter imports readRRFFileByPath into its own
# namespace, so it must be patched under "src.umls.UMLSAdapter" rather
# than under "src.umls.UMLSAdapterUtils" where it is originally defined.
PATCH_MODULE = "src.umls.UMLSAdapter"


@pytest.fixture
def config_path(tmp_path):
    """
    Write a minimal adapter config YAML to a temp file and return its
    path. Only `input_files` is set explicitly; every other field —
    input_folder, output_folder, output_file, skip_if_present, the four
    EAV column names, encoding, separator — is left unset so
    BaseAdapterConfig's own defaults apply.
    """
    config = {
        "adapter": {
            "umls": {
                "input_files": ["MRCONSO.RRF", "MRDEF.RRF"],
            }
        }
    }
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(config, f)
    return str(path)


@pytest.fixture
def adapter(config_path):
    return UMLSAdapter(config=config_path)


def make_frame(config, id_values, attribute, value_values):
    """Build a small EAV-shaped DataFrame, as readRRFFileByPath would return."""
    n = len(id_values)
    return pd.DataFrame({
        config.id_column        : id_values,
        config.attribute_column : [attribute] * n,
        config.value_column     : value_values,
        config.additional_column: [{} for _ in range(n)],
    })


class TestUMLSAdapterInit:
    """
    Unit tests for UMLSAdapter.__init__.

    Verifies that configuration values are correctly loaded from the
    YAML file and that self.data is unset before load() is called.
    """

    def test_init_loads_config_from_yaml(self, adapter):
        assert adapter.config.input_files == ["MRCONSO.RRF", "MRDEF.RRF"]

    def test_data_is_unset_before_load(self, adapter):
        assert adapter.data is None


class TestUMLSAdapterLoadSkipping:
    """
    Tests for the early-exit paths in UMLSAdapter.load():
    no input files configured, and skip_if_present when output exists.
    """

    def test_load_returns_zero_when_no_input_files_configured(self, tmp_path):
        config = {"adapter": {"umls": {"input_files": []}}}
        path = tmp_path / "config.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(config, f)
        adapter = UMLSAdapter(config=str(path))

        assert adapter.load() == 0
        assert adapter.data is None

    @patch("os.path.isfile", return_value=True)
    @patch(f"{PATCH_MODULE}.readRRFFileByPath")
    def test_load_skips_when_output_present_and_skip_if_present_true(
        self, mock_read_rrf, mock_is_file, tmp_path
    ):
        config = {
            "adapter": {
                "umls": {
                    "input_files": ["MRCONSO.RRF"],
                    "skip_if_present": True,
                }
            }
        }
        path = tmp_path / "config.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(config, f)
        adapter = UMLSAdapter(config=str(path))

        ret = adapter.load()

        assert ret == 0
        assert adapter.data is None
        mock_read_rrf.assert_not_called()

    @patch("os.path.isfile", return_value=True)
    @patch(f"{PATCH_MODULE}.readRRFFileByPath")
    def test_load_does_not_skip_when_skip_if_present_is_false_even_if_file_exists(
        self, mock_read_rrf, mock_is_file, adapter
    ):
        mock_read_rrf.return_value = make_frame(
            adapter.config, ["C0001"], "label", ["Some Concept"]
        )

        adapter.load()

        mock_read_rrf.assert_called()


class TestUMLSAdapterLoad:
    """
    Tests for file reading, DataFrame merging, post-processing
    (ID/value cleaning, deduplication), and the row count returned
    by UMLSAdapter.load().
    """

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_MODULE}.readRRFFileByPath")
    def test_load_calls_readRRFFileByPath_for_every_configured_file_with_full_path_and_config(
        self, mock_read_rrf, mock_is_file, adapter
    ):
        mock_read_rrf.return_value = make_frame(
            adapter.config, ["C0001"], "label", ["Some Concept"]
        )

        adapter.load()

        expected_paths = [
            os.path.join(adapter.config.input_folder, f)
            for f in adapter.config.input_files
        ]
        actual_paths = [c.args[0] for c in mock_read_rrf.call_args_list]
        assert actual_paths == expected_paths

        for c in mock_read_rrf.call_args_list:
            _, id_col, attr_col, val_col, add_col, encoding, separator = c.args
            assert id_col   == adapter.config.id_column
            assert attr_col == adapter.config.attribute_column
            assert val_col  == adapter.config.value_column
            assert add_col  == adapter.config.additional_column
            assert encoding == adapter.config.encoding
            assert separator == adapter.config.separator

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_MODULE}.readRRFFileByPath")
    def test_load_merges_frames_and_returns_row_count(
        self, mock_read_rrf, mock_is_file, adapter
    ):
        mock_read_rrf.side_effect = [
            make_frame(adapter.config, ["C0001", "C0002"], "label", ["A", "B"]),
            make_frame(adapter.config, ["C0001"], "definition", ["A definition."]),
        ]

        ret = adapter.load()

        assert ret == 3
        assert len(adapter.data) == 3
        assert set(adapter.data[adapter.config.attribute_column]) == {
            "label", "definition"
        }

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_MODULE}.readRRFFileByPath")
    def test_load_skips_files_whose_reader_returns_none_or_empty(
        self, mock_read_rrf, mock_is_file, adapter
    ):
        mock_read_rrf.side_effect = [
            None,
            make_frame(adapter.config, [], "definition", []),
        ]

        ret = adapter.load()

        assert ret == 0
        assert adapter.data is None

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_MODULE}.readRRFFileByPath")
    def test_load_removes_rows_with_missing_or_empty_id(
        self, mock_read_rrf, mock_is_file, adapter
    ):
        frame = make_frame(
            adapter.config,
            ["C0001", None, ""],
            "label",
            ["Valid", "Missing ID", "Empty ID"],
        )
        mock_read_rrf.return_value = frame

        adapter.load()

        assert len(adapter.data) == 1
        assert adapter.data.iloc[0][adapter.config.value_column] == "Valid"

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_MODULE}.readRRFFileByPath")
    def test_load_removes_rows_with_missing_or_empty_value(
        self, mock_read_rrf, mock_is_file, adapter
    ):
        frame = make_frame(
            adapter.config,
            ["C0001", "C0002", "C0003"],
            "label",
            ["Valid", None, ""],
        )
        mock_read_rrf.return_value = frame

        adapter.load()

        assert len(adapter.data) == 1
        assert adapter.data.iloc[0][adapter.config.id_column] == "C0001"

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_MODULE}.readRRFFileByPath")
    def test_load_removes_duplicate_id_attribute_value_rows(
        self, mock_read_rrf, mock_is_file, adapter
    ):
        frame = make_frame(
            adapter.config,
            ["C0001", "C0001", "C0002"],
            "label",
            ["Same Term", "Same Term", "Different Term"],
        )
        mock_read_rrf.return_value = frame

        ret = adapter.load()

        assert ret == 2


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))