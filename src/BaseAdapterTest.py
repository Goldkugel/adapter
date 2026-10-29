"""
Tests for BaseAdapter.

Contains three test classes:
- TestBaseAdapterConfigErrors: clear errors for missing or invalid
  configuration sections.
- TestBaseAdapterPrefix: the adapter's default prefix and the configured
  prefix.
- TestBaseAdapterLoad: the shared steps of load() (merging, cleaning,
  the _clean() hook, prefixing).
"""

from __future__ import annotations

import pytest
import pandas as pd
import yaml

from unittest.mock     import patch
from .BaseAdapter      import BaseAdapter
from .BaseAdapterUtils import labelClass, childrenClass


class DummyAdapter(BaseAdapter):
    """Minimal concrete adapter returning the frames it was given."""

    ontology_name  = "dummy"
    default_prefix = "DUMMY:"

    def __init__(self, config: str, frames: list | None = None):
        super().__init__(config, "dummy")
        self.frames  = frames or []
        self.cleaned = False

    def _loadFrames(self) -> list[pd.DataFrame]:
        return self.frames

    def _clean(self, data: pd.DataFrame) -> pd.DataFrame:
        self.cleaned = True
        return data[data["value"] != "dropped by _clean"]


def write_config(tmp_path, content) -> str:
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(content, f)
    return str(path)


def make_frame(ids, attributes, values):
    return pd.DataFrame({
        "id"        : ids,
        "attribute" : attributes,
        "value"     : values,
        "additional": [{} for _ in ids],
    })


class TestBaseAdapterConfigErrors:

    def test_missing_adapter_section_names_the_section(self, tmp_path):
        path = write_config(tmp_path, {"logger": {}})
        with pytest.raises(ValueError, match=r"Section 'adapter' not found.*\['logger'\]"):
            DummyAdapter(path)

    def test_missing_adapter_name_lists_available_sections(self, tmp_path):
        path = write_config(tmp_path, {"adapter": {"hpo": {}, "sct": {}}})
        with pytest.raises(ValueError, match=r"Section 'adapter.dummy' not found.*\['hpo', 'sct'\]"):
            DummyAdapter(path)

    def test_empty_file_is_reported(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text("")
        with pytest.raises(ValueError, match="Section 'adapter' not found"):
            DummyAdapter(str(path))

    def test_empty_section_is_reported(self, tmp_path):
        path = write_config(tmp_path, {"adapter": {"dummy": None}})
        with pytest.raises(ValueError, match="'adapter.dummy'.*empty or not a mapping"):
            DummyAdapter(path)

    def test_invalid_values_name_the_section(self, tmp_path):
        path = write_config(tmp_path, {"adapter": {"dummy": {"unknown_key": 1}}})
        with pytest.raises(ValueError, match=r"Invalid section 'adapter.dummy'(.|\n)*unknown_key"):
            DummyAdapter(path)


class TestBaseAdapterPrefix:

    def test_default_prefix_applies_when_not_configured(self, tmp_path):
        path = write_config(tmp_path, {"adapter": {"dummy": {}}})
        assert DummyAdapter(path).config.prefix == "DUMMY:"

    def test_configured_prefix_overrides_default(self, tmp_path):
        path = write_config(tmp_path, {"adapter": {"dummy": {"prefix": ""}}})
        assert DummyAdapter(path).config.prefix == ""


class TestBaseAdapterLoad:

    @patch("os.path.isfile", return_value=False)
    def test_load_cleans_merges_and_prefixes(self, mock_is_file, tmp_path):
        path = write_config(tmp_path, {"adapter": {"dummy": {"input_files": ["x"]}}})
        adapter = DummyAdapter(path, [
            make_frame(["1", "1", ""], [labelClass] * 3, ["A", "A", "No ID"]),
            None,
            make_frame([], [], []),
            make_frame(["1", "2", "3"], [childrenClass, labelClass, labelClass],
                       ["2", "", "dropped by _clean"]),
        ])

        ret = adapter.load()

        assert adapter.cleaned
        assert ret == 2
        assert adapter.data[["id", "attribute", "value"]].values.tolist() == [
            ["DUMMY:1", labelClass,    "A"],
            ["DUMMY:1", childrenClass, "DUMMY:2"],
        ]

    @patch("os.path.isfile", return_value=False)
    def test_empty_prefix_leaves_ids_unchanged(self, mock_is_file, tmp_path):
        path = write_config(tmp_path, {"adapter": {"dummy": {"input_files": ["x"], "prefix": ""}}})
        adapter = DummyAdapter(path, [
            make_frame(["HP:1"], [childrenClass], ["HP:2"]),
        ])

        adapter.load()

        assert adapter.data[["id", "value"]].values.tolist() == [["HP:1", "HP:2"]]

    @patch("os.path.isfile", return_value=False)
    def test_load_without_data_leaves_data_unset(self, mock_is_file, tmp_path):
        path = write_config(tmp_path, {"adapter": {"dummy": {"input_files": ["x"]}}})
        adapter = DummyAdapter(path, [None])

        assert adapter.load() == 0
        assert adapter.data is None


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
