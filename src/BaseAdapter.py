import sys

# Prevent Python from generating .pyc bytecode files
sys.dont_write_bytecode = True

from abc                import ABC, abstractmethod
from .BaseAdapterConfig import *
from logger             import Logger
from .BaseAdapterUtils  import *
import pandas           as pd
import yaml
import os

# Key under which adapter settings are expected to live in the YAML config file.
configuration_section: str  = "adapter"

# Default path to the config file, used if no path is explicitly passed in.
standard_directory: str     = "../config/config.yaml"

def isFile(path: str = "") -> bool:
    """
    Check whether the given path refers to an existing file.

    Parameters
    ----------
    path : str, optional
        Path to check.

    Returns
    -------
    bool
        True if the path exists and is a file, False otherwise.
    """
    return os.path.isfile(path)


def isFolder(path: str = "") -> bool:
    """
    Check whether the given path refers to an existing directory.

    Parameters
    ----------
    path : str, optional
        Path to check.

    Returns
    -------
    bool
        True if the path exists and is a directory, False otherwise.
    """
    return os.path.isdir(path)


def createFolder(path: str = "") -> bool:
    """
    Create a directory if it does not already exist.

    A log message is written indicating whether the directory was created
    or already existed.

    Parameters
    ----------
    path : str, optional
        Path of the directory to create.

    Returns
    -------
    bool
        True if the directory was created, False if it already existed.
    """
    ret = False

    l = Logger()
    base_name = os.path.basename(path)

    if not isFolder(path):
        os.makedirs(path)
        l.log(f"Folder '{base_name}' created.")
        ret = True
    else:
        l.log(f"Folder '{base_name}' already exists.")

    return ret

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

    # Validated configuration object (input path, output folder/file
    # name, delimiter, encoding, etc.)
    config: BaseAdapterConfig = None

    # The DataFrame containing the loaded data in EAV format (entity_id,
    # attribute, value), with an additional column containing extra
    # information as a JSON object where needed.
    data: pd.DataFrame = None

    def __init__(self, config: str = standard_directory, adapter_name: str = ""):
        """
        Load and validate adapter configuration from a YAML file.
        """
        # Open and parse the YAML config file.
        with open(config, "r") as f:
            data = yaml.safe_load(f)

        # Extract the "adapter" section and validate/coerce it into a
        # BaseAdapterConfig model (raises if required fields are
        # missing/invalid, or if unexpected keys are present, per the
        # model's configuration).
        if len(adapter_name) > 0:
            self.config = BaseAdapterConfig.model_validate(
                data[configuration_section][adapter_name]
            )
        else:
            self.config = BaseAdapterConfig.model_validate(
                data[configuration_section]
            )

    @abstractmethod
    def load(self) -> int:
        """
        Load and parse the ontology from the file or directory specified in
        the configuration file.

        Concrete subclasses must implement this to populate `self.data`
        with the parsed ontology content in EAV format.
        """

    def to_csv(self) -> int:
        # Write self.data to disk at the configured output location,
        # using the configured delimiter and encoding. Shared across
        # all adapters, since the write logic itself doesn't depend on
        # which ontology was loaded.

        # Creating folder if it does not exist.
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