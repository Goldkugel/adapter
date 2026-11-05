"""
Tests for BaseAdapterUtils.

Contains four test classes:
- TestFilesystemHelpers: isFile, isFolder and createFolder.
- TestWriteCSV: the CSV format (quoting, delimiter, encoding, the
  additional dict) and the no-data / no-file paths.
- TestWriteHugeCSV: the atomic write via a temporary file, including
  cleaning up the temporary file when nothing is written or the write
  fails.
- TestMergeAdditional: merging the additional dicts of duplicate rows.
"""

from __future__ import annotations

import ast
import os
import threading
import pytest
import pandas as pd

from unittest.mock        import patch
from adapter.BaseAdapterUtils import (
    isFile, isFolder, createFolder, writeCSV, writeHugeCSV,
    labelClass, synonymClass, mergeAdditional, additionalSeparator,
)


def make_frame():
    """A small EAV DataFrame with values that need quoting."""
    return pd.DataFrame({
        "id"        : ["HP:1", "HP:1", "HP:2"],
        "attribute" : [labelClass, synonymClass, labelClass],
        "value"     : ["Plain", 'Has "quotes"; and a delimiter', "Line\nbreak"],
        "additional": [{}, {"semantic_class": "exact"}, {}],
    })


def temporary_files(folder) -> list[str]:
    """The temporary files writeHugeCSV() left in `folder`."""
    return [name for name in os.listdir(folder) if name.endswith(".tmp")]


def read_back(path, separator=";", encoding="utf-8"):
    """Read a CSV written by writeCSV, keeping every field a string."""
    return pd.read_csv(path, sep=separator, encoding=encoding, dtype=str, keep_default_na=False)


class TestFilesystemHelpers:

    def test_is_file_and_is_folder(self, tmp_path):
        file = tmp_path / "file.txt"
        file.write_text("x")

        assert isFile(str(file))
        assert not isFile(str(tmp_path))
        assert not isFile(str(tmp_path / "missing.txt"))

        assert isFolder(str(tmp_path))
        assert not isFolder(str(file))
        assert not isFolder(str(tmp_path / "missing"))

    def test_create_folder_creates_missing_parents(self, tmp_path):
        folder = tmp_path / "a" / "b"

        assert createFolder(str(folder)) is True
        assert folder.is_dir()

    def test_create_folder_tolerates_a_folder_created_meanwhile(self, tmp_path):
        """E.g. by another job of a Slurm array, between the check and makedirs."""
        with patch("adapter.BaseAdapterUtils.isFolder", return_value=False):
            assert createFolder(str(tmp_path)) is True

    def test_create_folder_returns_false_if_it_exists(self, tmp_path):
        assert createFolder(str(tmp_path)) is False


class TestWriteCSV:

    def test_round_trip_keeps_values_and_additional_dict(self, tmp_path):
        path = str(tmp_path / "out.csv")
        data = make_frame()

        assert writeCSV(data, path) == 3

        back = read_back(path)
        assert list(back.columns) == list(data.columns)
        assert back["value"].tolist() == data["value"].tolist()
        # The additional column is a Python dict literal.
        assert [ast.literal_eval(v) for v in back["additional"]] == data["additional"].tolist()

    def test_every_field_is_quoted_and_the_index_is_not_written(self, tmp_path):
        path = str(tmp_path / "out.csv")
        writeCSV(make_frame().iloc[[0]], path)

        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()

        assert lines == [
            '"id";"attribute";"value";"additional"',
            f'"HP:1";"{labelClass}";"Plain";"{{}}"',
        ]

    def test_separator_and_encoding_are_used(self, tmp_path):
        path = str(tmp_path / "out.csv")
        data = pd.DataFrame({"id": ["1"], "value": ["Ménière"]})

        writeCSV(data, path, separator="\t", encoding="latin-1")

        assert read_back(path, "\t", "latin-1")["value"].tolist() == ["Ménière"]

    def test_no_data_writes_nothing(self, tmp_path):
        path = tmp_path / "out.csv"
        assert writeCSV(None, str(path)) == 0
        assert not path.exists()

    @pytest.mark.parametrize("file", [None, ""])
    def test_no_file_writes_nothing(self, file):
        assert writeCSV(make_frame(), file) == 0


