"""
Tests for BaseAdapter.

Contains five test classes:
- TestBaseAdapterConfigErrors: clear errors for missing or invalid
  configuration sections.
- TestBaseAdapterConfigSources: configuration from a YAML path, a dict or
  a BaseAdapterConfig, and configuring the Logger from the same source.
- TestBaseAdapterPrefix: the adapter's default prefix and the configured
  prefix.
- TestBaseAdapterLoad: the shared steps of load() (merging, cleaning,
  the _clean() hook, prefixing).
- TestBaseAdapterToCSV: writing self.data to the configured output file.
"""

from __future__ import annotations

import pathlib
import pytest
import pandas as pd
import yaml

from unittest.mock     import patch
from logger            import Logger, LoggerConfig
from .BaseAdapter      import BaseAdapter
from .BaseAdapterConfig import BaseAdapterConfig
from .BaseAdapterUtils import labelClass, childrenClass


class DummyAdapter(BaseAdapter):
    """Minimal concrete adapter returning the frames it was given."""

    ontology_name  = "dummy"
    default_prefix = "DUMMY:"

    def __init__(self, config, frames: list | None = None):
        super().__init__(config, "dummy")
        self.frames  = frames or []
        self.cleaned = False

    def _loadFrames(self) -> list[pd.DataFrame]:
        return self.frames

    def _clean(self, data: pd.DataFrame) -> pd.DataFrame:
        self.cleaned = True
        return data[data["value"] != "dropped by _clean"]


@pytest.fixture
def fresh_logger():
    """Starts the test with an unconfigured Logger and restores the previous
    singleton state afterwards."""
    saved = (Logger._instance, Logger.config, Logger.start_time)
    Logger._instance  = None
    Logger.config     = None
    Logger.start_time = 0
    yield
    Logger._instance, Logger.config, Logger.start_time = saved


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


class TestBaseAdapterConfigSources:

    def test_accepts_a_path_object(self, tmp_path):
        path = write_config(tmp_path, {"adapter": {"dummy": {"output_file": "x.csv"}}})
        assert DummyAdapter(pathlib.Path(path)).config.output_file == "x.csv"

    def test_missing_file_raises_file_not_found_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            DummyAdapter(str(tmp_path / "missing.yaml"))

    def test_accepts_a_full_configuration_dict(self):
        adapter = DummyAdapter({"adapter": {"dummy": {"output_file": "x.csv"}}})
        assert adapter.config.output_file == "x.csv"
        assert adapter.config.prefix      == "DUMMY:"

    def test_full_configuration_dict_errors_name_the_section(self):
        with pytest.raises(ValueError, match=r"Section 'adapter.dummy' not found in the given configuration dict.*\['hpo'\]"):
            DummyAdapter({"adapter": {"hpo": {}}})

    def test_accepts_a_dict_of_adapter_settings(self):
        adapter = DummyAdapter({"output_file": "x.csv", "prefix": "X:"})
        assert adapter.config.output_file == "x.csv"
        assert adapter.config.prefix      == "X:"

    def test_dict_of_adapter_settings_gets_the_default_prefix(self):
        assert DummyAdapter({}).config.prefix == "DUMMY:"

    def test_rejects_unknown_keys_in_a_dict(self):
        with pytest.raises(ValueError, match=r"Invalid adapter settings in the given dict(.|\n)*unknown_key"):
            DummyAdapter({"unknown_key": 1})

    def test_accepts_a_base_adapter_config_and_copies_it(self):
        config  = BaseAdapterConfig(output_file="x.csv", prefix="X:")
        adapter = DummyAdapter(config)
        assert adapter.config == config

        # Later changes to the passed object must not affect the adapter.
        config.output_file = "changed.csv"
        assert adapter.config.output_file == "x.csv"

    def test_base_adapter_config_without_prefix_gets_the_default_prefix(self):
        assert DummyAdapter(BaseAdapterConfig()).config.prefix == "DUMMY:"

    def test_base_adapter_config_with_explicit_empty_prefix_keeps_it(self):
        assert DummyAdapter(BaseAdapterConfig(prefix="")).config.prefix == ""

    def test_unconfigured_logger_is_configured_from_the_file(self, tmp_path, fresh_logger):
        path = write_config(tmp_path, {
            "logger" : {"folder": str(tmp_path) + "/", "file_name": "file.log"},
            "adapter": {"dummy": {}},
        })
        DummyAdapter(path)
        assert Logger.config.file_name == "file.log"

    def test_unconfigured_logger_is_configured_from_a_full_configuration_dict(
        self, tmp_path, fresh_logger
    ):
        DummyAdapter({
            "logger" : {"folder": str(tmp_path) + "/", "file_name": "dict.log"},
            "adapter": {"dummy": {}},
        })
        assert Logger.config.file_name == "dict.log"

    def test_existing_logger_configuration_is_kept(self, tmp_path, fresh_logger):
        Logger.config = LoggerConfig(folder=str(tmp_path) + "/", file_name="kept.log")
        DummyAdapter({
            "logger" : {"file_name": "ignored.log"},
            "adapter": {"dummy": {}},
        })
        assert Logger.config.file_name == "kept.log"


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


class TestBaseAdapterToCSV:

    def test_to_csv_creates_the_folder_and_uses_the_configured_format(self, tmp_path):
        output_folder = tmp_path / "out" / "dummy"
        adapter = DummyAdapter({
            "output_folder": str(output_folder),
            "output_file"  : "dummy.csv",
            "delimiter"    : "|",
        })
        adapter.data = make_frame(["DUMMY:1"], [labelClass], ["A; B"])

        assert adapter.to_csv() == 1

        back = pd.read_csv(output_folder / "dummy.csv", sep="|", dtype=str)
        assert back[["id", "attribute", "value"]].values.tolist() == [
            ["DUMMY:1", labelClass, "A; B"],
        ]

    @patch("os.path.isfile", return_value=False)
    def test_load_then_to_csv_writes_the_loaded_rows(self, mock_is_file, tmp_path):
        adapter = DummyAdapter(
            {"input_files": ["x"], "output_folder": str(tmp_path), "output_file": "d.csv"},
            [make_frame(["1", "1"], [labelClass, childrenClass], ["A", "2"])],
        )
        adapter.load()

        assert adapter.to_csv() == 2

        back = pd.read_csv(tmp_path / "d.csv", sep=";", dtype=str)
        assert back[["id", "value"]].values.tolist() == [["DUMMY:1", "A"], ["DUMMY:1", "DUMMY:2"]]


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
