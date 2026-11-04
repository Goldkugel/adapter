from pydantic import BaseModel, ConfigDict

class BaseAdapterConfig(BaseModel):
    """
    Pydantic model defining and validating the configuration schema shared
    by all ontology adapters.

    Built by `BaseAdapter.__init__()` from one section of the YAML config
    file (e.g. `adapter.hpo`) or a dict, or passed in directly. Fields only
    some adapters use (e.g. `separator`) are ignored by the others.
    """

    # Reject unknown keys, so typos and outdated config keys fail early.
    model_config = ConfigDict(extra = "forbid")

    input_folder: str       = "./data/input/"
    input_files: list[str]  = []
    output_folder: str      = "./data/output/transformed/"
    output_file: str        = "ontology.csv"

    # Delimiter of the output CSV; `separator` is the one of the input.
    delimiter: str          = ";"

    # Used for reading the input and writing the output.
    encoding: str           = "utf-8"

    # Output column names.
    id_column: str          = "id"
    attribute_column: str   = "attribute"
    value_column: str       = "value"

    # Holds a dict, written as a Python literal (read with ast.literal_eval).
    additional_column: str  = "additional"

    # If True, load() does nothing when the output file already exists.
    skip_if_present: bool   = False

    # Put in front of every ID and every child row value, e.g.
    # "SNOMEDCT_US:404684003". Defaults to BaseAdapter.default_prefix if
    # the config section doesn't set it (empty for HPO, whose IDs have one).
    prefix: str             = ""

    # Separator of tabular input files: "\t" for SNOMED CT RF2, "|" for
    # UMLS RRF. Unused by HPO (OWL).
    separator: str          = "\t"