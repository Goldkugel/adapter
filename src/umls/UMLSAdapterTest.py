"""
Tests for UMLSAdapter and UMLSAdapterUtils.

Contains four test classes:
- TestUMLSAdapterInit: unit tests for configuration loading via __init__.
- TestUMLSAdapterLoadSkipping: tests for the skip-if-present and
  no-input-files early-exit paths.
- TestUMLSAdapterLoad: tests for file reading, merging, cleaning, and
  the row count returned by load().
- TestUMLSAdapterUtilsParsing: tests for reading real RRF content.
"""

from __future__ import annotations

import os

from unittest.mock  import patch
from .UMLSAdapter       import UMLSAdapter
from .UMLSAdapterUtils  import readRRFFileByPath
from .                  import UMLSAdapterUtils
from ..BaseAdapterUtils import referenceClass, labelClass
from .UMLSAdapterUtils  import sourceAbbreviation
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
        assert adapter.data.iloc[0][adapter.config.id_column] == "UMLS:C0001"

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


class TestUMLSAdapterUtilsParsing:
    """
    Tests for reading real RRF content: strings must be read verbatim,
    without CSV quote handling or NA detection, and only the used
    columns and the kept rows must be loaded.
    """

    def test_mrconso_strings_are_read_verbatim(self, tmp_path):
        rows = [
            ["C1", "ENG", "P", "L1", "PF", "S1", "Y", "A1", "", "SC1", "", "MSH", "PT", "D1", '"Hazardous" stuff', "0", "N", ""],
            ["C2", "ENG", "P", "L2", "PF", "S2", "Y", "A2", "", "SC2", "", "MSH", "AB", "D2", "NA", "0", "N", ""],
            ["C3", "ENG", "P", "L3", "PF", "S3", "Y", "A3", "", "SC3", "", "MSH", "PT", "D3", '"Unbalanced quote', "0", "N", ""],
            ["C4", "ENG", "P", "L4", "PF", "S4", "Y", "A4", "", "SC4", "", "MSH", "PT", "D4", "Plain", "0", "N", ""],
        ]
        path = tmp_path / "MRCONSO.RRF"
        path.write_text("".join("|".join(r) + "|\n" for r in rows), encoding="utf-8")

        frame = readRRFFileByPath(str(path), "id", "attribute", "value", "additional", "utf-8", "|")

        strings = frame[frame["attribute"] != referenceClass]
        # The last "NA" is C2's fallback label (C2 has no PT/PN string).
        assert strings["value"].tolist() == ['"Hazardous" stuff', "NA", '"Unbalanced quote', "Plain", "NA"]

    def test_concept_without_pt_or_pn_gets_label_from_preferred_atom(self, tmp_path):
        # TS, STT, ISPREF are columns 3, 5 and 7; TTY is column 13.
        rows = [
            # C1 has a PT string, so it gets no extra label.
            ["C1", "ENG", "S", "L1", "VO", "S1", "N", "A1", "", "", "", "MSH", "SY", "D1", "C1 synonym", "0", "N", ""],
            ["C1", "ENG", "P", "L2", "PF", "S2", "Y", "A2", "", "", "", "MSH", "PT", "D1", "C1 preferred", "0", "N", ""],
            # C2 has only SY/AB/MH strings: the TS=P, STT=PF, ISPREF=Y atom wins.
            ["C2", "ENG", "S", "L3", "PF", "S3", "Y", "A3", "", "", "", "MSH", "SY", "D2", "C2 secondary", "0", "N", ""],
            ["C2", "ENG", "P", "L4", "VO", "S4", "Y", "A4", "", "", "", "MSH", "SY", "D2", "C2 variant", "0", "N", ""],
            ["C2", "ENG", "P", "L4", "PF", "S5", "Y", "A5", "", "", "", "NCI", "MH", "D2", "C2 preferred", "0", "N", ""],
            # A suppressed atom is never used, even if it is preferred.
            ["C3", "ENG", "P", "L6", "PF", "S6", "Y", "A6", "", "", "", "MSH", "MH", "D3", "C3 suppressed", "0", "O", ""],
            ["C3", "ENG", "S", "L7", "VO", "S7", "N", "A7", "", "", "", "MSH", "MH", "D3", "C3 kept", "0", "N", ""],
        ]
        path = tmp_path / "MRCONSO.RRF"
        path.write_text("".join("|".join(r) + "|\n" for r in rows), encoding="utf-8")

        frame = readRRFFileByPath(str(path), "id", "attribute", "value", "additional", "utf-8", "|")

        labels = frame[frame["attribute"] == labelClass]
        assert sorted(zip(labels["id"], labels["value"])) == [
            ("C1", "C1 preferred"),
            ("C2", "C2 preferred"),
            ("C3", "C3 kept"),
        ]
        c2 = labels[labels["id"] == "C2"].iloc[0]
        assert c2["additional"] == {sourceAbbreviation: "NCI"}

    def test_mrconso_reader_keeps_used_columns_and_filters_every_chunk(self, tmp_path, monkeypatch):
        # A chunk size of 2 spreads the rows over three chunks, so the
        # filter must be applied to each chunk, not only the first.
        monkeypatch.setattr(UMLSAdapterUtils, "rrfChunkSize", 2)
        rows = [
            ["C1", "ENG", "P", "L1", "PF", "S1", "Y", "A1", "", "", "", "MSH", "PT", "D1", "Kept one", "0", "N", ""],
            ["C2", "GER", "P", "L2", "PF", "S2", "Y", "A2", "", "", "", "MSH", "PT", "D2", "German", "0", "N", ""],
            ["C3", "ENG", "P", "L3", "PF", "S3", "Y", "A3", "", "", "", "MSH", "PT", "D3", "Suppressed", "0", "O", ""],
            ["C4", "ENG", "P", "L4", "PF", "S4", "Y", "A4", "", "", "", "MSH", "SY", "D4", "Kept two", "0", "N", ""],
            ["C5", "FRE", "P", "L5", "PF", "S5", "Y", "A5", "", "", "", "MSH", "PT", "D5", "French", "0", "N", ""],
        ]
        path = tmp_path / "MRCONSO.RRF"
        path.write_text("".join("|".join(r) + "|\n" for r in rows), encoding="utf-8")

        frame = UMLSAdapterUtils.readMRCONSOFile(str(path), "utf-8", "|")

        assert list(frame.columns) == UMLSAdapterUtils.mrconsoUsedColumns
        assert frame["STR"].tolist() == ["Kept one", "Kept two"]

    def test_mrdef_reader_drops_suppressed_rows(self, tmp_path):
        rows = [
            ["C1", "A1", "AT1", "", "MSH", "Kept", "N", ""],
            ["C2", "A2", "AT2", "", "MSH", "Suppressed", "E", ""],
        ]
        path = tmp_path / "MRDEF.RRF"
        path.write_text("".join("|".join(r) + "|\n" for r in rows), encoding="utf-8")

        frame = readRRFFileByPath(str(path), "id", "attribute", "value", "additional", "utf-8", "|")

        assert frame["value"].tolist() == ["Kept"]

    def test_unknown_file_name_returns_none(self, tmp_path):
        path = tmp_path / "MRSTY.RRF"
        path.write_text("C1|T047|B2.2.1.2.1|Disease or Syndrome|AT1||\n", encoding="utf-8")

        assert readRRFFileByPath(str(path), "id", "attribute", "value", "additional", "utf-8", "|") is None

    def test_mrsty_reader_reads_all_columns(self, tmp_path):
        # MRSTY has a reader but is not wired into readRRFFileByPath yet.
        path = tmp_path / "MRSTY.RRF"
        path.write_text("C1|T047|B2.2.1.2.1|Disease or Syndrome|AT1||\n", encoding="utf-8")

        frame = UMLSAdapterUtils.readMRSTYFile(str(path), "utf-8", "|")

        assert list(frame.columns) == UMLSAdapterUtils.mrstyColumns
        assert frame.values.tolist() == [["C1", "T047", "B2.2.1.2.1", "Disease or Syndrome", "AT1", ""]]

    def test_mrconso_codes_become_references_with_their_source(self, tmp_path):
        rows = [
            ["C1", "ENG", "P", "L1", "PF", "S1", "Y", "A1", "", "", "", "MSH", "PT", "D001", "Term", "0", "N", ""],
            ["C1", "ENG", "S", "L2", "VO", "S2", "N", "A2", "", "", "", "SNOMEDCT_US", "FN", "404684003", "Other TTY", "0", "N", ""],
        ]
        path = tmp_path / "MRCONSO.RRF"
        path.write_text("".join("|".join(r) + "|\n" for r in rows), encoding="utf-8")

        frame = readRRFFileByPath(str(path), "id", "attribute", "value", "additional", "utf-8", "|")

        refs = frame[frame["attribute"] == referenceClass]
        assert sorted(zip(refs["value"], [a[sourceAbbreviation] for a in refs["additional"]])) == [
            ("404684003", "SNOMEDCT_US"),
            ("D001", "MSH"),
        ]
        # The FN string produces no synonym, only its code a reference.
        assert "Other TTY" not in frame["value"].tolist()

    def test_empty_rrf_file_gives_empty_frame(self, tmp_path):
        path = tmp_path / "MRCONSO.RRF"
        path.write_text("", encoding="utf-8")

        frame = UMLSAdapterUtils.readMRCONSOFile(str(path), "utf-8", "|")

        assert frame.empty
        assert list(frame.columns) == UMLSAdapterUtils.mrconsoUsedColumns


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))