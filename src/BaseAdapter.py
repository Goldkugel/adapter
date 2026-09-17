"""
Abstract base class for all ontology adapters.

Defines the shared initialisation (loading and validating a YAML config),
the abstract load() interface that every concrete adapter must implement,
and the common to_csv() method for writing EAV data to disk.
"""

from __future__ import annotations

from abc                import ABC, abstractmethod
from .BaseAdapterConfig import BaseAdapterConfig
from .BaseAdapterUtils  import isFolder, createFolder, writeHugeCSV
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
    paths, CSV formatting options) from a YAML file, and provides a
    common `to_csv()` method for writing the loaded EAV data to disk.
    Concrete subclasses (e.g. HPOAdapter, SCTAdapter) must implement
    `load()` to populate `self.data` from their specific ontology
    source format.
    """

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
        """
        # Initialise instance attributes explicitly so each instance has
        # its own config and data, rather than sharing class-level defaults.
        self.config: BaseAdapterConfig = None
        self.data: pd.DataFrame        = None

        # Open and parse the YAML config file.
        with open(config, "r") as f:
            raw = yaml.safe_load(f)

        # Extract the "adapter" section and validate/coerce it into a
        # BaseAdapterConfig model (raises if required fields are
        # missing/invalid, or if unexpected keys are present, per the
        # model's configuration).
        if adapter_name:
            self.config = BaseAdapterConfig.model_validate(
                raw[configuration_section][adapter_name]
            )
        else:
            self.config = BaseAdapterConfig.model_validate(
                raw[configuration_section]
            )

    @abstractmethod
    def load(self) -> int:
        """
        Load and parse the ontology from the file or directory specified in
        the configuration file.

        Concrete subclasses must implement this to populate `self.data`
        with the parsed ontology content in EAV format.

        Returns
        -------
        int
            Number of EAV rows loaded into self.data.
        """
        return 0

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