"""
Abstract base class for all ontology adapters.

Defines the shared initialisation (loading and validating a YAML config),
the shared load() procedure (skip check, merging, cleaning, prefixing),
the abstract _loadFrames() interface that every concrete adapter must
implement, and the common to_csv() method for writing EAV data to disk.
"""

from __future__ import annotations

from abc                import ABC, abstractmethod
from pydantic           import ValidationError
from .BaseAdapterConfig import BaseAdapterConfig
from .BaseAdapterUtils  import isFile, isFolder, createFolder, writeHugeCSV, childrenClass
from logger             import Logger
import pandas           as pd
import yaml
import os

# Key under which adapter settings are expected to live in the YAML config file.
configuration_section: str = "adapter"

# Default path to the config file, used if no path is explicitly passed in.
standard_directory: str    = "./config/config.yaml"


class BaseAdapter(ABC):
    """
    Abstract base class for all ontology adapters.

    Handles loading and validating shared configuration (input/output
    paths, CSV formatting options, ID prefix) from a YAML file, the
    shared steps of `load()`, and a common `to_csv()` method for writing
    the loaded EAV data to disk. Concrete subclasses (e.g. HPOAdapter,
    SCTAdapter) must implement `_loadFrames()` to read their specific
    ontology source format, and may override `_clean()` for
    source-specific cleaning.
    """

    # Name of the ontology, used in log messages.
    ontology_name: str  = "ontology"

    # Prefix used if the config section doesn't set `prefix`.
    default_prefix: str = ""

    def __init__(self, config: str = standard_directory, adapter_name: str = ""):
        """
        Load and validate adapter configuration from a YAML file.

        Parameters
        ----------
        config : str, optional
            Path to the YAML configuration file.
        adapter_name : str, optional
            Key within the "adapter" section of the config file to load.
            If empty, the "adapter" section itself is used directly.

        Raises
        ------
        ValueError
            If the section is missing or not a mapping, or if its values
            are invalid (e.g. unknown keys or wrong types).
        """
        # Initialise instance attributes explicitly so each instance has
        # its own config and data, rather than sharing class-level defaults.
        self.config: BaseAdapterConfig = None
        self.data: pd.DataFrame        = None

        # Open and parse the YAML config file.
        with open(config, "r") as f:
            raw = yaml.safe_load(f)

        # Walk down to the section, e.g. "adapter" -> "sct", raising a
        # clear error naming the missing section and the keys that exist.
        keys = [configuration_section]
        if adapter_name:
            keys.append(adapter_name)

        section = raw
        for depth, key in enumerate(keys):
            path = ".".join(keys[:depth + 1])
            if not isinstance(section, dict):
                raise ValueError(
                    f"Section '{path}' not found in configuration file "
                    f"'{config}': its parent is empty or not a mapping."
                )
            if key not in section:
                raise ValueError(
                    f"Section '{path}' not found in configuration file "
                    f"'{config}'. Available keys: {sorted(section)}."
                )
            section = section[key]

        path = ".".join(keys)
        if not isinstance(section, dict):
            raise ValueError(
                f"Section '{path}' in configuration file '{config}' is "
                f"empty or not a mapping."
            )

        # Validate/coerce the section into a BaseAdapterConfig model. The
        # adapter's default prefix applies unless the section sets one.
        try:
            self.config = BaseAdapterConfig.model_validate(
                {"prefix": self.default_prefix, **section}
            )
        except ValidationError as e:
            raise ValueError(
                f"Invalid section '{path}' in configuration file "
                f"'{config}':\n{e}"
            ) from e

    @abstractmethod
    def _loadFrames(self) -> list[pd.DataFrame]:
        """
        Read the configured input files and convert them to EAV rows.

        Concrete subclasses must implement this for their ontology source
        format. Called by `load()` only if input files are configured and
        loading isn't skipped.

        Returns
        -------
        list[pd.DataFrame]
            One EAV DataFrame per input file or extractor. None entries
            and empty frames are allowed; `load()` skips them.
        """
        return []

    def _clean(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Apply source-specific cleaning to the merged EAV data.

        Called by `load()` after rows without an ID or value are removed,
        and before duplicates are removed and the prefix is added. Does
        nothing by default; subclasses override it as needed.
        """
        return data

    def load(self) -> int:
        """
        Load and parse the ontology from the files specified in the
        configuration file, and store the EAV rows in self.data.

        Reads the input via `_loadFrames()`, merges the frames, removes
        rows without an ID or value, applies `_clean()`, removes
        duplicate (id, attribute, value) rows and adds the configured
        prefix. Does nothing if no input files are configured, or if
        `skip_if_present` is set and the output file already exists.

        Returns
        -------
        int
            Number of EAV rows loaded into self.data.
        """
        ret = 0
        l = Logger()

        if self.config.input_files:

            output_file = os.path.join(
                self.config.output_folder,
                self.config.output_file
            )

            if isFile(output_file) and self.config.skip_if_present:
                l.log("Skipping loading since output file is already present.")
            else:
                l.log(f"Loading {self.ontology_name} from "
                      f"{len(self.config.input_files)} files...")

                frames = [
                    frame for frame in self._loadFrames()
                    if frame is not None and len(frame) > 0
                ]

                l.log("Loading completed.")

                if frames:
                    l.log("Merging data...")
                    self.data = pd.concat(frames, ignore_index=True)
                    l.log("Merging data completed.")
                    ret = len(self.data)
                    l.log(f"Found {ret} entities/rows in total.")

                    id_column        = self.config.id_column
                    attribute_column = self.config.attribute_column
                    value_column     = self.config.value_column

                    # Remove rows without an identifier — they cannot be
                    # assigned to a concept.
                    l.log("Removing rows without an ID...")
                    self.data = self.data[
                        (self.data[id_column].notna()) &
                        (self.data[id_column] != "")
                    ]
                    l.log("Removing rows without an ID completed.")
                    ret = len(self.data)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                    # Remove rows without a value — empty terms, codes or
                    # definitions add no information and can cause issues
                    # downstream (e.g. empty cells in the EAV CSV).
                    l.log("Removing rows without values...")
                    self.data = self.data[
                        (self.data[value_column].notna()) &
                        (self.data[value_column] != "")
                    ]
                    l.log("Removing rows without values completed.")
                    ret = len(self.data)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                    self.data = self._clean(self.data)

                    # Remove exact duplicates across (id, attribute, value) —
                    # e.g. the same term from several sources; only the
                    # first row's additional info is kept.
                    l.log("Removing duplicate rows...")
                    self.data = self.data.drop_duplicates(subset=[
                        id_column,
                        attribute_column,
                        value_column
                    ]).reset_index(drop=True)
                    l.log("Removing duplicate rows completed.")
                    ret = len(self.data)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                    if self.config.prefix:
                        l.log("Adding prefix...")
                        # Add the prefix to the id column
                        self.data[id_column] = self.config.prefix + self.data[id_column].astype(str)

                        # Add the prefix to the value column of child rows,
                        # whose values are IDs as well
                        child_mask = self.data[attribute_column] == childrenClass
                        self.data.loc[child_mask, value_column] = (
                            self.config.prefix + self.data.loc[child_mask, value_column].astype(str)
                        )
                        l.log("Adding prefix completed.")
                else:
                    l.log("No data found. Are the configured input files correct?")

                l.log(f"Loading {self.ontology_name} from "
                      f"{len(self.config.input_files)} files completed.")

        else:
            l.log("No input files found. Were they set in the "
                  "configuration file?")

        return ret

    def to_csv(self) -> int:
        """
        Write self.data to disk at the configured output location.

        Uses the configured delimiter and encoding. The output folder is
        created automatically if it does not already exist. Shared across
        all adapters, since the write logic itself doesn't depend on which
        ontology was loaded.

        Returns
        -------
        int
            Number of rows written to the CSV file.
        """
        # Create the output folder if it does not exist yet.
        if not isFolder(self.config.output_folder):
            createFolder(self.config.output_folder)

        return writeHugeCSV(
            self.data,
            os.path.join(
                self.config.output_folder,
                self.config.output_file
            ),
            self.config.delimiter,
            self.config.encoding
        )
