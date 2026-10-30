"""
Abstract base class for all ontology adapters.

Defines the shared initialisation (loading and validating the config from a
YAML file, a dict or a BaseAdapterConfig), the shared load() procedure
(skip check, merging, cleaning, prefixing), the abstract _loadFrames()
interface that every concrete adapter must implement, and the common
to_csv() method for writing EAV data to disk.
"""

from __future__ import annotations

from abc                import ABC, abstractmethod
from pydantic           import ValidationError
from .BaseAdapterConfig import BaseAdapterConfig
from .BaseAdapterUtils  import isFile, isFolder, createFolder, writeHugeCSV, childrenClass
from logger             import Logger, LoggerConfig
import pandas           as pd
import yaml
import os

# Key under which adapter settings are expected to live in the YAML config file.
configuration_section: str = "adapter"

# Key of the logger settings in the same file (see the logger package).
logger_section: str        = "logger"

# Default path to the config file, used if no path is explicitly passed in.
standard_directory: str    = "./config/config.yaml"


class BaseAdapter(ABC):
    """
    Abstract base class for all ontology adapters.

    Handles loading and validating shared configuration (input/output
    paths, CSV formatting options, ID prefix) from a YAML file, a dict or
    a BaseAdapterConfig, the shared steps of `load()`, and a common
    `to_csv()` method for writing the loaded EAV data to disk. Concrete subclasses (e.g. HPOAdapter,
    SCTAdapter) must implement `_loadFrames()` to read their specific
    ontology source format, and may override `_clean()` for
    source-specific cleaning.
    """

    # Name of the ontology, used in log messages.
    ontology_name: str  = "ontology"

    # Prefix used if the config section doesn't set `prefix`.
    default_prefix: str = ""

    def __init__(
        self,
        config: str | os.PathLike | dict | BaseAdapterConfig = standard_directory,
        adapter_name: str = "",
    ):
        """
        Load and validate the adapter configuration.

        Parameters
        ----------
        config : str, os.PathLike, dict or BaseAdapterConfig, optional
            Where the settings come from:
            - a path to a YAML configuration file with an "adapter" section
              (default: ./config/config.yaml relative to the working
              directory);
            - a dict, either the content of such a file (with an "adapter"
              key and optionally a "logger" key) or just the settings of
              this adapter (the content of e.g. `adapter.sct`);
            - a ready BaseAdapterConfig (a copy is stored). If it does not
              set `prefix` explicitly, the adapter's default prefix applies.

            If the Logger has not been configured yet, it is configured from
            the same source: the "logger" section of the file, or the
            "logger" key of a full configuration dict.
        adapter_name : str, optional
            Key within the "adapter" section of a configuration file or full
            configuration dict to load. If empty, the "adapter" section
            itself is used directly.

        Raises
        ------
        FileNotFoundError
            If the configuration file does not exist.
        ValueError
            If the section is missing or not a mapping, or if its values
            are invalid (e.g. unknown keys or wrong types).
        """
        # Declare the instance attributes. self.data stays None until
        # load() finds data; self.config is set right below.
        self.config: BaseAdapterConfig = None
        self.data: pd.DataFrame        = None

        # Raises before anything else happens if the configuration is
        # missing or invalid, so no adapter exists with a broken config.
        self.config, logger_path, logger_settings = self._resolveConfig(config, adapter_name)

        # The Logger is a process-wide singleton. If the entry point has not
        # configured it yet, configure it from the same source as the
        # adapter: the same YAML file, or the "logger" key of the same dict.
        # Without either, Logger() falls back to ./config/config.yaml.
        if Logger.config is None and logger_path is not None:
            Logger(logger_path)
        elif Logger.config is None and logger_settings is not None:
            Logger.config = LoggerConfig.model_validate(logger_settings)

    def _resolveConfig(
        self,
        config: str | os.PathLike | dict | BaseAdapterConfig,
        adapter_name: str,
    ) -> tuple[BaseAdapterConfig, str | None, dict | None]:
        """
        Turn the `config` argument of __init__ into a BaseAdapterConfig.

        Returns the BaseAdapterConfig, the YAML file it came from if that
        file has a "logger" section (or None), and the "logger" section of a
        full configuration dict (or None), so __init__ can configure the
        Logger from the same source.
        """
        if isinstance(config, BaseAdapterConfig):
            # Copy the given config so later changes by the caller do not
            # silently change the adapter's configuration. The adapter's
            # default prefix applies unless the config sets one explicitly:
            # model_fields_set holds only the fields passed when the model
            # was created, so an explicit prefix="" is kept, while a prefix
            # left at the field default is replaced.
            if "prefix" in config.model_fields_set:
                return config.model_copy(deep=True), None, None
            return config.model_copy(deep=True, update={"prefix": self.default_prefix}), None, None

        logger_path = None
        logger_settings = None

        if isinstance(config, dict):
            # A full configuration (the parsed YAML file) has an "adapter"
            # key, which is not a valid adapter setting itself, so the two
            # kinds of dict cannot be confused.
            if configuration_section not in config:
                return self._validateSection(config, "", "the given dict"), None, None
            raw = config
            source = "the given configuration dict"
            logger_settings = config.get(logger_section)
        else:
            file_path = os.fspath(config)
            # Open and parse the YAML config file.
            with open(file_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            source = f"configuration file '{file_path}'"
            # Only hand the path on to the Logger if the file has logger
            # settings.
            if isinstance(raw, dict) and logger_section in raw:
                logger_path = file_path

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
                    f"Section '{path}' not found in {source}: its parent is "
                    f"empty or not a mapping."
                )
            if key not in section:
                raise ValueError(
                    f"Section '{path}' not found in {source}. "
                    f"Available keys: {sorted(section)}."
                )
            section = section[key]

        return self._validateSection(section, ".".join(keys), source), logger_path, logger_settings

    def _validateSection(self, section: object, path: str, source: str) -> BaseAdapterConfig:
        """
        Validate one adapter section (e.g. the content of `adapter.sct`)
        into a BaseAdapterConfig, raising a ValueError that names the
        section and where it came from.
        """
        # Settings passed directly as a dict have no section path.
        name = f"section '{path}'" if path else "adapter settings"

        if not isinstance(section, dict):
            raise ValueError(f"The {name} in {source} is empty or not a mapping.")

        # Validate/coerce the section into a BaseAdapterConfig model. The
        # adapter's default prefix applies unless the section sets one.
        try:
            return BaseAdapterConfig.model_validate(
                {"prefix": self.default_prefix, **section}
            )
        except ValidationError as e:
            raise ValueError(f"Invalid {name} in {source}:\n{e}") from e

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
        Load and parse the ontology from the input files named in the
        configuration, and store the EAV rows in self.data.

        Reads the input via `_loadFrames()`, merges the frames, removes
        rows without an ID or value, applies `_clean()`, removes
        duplicate (id, attribute, value) rows and adds the configured
        prefix. Does nothing if no input files are configured, or if
        `skip_if_present` is set and the output file already exists.

        Returns
        -------
        int
            Number of EAV rows loaded into self.data (0 if nothing was
            loaded, in which case self.data is left unchanged).
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

                # Drop the None entries (unrecognised files) and empty
                # frames; pd.concat() would fail on an all-None list.
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

                    # The prefix is added last, so the steps above (and
                    # _clean()) always see the IDs as the source has them.
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
