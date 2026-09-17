"""
Tests for SCTAdapter and SCTAdapterUtils.

Contains five test classes:
- TestSCTAdapterInit: unit tests for configuration loading via __init__.
- TestFindInputFile: unit tests for the _findInputFile helper method.
- TestSCTAdapterLoadSkipping: tests for the skip-if-present and no-input-files paths.
- TestSCTAdapterLoadConceptHandling: tests for Concept file reading and filtering.
- TestSCTAdapterLoadMerging: tests for DataFrame merging and row count.
"""

from __future__ import annotations

import os

from unittest.mock      import MagicMock, patch, call
from .SCTAdapter        import SCTAdapter
from .SCTAdapterUtils   import (
    conceptPrefix, rf2SourceId,
    descriptionPrefix, relationshipPrefix,
)
import pandas           as pd
import yaml
import pytest

CONCEPT_FILE      = "sct2_Concept_Full_INT_20260701.txt"
DESCRIPTION_FILE  = "sct2_Description_Full-en_INT_20260701.txt"
RELATIONSHIP_FILE = "sct2_Relationship_Full_INT_20260701.txt"

# unittest.mock patches names where they are looked up, not where they
# are defined. SCTAdapter imports readConceptFile, readRF2FileByPath,
# getConcepts, and removeNotActiveConcepts into its own namespace, so
# they must be patched under "src.sct.SCTAdapter" rather than under
# "src.sct.SCTAdapterUtils" where they are originally defined.
PATCH_TARGET = "src.sct.SCTAdapter"


@pytest.fixture
def config_path(tmp_path):
    config = {
        "adapter": {
            "sct": {
                "input_files": [CONCEPT_FILE, DESCRIPTION_FILE, RELATIONSHIP_FILE],
            }
        }
    }
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(config, f)
    return str(path)


@pytest.fixture
def adapter(config_path):
    return SCTAdapter(config=config_path)


def make_frame(config, id_values, attribute, value_values):
    """Build a minimal EAV DataFrame for use in tests."""
    n = len(id_values)
    return pd.DataFrame({
        config.id_column        : id_values,
        config.attribute_column : [attribute] * n,
        config.value_column     : value_values,
        config.additional_column: [{} for _ in range(n)],
    })


class TestSCTAdapterInit:
    """
    Unit tests for SCTAdapter.__init__.

    Verifies that configuration values are correctly loaded from the
    YAML file and that self.data is unset before load() is called.
    """

    def test_init_loads_config_from_yaml(self, adapter):
        assert adapter.config.input_files == [
            CONCEPT_FILE, DESCRIPTION_FILE, RELATIONSHIP_FILE
        ]

    def test_data_is_unset_before_load(self, adapter):
        assert adapter.data is None


class TestFindInputFile:
    """
    Unit tests for SCTAdapter._findInputFile.

    Verifies that the helper correctly identifies, raises on missing,
    and raises on ambiguous prefix matches.
    """

    def test_returns_the_single_matching_file(self, adapter):
        assert adapter._findInputFile(conceptPrefix) == CONCEPT_FILE

    def test_raises_file_not_found_when_no_file_matches(self, adapter):
        with pytest.raises(FileNotFoundError):
            adapter._findInputFile("der2_sRefset_SimpleMapFull")

    def test_raises_value_error_when_multiple_files_match(self, tmp_path):
        config = {
            "adapter": {
                "sct": {
                    "input_files": [
                        "sct2_Relationship_Full_INT_20260701.txt",
                        "sct2_Relationship_Snapshot_INT_20260701.txt",
                    ]
                }
            }
        }
        path = tmp_path / "config2.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(config, f)
        adapter = SCTAdapter(config=str(path))

        with pytest.raises(ValueError):
            adapter._findInputFile("sct2_Relationship_")


class TestSCTAdapterLoadSkipping:
    """
    Tests for the early-exit paths in SCTAdapter.load():
    no input files configured, and skip_if_present when output exists.
    """

    def test_load_returns_zero_when_no_input_files_configured(self, tmp_path):
        config = {"adapter": {"sct": {"input_files": []}}}
        path = tmp_path / "config.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(config, f)
        adapter = SCTAdapter(config=str(path))

        assert adapter.load() == 0
        assert adapter.data is None

    @patch("os.path.isfile", return_value=True)
    @patch(f"{PATCH_TARGET}.readConceptFile")
    def test_load_skips_when_output_present_and_skip_if_present_true(
        self, mock_read_concept, mock_is_file, tmp_path
    ):
        config = {
            "adapter": {
                "sct": {
                    "input_files": [CONCEPT_FILE, DESCRIPTION_FILE],
                    "skip_if_present": True,
                }
            }
        }
        path = tmp_path / "config.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(config, f)
        adapter = SCTAdapter(config=str(path))

        ret = adapter.load()

        assert ret == 0
        assert adapter.data is None
        mock_read_concept.assert_not_called()


