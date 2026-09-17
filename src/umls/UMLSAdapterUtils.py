"""
Utility functions and constants for the UMLS adapter.

Provides RRF column layouts, file readers, and EAV transformers for
the MRCONSO and MRDEF RRF release files. All functions are used by
UMLSAdapter.load().
"""

from __future__ import annotations

from ..BaseAdapterUtils import labelClass, definitionClass, referenceClass, synonymClass
from logger             import Logger
import pandas           as pd
import os

# --- Filter value constants ---

# RRF files use "Y" / "N" strings for boolean-like flags (e.g. SUPPRESS).
yes : str = "Y"
no  : str = "N"

# --- Term type constants (values found in the TTY column of MRCONSO) ---

preferredTerm     : str = "PT"   # Preferred term
synonymTerm       : str = "SY"   # Synonym
abbreviationTerm  : str = "AB"   # Abbreviation
preferredNameTerm : str = "PN"   # Preferred name

# --- Language filter ---

# Only English-language rows are extracted from MRCONSO.
englishLanguage : str = "ENG"

# --- EAV additional-column key ---

sourceAbbreviation : str = "source_abbreviation"

# --- RRF source column names (MRCONSO) ---

rrfConceptUniqueIdentifier          : str = "CUI"
rrfLanguage                         : str = "LAT"
rrfTermStatus                       : str = "TS"
rrfLexicalUniqueIdentifier          : str = "LUI"
rrfStringType                       : str = "STT"
rrfStringUniqueIdentifier           : str = "SUI"
rrfIsPreferred                      : str = "ISPREF"
rrfAtomUniqueIdentifier             : str = "AUI"
rrfSourceAtomUniqueIdentifier       : str = "SAUI"
rrfSourceConceptUniqueIdentifier    : str = "SCUI"
rrfSourceDescriptorUniqueIdentifier : str = "SDUI"
rrfSourceAbbreviation               : str = "SAB"
rrfTermType                         : str = "TTY"
rrfSourceCode                       : str = "CODE"
rrfString                           : str = "STR"
rrfSourceRestrictionLevel           : str = "SRL"
rrfSuppressibleFlag                 : str = "SUPPRESS"
rrfContentViewFlag                  : str = "CVF"

# --- RRF source column names (MRDEF) ---

rrfAttributeUniqueIdentifier        : str = "ATUI"
rrfSourceAssertedAttributeIdentifier: str = "SATUI"
rrfDefinition                       : str = "DEF"

# --- RRF source column names (MRSTY) ---

rrfSemanticTypeUniqueIdentifier     : str = "TUI"
rrfSemanticTypeTreeNumber           : str = "STN"
rrfSemanticType                     : str = "STY"

# --- RRF source column names (MRREL) ---

rrfConceptUniqueIdentifier1         : str = "CUI1"
rrfAtomUniqueIdentifier1            : str = "AUI1"
rrfSourceOrAtomIdentifierType1      : str = "STYPE1"
rrfRelationship                     : str = "REL"
rrfConceptUniqueIdentifier2         : str = "CUI2"
rrfAtomUniqueIdentifier2            : str = "AUI2"
rrfSourceOrAtomIdentifierType2      : str = "STYPE2"
rrfRelationshipAttribute            : str = "RELA"
rrfRelationshipUniqueIdentifier     : str = "RUI"
rrfSourceAssertedRelationshipIdentifier : str = "SRUI"
rrfSourceLevel                      : str = "SL"
rrfRelationshipGroup                : str = "RG"
rrfDirectionalityFlag               : str = "DIR"

# --- RRF column layouts ---

mrconsoColumns = [
    rrfConceptUniqueIdentifier,          # ID
    rrfLanguage,                         # Filter: only ENG
    rrfTermStatus,
    rrfLexicalUniqueIdentifier,
    rrfStringType,
    rrfStringUniqueIdentifier,
    rrfIsPreferred,
    rrfAtomUniqueIdentifier,
    rrfSourceAtomUniqueIdentifier,
    rrfSourceConceptUniqueIdentifier,
    rrfSourceDescriptorUniqueIdentifier,
    rrfSourceAbbreviation,               # Additional: source vocabulary
    rrfTermType,                         # Determines attribute: label or synonym
    rrfSourceCode,                       # Value for reference rows
    rrfString,                           # Value for label/synonym rows
    rrfSourceRestrictionLevel,
    rrfSuppressibleFlag,                 # Filter: only N (not suppressed)
    rrfContentViewFlag,
]

