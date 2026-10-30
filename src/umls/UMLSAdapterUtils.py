"""
Utility functions and constants for the UMLS adapter.

Provides RRF column layouts, file readers, and EAV transformers for
the MRCONSO and MRDEF RRF release files, which UMLSAdapter._loadFrames()
processes. Column layouts for MRSTY and MRREL, and a reader for MRSTY,
are defined as well but not yet wired into readRRFFileByPath(), so
those files are skipped if configured.
"""

from __future__ import annotations

from ..BaseAdapterUtils import labelClass, definitionClass, referenceClass, synonymClass
from logger             import Logger
import pandas           as pd
import os
import csv

# --- Filter value constants ---

# RRF files use "Y" / "N" strings for boolean-like flags (e.g. SUPPRESS).
yes : str = "Y"
no  : str = "N"

# --- Term type constants (values found in the TTY column of MRCONSO) ---

preferredTerm     : str = "PT"   # Preferred term
synonymTerm       : str = "SY"   # Synonym
abbreviationTerm  : str = "AB"   # Abbreviation
preferredNameTerm : str = "PN"   # Preferred name

# --- Preferred-atom flag values (MRCONSO columns TS, STT and ISPREF) ---

# Used to pick a label for concepts without a PT/PN string: the atom
# whose term status is "P" (preferred LUI of the concept), string type
# "PF" (preferred form of the term) and ISPREF "Y" (preferred atom of
# the string) is the concept's preferred atom.
preferredTermStatus : str = "P"
preferredStringType : str = "PF"

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
    rrfTermStatus,                       # Fallback label: TS = P
    rrfLexicalUniqueIdentifier,
    rrfStringType,                       # Fallback label: STT = PF
    rrfStringUniqueIdentifier,
    rrfIsPreferred,                      # Fallback label: ISPREF = Y
    rrfAtomUniqueIdentifier,
    rrfSourceAtomUniqueIdentifier,
    rrfSourceConceptUniqueIdentifier,
    rrfSourceDescriptorUniqueIdentifier,
    rrfSourceAbbreviation,               # Additional: source vocabulary
    rrfTermType,                         # Determines attribute: label, synonym or none
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


# Rows read from an RRF file at a time. Each chunk is filtered before
# the next one is read, so only the rows that are kept accumulate in
# memory (MRCONSO alone has well over ten million rows).
rrfChunkSize : int = 1_000_000

# Columns of MRCONSO and MRDEF that the transformers below use. The
# other columns are skipped while reading, which saves most of the
# memory since every value is held as a Python string.
mrconsoUsedColumns = [
    rrfConceptUniqueIdentifier,
    rrfLanguage,
    rrfTermStatus,
    rrfStringType,
    rrfIsPreferred,
    rrfSourceAbbreviation,
    rrfTermType,
    rrfSourceCode,
    rrfString,
    rrfSuppressibleFlag,
]

mrdefUsedColumns = [
    rrfConceptUniqueIdentifier,
    rrfSourceAbbreviation,
    rrfDefinition,
    rrfSuppressibleFlag,
]


def _isEnglishAndNotSuppressed(data: pd.DataFrame) -> pd.Series:
    """Row mask for English (LAT = ENG), non-suppressed (SUPPRESS = N) rows."""
    return (data[rrfLanguage] == englishLanguage) & (data[rrfSuppressibleFlag] == no)


def _isNotSuppressed(data: pd.DataFrame) -> pd.Series:
    """Row mask for non-suppressed (SUPPRESS = N) rows."""
    return data[rrfSuppressibleFlag] == no


def _readRRFFile(
    path      : str,
    columns   : list[str],
    encoding  : str,
    separator : str,
    usecols   : list[str] | None = None,
    rowFilter = None
) -> pd.DataFrame:
    """
    Read a UMLS RRF file into a DataFrame.

    RRF files have no header row — column names are supplied explicitly
    from the UMLS documentation. A trailing pipe at the end of each row
    means pandas sees one extra unnamed column; it is named "_" so that
    it can be told apart from the real columns, and is never kept.

    All columns are read as strings to avoid misinterpreting CUIs or
    other numeric-looking fields. RRF has no quoting, so quote characters
    are kept as part of the string, and NA detection is disabled so
    strings like "NA" (sodium) or "None" are not turned into missing
    values; empty fields become "".

    The file is read in chunks of rrfChunkSize rows, and rowFilter is
    applied to each chunk before the next one is read, so the full file
    is never held in memory at once.

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
    usecols : list[str], optional
        Subset of `columns` to read. All columns if omitted.
    rowFilter : callable, optional
        Function taking a chunk and returning a boolean row mask; only
        rows where it is True are kept. All rows if omitted.

    Returns
    -------
    pd.DataFrame
        DataFrame with one row per kept RRF record and the read columns.
    """
    l = Logger()
    l.printFileProcessingStart(path)

    if usecols is None:
        usecols = columns

    reader = pd.read_csv(
        path,
        sep             = separator,
        header          = None,
        names           = columns + ["_"],  # absorb the trailing pipe
        usecols         = usecols,
        dtype           = str,
        encoding        = encoding,
        quoting         = csv.QUOTE_NONE,
        keep_default_na = False,
        chunksize       = rrfChunkSize,
    )

    chunks = []
    for chunk in reader:
        if rowFilter is not None:
            chunk = chunk[rowFilter(chunk)]
        chunks.append(chunk)

    # pd.concat needs at least one frame; an empty file yields none.
    if chunks:
        ret = pd.concat(chunks, ignore_index=True)
    else:
        ret = pd.DataFrame(columns=usecols, dtype=str)

    # read_csv returns usecols in file order; restore the requested order.
    ret = ret[usecols]

    l.printFileProcessingEnd(path)
    l.log(f"{len(ret)} entities of UMLS extracted.")
    return ret


def readMRCONSOFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read MRCONSO.RRF: one row per concept string across all source
    vocabularies, including preferred terms, synonyms, and source codes.

    Only the columns used by getConcepts() and only English,
    non-suppressed rows are kept.
    """
    return _readRRFFile(
        path, mrconsoColumns, encoding, separator,
        usecols   = mrconsoUsedColumns,
        rowFilter = _isEnglishAndNotSuppressed,
    )


def readMRDEFFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read MRDEF.RRF: one row per concept definition, sourced from
    individual vocabularies included in the UMLS Metathesaurus.

    Only the columns used by getDefinitions() and only non-suppressed
    rows are kept.
    """
    return _readRRFFile(
        path, mrdefColumns, encoding, separator,
        usecols   = mrdefUsedColumns,
        rowFilter = _isNotSuppressed,
    )


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


def _getFallbackLabels(
    data             : pd.DataFrame,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str,
) -> pd.DataFrame:
    """
    Pick one label per concept from a raw (filtered) MRCONSO DataFrame.

    Used for concepts that have no PT/PN string. Each concept's atoms
    are ranked by how many of the preferred-atom flags they have, in
    this order: TS = P, STT = PF, ISPREF = Y. The string of the best
    atom becomes the label; ties keep the first atom in file order.
    The source abbreviation (SAB) is carried as additional information.
    """
    candidates = data[data[rrfString].notna() & (data[rrfString] != "")]

    # Lower rank is better; each missing flag adds its weight, so TS
    # outweighs STT, which outweighs ISPREF.
    rank = (
        (candidates[rrfTermStatus]  != preferredTermStatus).astype(int) * 4 +
        (candidates[rrfStringType]  != preferredStringType).astype(int) * 2 +
        (candidates[rrfIsPreferred] != yes).astype(int)
    )
    best = (
        candidates.assign(_rank=rank.values)
        .sort_values("_rank", kind="stable")
        .drop_duplicates(subset=[rrfConceptUniqueIdentifier], keep="first")
    )

    return pd.DataFrame({
        id_column        : best[rrfConceptUniqueIdentifier].values,
        attribute_column : [labelClass] * len(best),
        value_column     : best[rrfString].values,
        additional_column: best[rrfSourceAbbreviation].map(
            lambda v: {sourceAbbreviation: v}
        ).values,
    })


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

    Each string (STR) produces one label or synonym row. Each concept
    without a PT/PN string gets one label from its preferred atom
    instead (see _getFallbackLabels). Each source code (CODE) produces
    one reference row carrying the source abbreviation (SAB) as
    additional information.
    """
    l = Logger()

    # Keep only English, non-suppressed rows. readMRCONSOFile() already
    # drops the others while reading; this keeps the transformer correct
    # for frames that were read without that filter.
    filtered = data[_isEnglishAndNotSuppressed(data)].copy()

    l.log(f"Transforming {len(filtered)} rows into EAV schema...")

    # Map TTY to EAV attribute name.
    tty_to_attribute = {
        preferredTerm    : labelClass,
        preferredNameTerm: labelClass,
        synonymTerm      : synonymClass,
        abbreviationTerm : synonymClass,
    }
    # Other TTYs map to NaN and produce no label/synonym row.
    attribute_series = filtered[rrfTermType].map(tty_to_attribute)

    # Build label/synonym rows for rows with a known TTY and a non-empty
    # string; the same mask is applied to the rows and to their attribute
    # names, so the two stay aligned.
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

    # Give every concept without a PT/PN label one label from its
    # preferred atom. Only the atoms of those concepts are passed on, but
    # all of their atoms (any TTY), since the preferred atom can have any
    # term type.
    labelled = label_synonym_rows.loc[
        label_synonym_rows[attribute_column] == labelClass, id_column
    ]
    fallback_rows = _getFallbackLabels(
        filtered[~filtered[rrfConceptUniqueIdentifier].isin(labelled)],
        id_column,
        attribute_column,
        value_column,
        additional_column,
    )

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
        pd.concat([label_synonym_rows, fallback_rows, reference_rows], ignore_index=True)
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

    # Keep only non-suppressed rows with a non-empty definition
    # (readMRDEFFile() already drops suppressed rows while reading).
    filtered = data[
        _isNotSuppressed(data) &
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


# Prefix -> reader and prefix -> transformer lookups, checked in
# insertion order against a file's basename; the first matching prefix
# wins. A more specific prefix must be listed before any shorter
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