class TestWriteHugeCSV:

    def test_writes_the_target_and_removes_the_temporary_file(self, tmp_path):
        path = str(tmp_path / "out.csv")

        assert writeHugeCSV(make_frame(), path) == 3

        assert read_back(path)["value"].tolist() == make_frame()["value"].tolist()
        assert temporary_files(tmp_path) == []

    def test_replaces_an_existing_file(self, tmp_path):
        path = tmp_path / "out.csv"
        path.write_text("old content")

        writeHugeCSV(make_frame(), str(path))

        assert len(read_back(str(path))) == 3

    def test_empty_frame_keeps_the_existing_file(self, tmp_path):
        path = tmp_path / "out.csv"
        path.write_text("old content")

        assert writeHugeCSV(make_frame().iloc[0:0], str(path)) == 0

        assert path.read_text() == "old content"
        assert temporary_files(tmp_path) == []

    def test_failed_write_keeps_the_existing_file_and_cleans_up(self, tmp_path):
        path = tmp_path / "out.csv"
        path.write_text("old content")

        def fail_halfway(self, file, **kwargs):
            # Leave a partial temporary file behind, as an interrupted
            # write would.
            with open(file, "w") as f:
                f.write("partial")
            raise OSError("disk full")

        with patch.object(pd.DataFrame, "to_csv", fail_halfway):
            with pytest.raises(OSError, match="disk full"):
                writeHugeCSV(make_frame(), str(path))

        assert path.read_text() == "old content"
        assert temporary_files(tmp_path) == []

    def test_concurrent_writers_do_not_share_the_temporary_file(self, tmp_path):
        """
        Two threads writing the same file at once each replace it with their
        complete content; with one shared temporary file, one would move the
        other's half-written file into place, or fail to find its own.
        """
        path = str(tmp_path / "out.csv")
        both_written = threading.Barrier(2)
        errors = []

        def write(data, file, separator, encoding):
            with open(file, "w") as f:
                f.write(data)
            both_written.wait(timeout=10)
            return 1

        def writer(text):
            try:
                writeHugeCSV(text, path)
            except Exception as e:
                errors.append(e)

        with patch("adapter.BaseAdapterUtils.writeCSV", write):
            threads = [threading.Thread(target=writer, args=(t * 1000,)) for t in ("a", "b")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        assert errors == []
        assert open(path).read() in ("a" * 1000, "b" * 1000)
        assert temporary_files(tmp_path) == []

    def test_no_data_or_no_file_writes_nothing(self, tmp_path):
        path = tmp_path / "out.csv"

        assert writeHugeCSV(None, str(path)) == 0
        assert writeHugeCSV(make_frame(), "") == 0
        assert list(tmp_path.iterdir()) == []


class TestMergeAdditional:

    def test_different_values_are_joined_in_row_order(self):
        merged = mergeAdditional([
            {"semantic_class": "exact",   "source_type": "layperson"},
            {"semantic_class": "related", "source_type": "layperson"},
        ])

        assert merged == {
            "semantic_class": "exact" + additionalSeparator + "related",
            "source_type"   : "layperson",
        }
        assert merged["semantic_class"] == "exact, related"

    def test_every_value_is_joined_once(self):
        merged = mergeAdditional([{"k": "a"}, {"k": "b"}, {"k": "a"}, {"k": "b"}])

        assert merged == {"k": "a, b"}

    def test_keys_of_only_some_entries_are_kept(self):
        merged = mergeAdditional([{"a": "1"}, {"b": "2"}, {}])

        assert merged == {"a": "1", "b": "2"}

    def test_equal_values_keep_their_type(self):
        assert mergeAdditional([{"n": 1}, {"n": 1}]) == {"n": 1}

    def test_entries_that_are_not_dicts_add_nothing(self):
        assert mergeAdditional([float("nan"), None, {"a": "1"}]) == {"a": "1"}
        assert mergeAdditional([]) == {}

    def test_entries_are_not_changed(self):
        entries = [{"a": "1"}, {"a": "2"}]

        mergeAdditional(entries)

        assert entries == [{"a": "1"}, {"a": "2"}]