mrdefColumns = [
    rrfConceptUniqueIdentifier,          # ID
    rrfAtomUniqueIdentifier,
    rrfAttributeUniqueIdentifier,
    rrfSourceAssertedAttributeIdentifier,
    rrfSourceAbbreviation,               # Additional: source vocabulary
    rrfDefinition,                       # Value
    rrfSuppressibleFlag,                 # Filter: only N (not suppressed)
    rrfContentViewFlag,
]

mrstyColumns = [
    rrfConceptUniqueIdentifier,
    rrfSemanticTypeUniqueIdentifier,
    rrfSemanticTypeTreeNumber,
    rrfSemanticType,
    rrfAttributeUniqueIdentifier,
    rrfContentViewFlag,
]

mrrelColumns = [
    rrfConceptUniqueIdentifier1,
    rrfAtomUniqueIdentifier1,
    rrfSourceOrAtomIdentifierType1,
    rrfRelationship,
    rrfConceptUniqueIdentifier2,
    rrfAtomUniqueIdentifier2,
    rrfSourceOrAtomIdentifierType2,
    rrfRelationshipAttribute,
    rrfRelationshipUniqueIdentifier,
    rrfSourceAssertedRelationshipIdentifier,
    rrfSourceAbbreviation,
    rrfSourceLevel,
    rrfRelationshipGroup,
    rrfDirectionalityFlag,
    rrfSuppressibleFlag,
    rrfContentViewFlag,
]

# --- RRF filename prefixes ---

conceptPrefix    : str = "MRCONSO"
definitionPrefix : str = "MRDEF"


