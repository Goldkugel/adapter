"""
Utility functions and constants for the UMLS adapter.

RRF column layouts, file readers and EAV transformers for MRCONSO and
MRDEF. The MRSTY and MRREL layouts and the MRSTY reader are not yet wired
into readRRFFileByPath(), so those files are skipped if configured.
"""

from __future__ import annotations

from ..BaseAdapterUtils import (
    labelClass, definitionClass, referenceClass, synonymClass,
    additionalFrom, readFileByPrefix,
)
from logger             import Logger
import pandas           as pd
import csv

# RRF flag values (e.g. SUPPRESS, ISPREF).
rrfYes : str = "Y"
rrfNo  : str = "N"

# Term types (MRCONSO column TTY).
preferredTerm     : str = "PT"   # Preferred term
synonymTerm       : str = "SY"   # Synonym
abbreviationTerm  : str = "AB"   # Abbreviation
preferredNameTerm : str = "PN"   # Preferred name

# Preferred-atom flags, used to pick a label for concepts without a PT/PN
# string: TS "P" (preferred LUI), STT "PF" (preferred form), ISPREF "Y".
preferredTermStatus : str = "P"
preferredStringType : str = "PF"

englishLanguage : str = "ENG"

# CODE of atoms without a source code (e.g. most MTH atoms); gives no
# reference row.
noCode : str = "NOCODE"

# Key of the SAB in the additional dict.
sourceAbbreviation : str = "source_abbreviation"

# RRF column names: MRCONSO, then MRDEF, MRSTY and MRREL.
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

rrfAttributeUniqueIdentifier        : str = "ATUI"
rrfSourceAssertedAttributeIdentifier: str = "SATUI"
rrfDefinition                       : str = "DEF"

rrfSemanticTypeUniqueIdentifier     : str = "TUI"
rrfSemanticTypeTreeNumber           : str = "STN"
rrfSemanticType                     : str = "STY"

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

# Full column layouts in file order.
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

conceptPrefix    : str = "MRCONSO"
definitionPrefix : str = "MRDEF"


# Rows per chunk; each chunk is filtered before the next is read, as
# MRCONSO has well over ten million rows.
rrfChunkSize : int = 1_000_000

# Columns the transformers use; skipping the rest saves most of the
# memory, since every value is a Python string.
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
    return (data[rrfLanguage] == englishLanguage) & (data[rrfSuppressibleFlag] == rrfNo)


def _isNotSuppressed(data: pd.DataFrame) -> pd.Series:
    """Row mask for non-suppressed (SUPPRESS = N) rows."""
    return data[rrfSuppressibleFlag] == rrfNo


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

    All columns are read as strings, quote characters are kept, and NA
    detection is off so "NA" (sodium) or "None" stay strings; empty fields
    become "". The file is read in chunks of rrfChunkSize rows, each
    filtered by rowFilter, so the whole file is never held in memory.

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
        names           = columns + ["_"],  # column after the trailing pipe
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

    l.log(f"{len(ret)} entities of UMLS extracted.")
    l.printFileProcessingEnd(path)
    return ret


def readMRCONSOFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read MRCONSO.RRF (concept strings of all source vocabularies), keeping
    the columns getConcepts() uses and English, non-suppressed rows.
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
    Read MRDEF.RRF (definitions of the source vocabularies), keeping the
    columns getDefinitions() uses and non-suppressed rows.
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

    Atoms are ranked by the preferred-atom flags, TS = P outweighing
    STT = PF outweighing ISPREF = Y; ties keep file order. The SAB goes to
    the additional dict.
    """
    candidates = data[data[rrfString].notna() & (data[rrfString] != "")]

    # Lower is better; each missing flag adds its weight.
    rank = (
        (candidates[rrfTermStatus]  != preferredTermStatus).astype(int) * 4 +
        (candidates[rrfStringType]  != preferredStringType).astype(int) * 2 +
        (candidates[rrfIsPreferred] != rrfYes).astype(int)
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
        additional_column: additionalFrom(best[rrfSourceAbbreviation], sourceAbbreviation),
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

    A concept without a PT/PN string gets one label from its preferred
    atom (see _getFallbackLabels). Each real source code (CODE) gives a
    reference row. All rows carry the SAB as additional information;
    duplicates across sources are merged later by load().
    """
    l = Logger()

    # readMRCONSOFile() already filters; this covers frames read otherwise.
    filtered = data[_isEnglishAndNotSuppressed(data)].copy()

    l.log(f"Transforming {len(filtered)} rows into EAV schema...")

    tty_to_attribute = {
        preferredTerm    : labelClass,
        preferredNameTerm: labelClass,
        synonymTerm      : synonymClass,
        abbreviationTerm : synonymClass,
    }
    # Other TTYs map to NaN and produce no label/synonym row.
    attribute_series = filtered[rrfTermType].map(tty_to_attribute)

    # One mask for rows and attributes keeps them aligned.
    has_term   = attribute_series.notna() & filtered[rrfString].notna() & (filtered[rrfString] != "")
    known      = filtered[has_term].copy()
    attributes = attribute_series[has_term]

    label_synonym_rows = pd.DataFrame({
        id_column        : known[rrfConceptUniqueIdentifier].values,
        attribute_column : attributes.values,
        value_column     : known[rrfString].values,
        additional_column: additionalFrom(known[rrfSourceAbbreviation], sourceAbbreviation),
    })

    # Pass all atoms (any TTY) of the unlabelled concepts, since the
    # preferred atom can have any term type.
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

    has_code = filtered[
        filtered[rrfSourceCode].notna() &
        (filtered[rrfSourceCode] != "") &
        (filtered[rrfSourceCode] != noCode)
    ].copy()

    reference_rows = pd.DataFrame({
        id_column        : has_code[rrfConceptUniqueIdentifier].values,
        attribute_column : [referenceClass] * len(has_code),
        value_column     : has_code[rrfSourceCode].values,
        additional_column: additionalFrom(has_code[rrfSourceAbbreviation], sourceAbbreviation),
    })

    l.log(f"Transforming {len(filtered)} rows into EAV schema completed.")

    return pd.concat([label_synonym_rows, fallback_rows, reference_rows], ignore_index=True)


def getDefinitions(
    data             : pd.DataFrame,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str,
) -> pd.DataFrame:
    """
    Convert a raw MRDEF DataFrame into EAV rows.

    Keeps non-suppressed rows with a non-empty definition, with the SAB as
    additional information; duplicates across sources are merged later by
    load().
    """
    l = Logger()

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
        additional_column: additionalFrom(filtered[rrfSourceAbbreviation], sourceAbbreviation),
    })

    l.log(f"Transforming {len(filtered)} rows into EAV schema completed.")
    return result


# Checked in order against a file's basename; the first match wins, so a
# new prefix must precede any shorter prefix it also matches.
_rrfHandlersByPrefix = {
    conceptPrefix    : (readMRCONSOFile, getConcepts),
    definitionPrefix : (readMRDEFFile,   getDefinitions),
}


def readRRFFileByPath(
    file_path        : str,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str,
    encoding         : str,
    separator        : str
) -> pd.DataFrame | None:
    """
    Read a single RRF file and convert it to EAV rows.

    The reader is chosen by the file's own name, so file_path must point
    to the file, not its directory. Returns None (and logs) if no known
    RRF prefix matches.
    """
    return readFileByPrefix(
        file_path, _rrfHandlersByPrefix, "RRF",
        id_column, attribute_column, value_column, additional_column,
        encoding, separator,
    )