class TestSCTAdapterLoadConceptHandling:
    """
    Tests for the Concept file reading, active-concept extraction,
    and EAV extraction loop in SCTAdapter.load().
    """

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_TARGET}.readRF2FileByPath")
    @patch(f"{PATCH_TARGET}.removeNotActiveConcepts")
    @patch(f"{PATCH_TARGET}.getConcepts")
    @patch(f"{PATCH_TARGET}.readConceptFile")
    def test_concept_file_is_read_once_from_its_full_path(
        self, mock_read_concept, mock_get_concepts, mock_remove_inactive,
        mock_read_rf2, mock_is_file, adapter
    ):
        mock_read_concept.return_value = MagicMock(name="concept_df")
        mock_get_concepts.return_value = ["100001", "100002"]
        mock_read_rf2.return_value = make_frame(adapter.config, ["100001"], "label", ["x"])
        mock_remove_inactive.return_value = make_frame(adapter.config, ["100001"], "label", ["x"])

        adapter.load()

        expected_path = os.path.join(adapter.config.input_folder, CONCEPT_FILE)
        mock_read_concept.assert_called_once_with(
            expected_path,
            adapter.config.encoding,
            adapter.config.separator,
        )

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_TARGET}.readRF2FileByPath")
    @patch(f"{PATCH_TARGET}.removeNotActiveConcepts")
    @patch(f"{PATCH_TARGET}.getConcepts")
    @patch(f"{PATCH_TARGET}.readConceptFile")
    def test_get_concepts_called_with_concept_dataframe_and_rf2SourceId(
        self, mock_read_concept, mock_get_concepts, mock_remove_inactive,
        mock_read_rf2, mock_is_file, adapter
    ):
        concept_df = MagicMock(name="concept_df")
        mock_read_concept.return_value = concept_df
        mock_get_concepts.return_value = ["100001"]
        mock_read_rf2.return_value = make_frame(adapter.config, ["100001"], "label", ["x"])
        mock_remove_inactive.return_value = make_frame(adapter.config, ["100001"], "label", ["x"])

        adapter.load()

        mock_get_concepts.assert_called_once_with(concept_df, rf2SourceId)

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_TARGET}.readRF2FileByPath")
    @patch(f"{PATCH_TARGET}.removeNotActiveConcepts")
    @patch(f"{PATCH_TARGET}.getConcepts")
    @patch(f"{PATCH_TARGET}.readConceptFile")
    def test_concept_file_is_excluded_from_the_readRF2FileByPath_loop(
        self, mock_read_concept, mock_get_concepts, mock_remove_inactive,
        mock_read_rf2, mock_is_file, adapter
    ):
        mock_read_concept.return_value = MagicMock(name="concept_df")
        mock_get_concepts.return_value = ["100001"]
        mock_read_rf2.return_value = make_frame(adapter.config, ["100001"], "label", ["x"])
        mock_remove_inactive.return_value = make_frame(adapter.config, ["100001"], "label", ["x"])

        adapter.load()

        called_paths = [c.args[0] for c in mock_read_rf2.call_args_list]
        assert os.path.join(adapter.config.input_folder, CONCEPT_FILE) not in called_paths
        assert len(called_paths) == 2  # DESCRIPTION_FILE and RELATIONSHIP_FILE


class TestSCTAdapterLoadMerging:
    """
    Tests for the DataFrame merging, deduplication, and row-count
    return value in SCTAdapter.load().
    """

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_TARGET}.readRF2FileByPath")
    @patch(f"{PATCH_TARGET}.removeNotActiveConcepts")
    @patch(f"{PATCH_TARGET}.getConcepts")
    @patch(f"{PATCH_TARGET}.readConceptFile")
    def test_each_read_frame_is_filtered_by_removeNotActiveConcepts(
        self, mock_read_concept, mock_get_concepts, mock_remove_inactive,
        mock_read_rf2, mock_is_file, adapter
    ):
        mock_read_concept.return_value = MagicMock()
        mock_get_concepts.return_value = ["100001", "100002"]
        raw_description_frame  = MagicMock(name="raw_description_frame")
        raw_relationship_frame = MagicMock(name="raw_relationship_frame")
        mock_read_rf2.side_effect = [raw_description_frame, raw_relationship_frame]
        mock_remove_inactive.return_value = make_frame(
            adapter.config, ["100001"], "label", ["x"]
        )

        adapter.load()

        actual_filtered_frames = [c.args[0] for c in mock_remove_inactive.call_args_list]
        assert actual_filtered_frames == [raw_description_frame, raw_relationship_frame]
        for c in mock_remove_inactive.call_args_list:
            assert c.args[1] == adapter.config.id_column
            assert c.args[2] == ["100001", "100002"]

    @patch("os.path.isfile", return_value=False)
    @patch(f"{PATCH_TARGET}.readRF2FileByPath")
    @patch(f"{PATCH_TARGET}.removeNotActiveConcepts")
    @patch(f"{PATCH_TARGET}.getConcepts", return_value=["100001"])
    @patch(f"{PATCH_TARGET}.readConceptFile", return_value=MagicMock())
    def test_frames_are_merged_and_row_count_returned(
        self, mock_read_concept, mock_get_concepts, mock_remove_inactive,
        mock_read_rf2, mock_is_file, adapter
    ):
        mock_read_rf2.side_effect = [MagicMock(), MagicMock()]
        mock_remove_inactive.side_effect = [
            make_frame(adapter.config, ["100001", "100002"], "label", ["A", "B"]),
            make_frame(adapter.config, ["100001"], "child", ["100003"]),
        ]

        ret = adapter.load()

        assert ret == 3
        assert len(adapter.data) == 3
        assert set(adapter.data[adapter.config.attribute_column]) == {"label", "child"}


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))