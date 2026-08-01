import sys

# Prevent Python from generating .pyc files (compiled bytecode files)
sys.dont_write_bytecode = True

from pydantic import BaseModel, ConfigDict

class BaseAdapterConfig(BaseModel):
    """
    Pydantic model defining and validating the configuration schema shared
    by all ontology adapters.

    Instances are typically created via `Adapter()`. Pydantic validates
    field types and enforces defaults for any fields not present in the
    supplied data.

    Ontology-specific adapters that need additional fields (e.g. a release
    version, or source-specific file paths) should subclass this model
    rather than modifying it directly.
    """

    # Reject any keys in the input data that aren't explicitly defined below.
    # This catches typos or outdated config keys early, instead of silently
    # ignoring them.
    model_config = ConfigDict(extra = "forbid")

    # Path to the raw ontology file (or directory, for multi-file formats
    # like SNOMED RF2) that this adapter should load.
    input_folder: str       = "../data/input/"

    # The list of input files to process.
    input_files: list       = []

    # Directory where the output CSV file will be written (relative or
    # absolute path).
    output_folder: str      = "../data/output/transformed/"

    # Name of the CSV file to write to within `output_folder`.
    output_file: str        = "ontology.csv"

    # Field delimiter used when writing the EAV CSV file.
    delimiter: str          = ";"

    # Character encoding used when writing the CSV file.
    encoding: str           = "utf-8"

    # The column where the IDs will be stored. 
    id_column: str          = "id"

    # The column where the attribute names will be stored.
    attribute_column: str   = "attribute"

    # The column where the values will be stored.
    value_column: str       = "value"

    # The column where additional information in form of a JSON object will be
    # stored.
    additional_column: str  = "additional"

    # Skip if the output file is already present. 
    skip_if_present: bool   = False

    # The encoding of the files if necessary.
    encoding: str           = "utf-8"

    # The separator of tabular files if necessary.
    separator: str          = "\t"