def _readRRFFile(
    path     : str,
    columns  : list[str],
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read a UMLS RRF file into a DataFrame.

    RRF files have no header row — column names are supplied explicitly
    from the UMLS documentation. A trailing pipe at the end of each row
    means pandas sees one extra unnamed column; it is read into a
    temporary "_" column and dropped immediately after loading.

    All columns are read as strings to avoid misinterpreting CUIs or
    other numeric-looking fields.

    Parameters
    ----------
    path : str
        Path to the RRF file.
    columns : list[str]
        Column names in the order they appear in the file, per the
        UMLS documentation.
    encoding : str
        Character encoding of the file.
    separator : str
        Field delimiter (pipe "|" for standard RRF files).

    Returns
    -------
    pd.DataFrame
        DataFrame with one row per RRF record and named columns.
    """
    l = Logger()
    l.printFileProcessingStart(path)
    ret = pd.read_csv(
        path,
        sep        = separator,
        header     = None,
        names      = columns + ["_"],  # absorb the trailing pipe
        dtype      = str,
        encoding   = encoding,
        low_memory = False,
    )
    l.printFileProcessingEnd(path)
    l.log(f"{len(ret)} entities of UMLS extracted.")
    return ret.drop(columns="_", errors="ignore")


def readMRCONSOFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read MRCONSO.RRF: one row per concept string across all source
    vocabularies, including preferred terms, synonyms, and source codes.
    """
    return _readRRFFile(path, mrconsoColumns, encoding, separator)


def readMRDEFFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read MRDEF.RRF: one row per concept definition, sourced from
    individual vocabularies included in the UMLS Metathesaurus.
    """
    return _readRRFFile(path, mrdefColumns, encoding, separator)


def readMRSTYFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read MRSTY.RRF: one row per semantic type assignment, linking each
    CUI to one or more entries in the UMLS Semantic Network.
    """
    return _readRRFFile(path, mrstyColumns, encoding, separator)


def getConcepts(
    data             : pd.DataFrame,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str,
) -> pd.DataFrame:
    """
    Convert a raw MRCONSO DataFrame into EAV rows.

    Only English, non-suppressed rows are kept. The TTY (term type)
    column determines the EAV attribute:
    - PT / PN  -> label
    - SY / AB  -> synonym

    Each string (STR) produces one label or synonym row. Each source
    code (CODE) produces one reference row carrying the source
    abbreviation (SAB) as additional information.
    """
    l = Logger()

    # Keep only English, non-suppressed rows.
    filtered = data[
        (data[rrfLanguage] == englishLanguage) &
        (data[rrfSuppressibleFlag] == no)
    ].copy()

    l.log(f"Transforming {len(filtered)} rows into EAV schema...")

    # Map TTY to EAV attribute name.
    tty_to_attribute = {
        preferredTerm    : labelClass,
        preferredNameTerm: labelClass,
        synonymTerm      : synonymClass,
        abbreviationTerm : synonymClass,
    }
    attribute_series = filtered[rrfTermType].map(tty_to_attribute)

    # Build label/synonym rows for rows with a known TTY and a non-empty string.
    known      = filtered[attribute_series.notna() & filtered[rrfString].notna() & (filtered[rrfString] != "")].copy()
    attributes = attribute_series[attribute_series.notna() & filtered[rrfString].notna() & (filtered[rrfString] != "")]

    label_synonym_rows = pd.DataFrame({
        id_column        : known[rrfConceptUniqueIdentifier].values,
        attribute_column : attributes.values,
        value_column     : known[rrfString].values,
        additional_column: known[rrfSourceAbbreviation].map(
            lambda v: {sourceAbbreviation: v}
        ).values,
    })

    # Build reference rows for rows with a non-empty source code.
    has_code = filtered[filtered[rrfSourceCode].notna() & (filtered[rrfSourceCode] != "")].copy()

    reference_rows = pd.DataFrame({
        id_column        : has_code[rrfConceptUniqueIdentifier].values,
        attribute_column : [referenceClass] * len(has_code),
        value_column     : has_code[rrfSourceCode].values,
        additional_column: has_code[rrfSourceAbbreviation].map(
            lambda v: {sourceAbbreviation: v}
        ).values,
    })

    l.log(f"Transforming {len(filtered)} rows into EAV schema completed.")
    l.log("Removing duplicated rows...")

    result = (
        pd.concat([label_synonym_rows, reference_rows], ignore_index=True)
        .drop_duplicates(subset=[id_column, attribute_column, value_column])
        .reset_index(drop=True)
    )

    l.log(f"Removing duplicated rows completed. {len(result)} rows left.")
    return result


def getDefinitions(
    data             : pd.DataFrame,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str,
) -> pd.DataFrame:
    """
    Convert a raw MRDEF DataFrame into EAV rows.

    Only non-suppressed rows with a non-empty definition string are kept.
    Each definition produces one row with attribute set to definitionClass,
    and the source abbreviation (SAB) carried as additional information.
    """
    l = Logger()

    # Keep only non-suppressed rows with a non-empty definition.
    filtered = data[
        (data[rrfSuppressibleFlag] == no) &
        data[rrfDefinition].notna() &
        (data[rrfDefinition].str.strip() != "")
    ].copy()

    l.log(f"Transforming {len(filtered)} rows into EAV schema...")

    result = pd.DataFrame({
        id_column        : filtered[rrfConceptUniqueIdentifier].values,
        attribute_column : [definitionClass] * len(filtered),
        value_column     : filtered[rrfDefinition].values,
        additional_column: filtered[rrfSourceAbbreviation].map(
            lambda v: {sourceAbbreviation: v}
        ).values,
    })

    l.log(f"Transforming {len(filtered)} rows into EAV schema completed.")
    l.log("Removing duplicated rows...")

    result = (
        result
        .drop_duplicates(subset=[id_column, attribute_column, value_column])
        .reset_index(drop=True)
    )

    l.log(f"Removing duplicated rows completed. {len(result)} rows left.")
    return result


# Ordered (prefix, reader/transformer) pairs, checked against a file's
# basename. A more specific prefix must be listed before any shorter
# prefix it could also satisfy; none of the current RRF prefixes overlap,
# but new file types should be added with that in mind.
_rrfReadersByPrefix = {
    conceptPrefix   : readMRCONSOFile,
    definitionPrefix: readMRDEFFile,
}
_rrfTransformersByPrefix = {
    conceptPrefix   : getConcepts,
    definitionPrefix: getDefinitions,
}


def readRRFFileByPath(
    file_path        : str,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str,
    encoding         : str,
    separator        : str
) -> pd.DataFrame:
    """
    Read a single RRF file and convert it to EAV rows.

    Chooses the appropriate reader function — and therefore the
    appropriate column layout — based on the file's own name.
    file_path must point directly to the file itself, not to the
    directory containing it. Returns None and logs a warning if the
    filename doesn't start with any of the known RRF prefixes.
    """
    ret      = None
    l        = Logger()
    filename = os.path.basename(file_path)

    for prefix, reader in _rrfReadersByPrefix.items():
        if filename.startswith(prefix):
            ret = reader(file_path, encoding, separator)
            ret = _rrfTransformersByPrefix[prefix](
                ret,
                id_column,
                attribute_column,
                value_column,
                additional_column
            )
            break

    if ret is None:
        l.log(f"'{filename}' doesn't match any known RRF file prefix.")

    return ret