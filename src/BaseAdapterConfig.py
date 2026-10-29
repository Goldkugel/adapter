from pydantic import BaseModel, ConfigDict

class BaseAdapterConfig(BaseModel):
    """
    Pydantic model defining and validating the configuration schema shared
    by all ontology adapters.

    Instances are created by `BaseAdapter.__init__()` from one section of
    the YAML config file (e.g. `adapter.hpo`). Pydantic validates field
    types and enforces defaults for any fields not present in the
    supplied data.

    Ontology-specific adapters that need additional fields (e.g. a release
    version, or source-specific file paths) should subclass this model
    rather than modifying it directly.
    """

    # Reject any keys in the input data that aren't explicitly defined below.
    # This catches typos or outdated config keys early, instead of silently
    # ignoring them.
    model_config = ConfigDict(extra = "forbid")

    # Directory containing the raw ontology input file(s).
    input_folder: str       = "./data/input/"

    # The list of input files to process.
    input_files: list[str]  = []

    # Directory where the output CSV file will be written (relative or
    # absolute path).
    output_folder: str      = "./data/output/transformed/"

    # Name of the CSV file to write to within `output_folder`.
    output_file: str        = "ontology.csv"

    # Field delimiter used when writing the EAV CSV file (output). See
    # `separator` for the delimiter of the input files.
    delimiter: str          = ";"

    # Character encoding used for both reading input files and writing
    # the output CSV file.
    encoding: str           = "utf-8"

    # The column where the IDs will be stored.
    id_column: str          = "id"

    # The column where the attribute names will be stored.
    attribute_column: str   = "attribute"

    # The column where the values will be stored.
    value_column: str       = "value"

    # The column where additional information is stored as a dict (written
    # to the CSV as a Python dict literal, readable with ast.literal_eval).
    additional_column: str  = "additional"

    # If True, load() does nothing when the output file already exists.
    skip_if_present: bool   = False

    # Prefix put in front of every ID, and in front of the value of every
    # child row (which is an ID as well), e.g. "SNOMEDCT_US:" turns
    # "404684003" into "SNOMEDCT_US:404684003". Empty for sources whose
    # IDs already carry a prefix, such as HPO ("HP:0000118"). If the
    # config section doesn't set it, the adapter's own default applies
    # (see BaseAdapter.default_prefix).
    prefix: str             = ""

    # Field separator used when reading tabular input files (input), e.g.
    # "\t" for SNOMED CT RF2 and "|" for UMLS RRF. Unused by the HPO
    # adapter, which parses an OWL file.
    separator: str          = "\t"